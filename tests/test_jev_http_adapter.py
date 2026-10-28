"""Jev's network and durable budget contract, entirely with offline transports."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from deposium_bench import jev_http_adapter as module
from deposium_bench.http_budget import HTTPBudget, BudgetError
from deposium_bench.jev_http_adapter import JevHTTPAdapter, JevProfileError, validate_model_profile

KEY = 'offline-fixture-secret-1234567890'


def native(model='jev-1.13.0'):
    return {'model':model,'answers':{'answer':{'type':'choice','choice':'Unknown',
             'probabilities':{'Known':.2,'Unknown':.8},'confidence':.8}},
            'usage':{'input_tokens':17,'output_tokens':2}}


class FakeSocket:
    def __init__(self): self.timeouts = []; self.shutdowns = 0
    def settimeout(self, value): self.timeouts.append(value)
    def shutdown(self, how): self.shutdowns += 1


class FakeResponse:
    def __init__(self, data=None, status=200, headers=None):
        self.body = json.dumps(native() if data is None else data).encode() if not isinstance(data, bytes) else data
        self.status = status
        self.headers = headers or {'x-typesafe-request-id':'safe-id-123'}
        self.closed = False
    def getheader(self, name): return self.headers.get(name)
    def read1(self, size):
        piece, self.body = self.body[:size], self.body[size:]
        return piece
    def close(self): self.closed = True


class FakeConnection:
    response = None
    request_error = None
    calls = []
    def __init__(self, host, **kwargs):
        self.host, self.kwargs = host, kwargs
        self.sock = FakeSocket(); self.closed = False
        self.__class__.calls.append(self)
    def connect(self): pass
    def request(self, method, path, body, headers):
        self.method, self.path, self.body, self.headers = method, path, body, headers
        if self.__class__.request_error is not None:
            raise self.__class__.request_error
    def getresponse(self): return self.__class__.response
    def close(self): self.closed = True


class JevHTTPTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root/'profiles'/'profile.json'
        self.path.parent.mkdir()
        self.ledger = self.root/'results'/'budget.jsonl'
        self.profile = {'schema_version':'deposium.candidate/v1','profile_id':'offline-jev',
                        'adapter':'jev_http','qualification':'model_isolated','capabilities':['bench.context-choice'],
                        'revision':None,'recordings':None,'timeout_seconds':1,
                        'model':{'endpoint':module.ENDPOINT,'model_id':'jev-1.13.0',
                                 'credential_env':'TYPESAFE_API_KEY','budget_ledger':'../results/budget.jsonl',
                                 'max_requests':800,'max_input_tokens':2_000_000,'reserved_input_tokens_per_request':65536,
                                 'max_request_bytes':131072,'min_interval_seconds':.1}}
        FakeConnection.response = FakeResponse()
        FakeConnection.request_error = None
        FakeConnection.calls = []
        for replacement in (patch.object(module,'HTTPSConnection',FakeConnection),
                            patch.dict(os.environ,{'TYPESAFE_API_KEY':KEY})):
            replacement.start(); self.addCleanup(replacement.stop)
    def adapter(self, profile=None):
        adapter=JevHTTPAdapter(profile or self.profile,self.path)
        self.addCleanup(adapter.close)
        return adapter
    def request(self, context='Ordinary context'):
        return {'case_id':'SEMANTIC_GOLD_PRIVATE','contract_id':'bench.context-choice',
                'input':{'context':context,'question':'Choose the compatible answer',
                         'options':[{'id':'opaque-first','description':'Known'},
                                    {'id':'opaque-second','description':'Unknown'}]}}
    def records(self): return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def test_profile_is_bounded_and_exact(self):
        validate_model_profile(self.profile)
        changes = [lambda p:p['model'].update(endpoint='http://api.typesafe.ai/v1/systemone'),
                   lambda p:p['model'].update(model_id='jev-latest'),lambda p:p['model'].update(credential_env='OTHER'),
                   lambda p:p['model'].update(max_requests=801),lambda p:p['model'].update(max_input_tokens=2_000_001),
                   lambda p:p['model'].update(max_requests=True),lambda p:p['model'].update(max_request_bytes=131073),
                   lambda p:p['model'].update(reserved_input_tokens_per_request=1),
                   lambda p:p['model'].update(min_interval_seconds=.09),lambda p:p.update(timeout_seconds=31),
                   lambda p:p.update(revision='main'),lambda p:p.update(capabilities=['mcps.document-plan']),
                   lambda p:p['model'].update(key='never allowed')]
        for change in changes:
            value=deepcopy(self.profile);change(value)
            with self.subTest(value=value), self.assertRaises(JevProfileError): validate_model_profile(value)

    def test_missing_or_bad_key_never_opens_transport_or_ledger(self):
        for value, expected in (('', 'missing'),('unsafe\r\nheader','error')):
            with self.subTest(value=value),patch.dict(os.environ,{'TYPESAFE_API_KEY':value}):
                adapter=self.adapter(); result=adapter.predict(self.request())
                self.assertEqual(result['status'],expected)
                self.assertFalse(adapter.provenance['available'])
                self.assertFalse(self.ledger.exists());self.assertEqual(FakeConnection.calls,[])

    def test_success_isolated_request_and_tls_verified(self):
        adapter=self.adapter()
        self.assertFalse(self.ledger.exists());self.assertEqual(FakeConnection.calls,[])
        result=adapter.predict(self.request())
        self.assertEqual(result['status'],'ok');self.assertEqual(result['output'],{'choice_id':'opaque-second'})
        connection=FakeConnection.calls[0]
        self.assertEqual(connection.host,'api.typesafe.ai');self.assertEqual(connection.path,'/v1/systemone')
        self.assertTrue(connection.kwargs['context'].check_hostname)
        self.assertEqual(connection.kwargs['context'].verify_mode,ssl.CERT_REQUIRED)
        body=json.loads(connection.body)
        self.assertEqual(body,{'model':'jev-1.13.0','state':'Ordinary context','questions':{'answer':{
            'type':'choice','instructions':'Choose the compatible answer','criteria':{'Known':None,'Unknown':None}}}})
        self.assertEqual(list(body['questions']['answer']['criteria']),['Known','Unknown'])
        self.assertNotIn('opaque-',connection.body.decode());self.assertNotIn('SEMANTIC',connection.body.decode())
        self.assertEqual(connection.headers['Authorization'],'Bearer '+KEY)
        self.assertTrue(connection.closed);self.assertTrue(FakeConnection.response.closed)
        raw=result['raw_output'];self.assertTrue(raw['http_attempted']);self.assertFalse(raw['cached_failure'])
        self.assertEqual(raw['request_id'],'safe-id-123');self.assertEqual(raw['usage'],native()['usage'])
        self.assertEqual(raw['request_body_sha256'],hashlib.sha256(connection.body).hexdigest())
        self.assertEqual([r['kind'] for r in self.records()],['policy','reservation','settlement'])
        self.assertNotIn(KEY,json.dumps(result)+json.dumps(adapter.provenance)+self.ledger.read_text())
        self.assertNotIn('Ordinary context',self.ledger.read_text())

    def test_reservation_is_fsynced_before_sending_and_failure_keeps_it(self):
        adapter=self.adapter()
        observed=[]
        def call(_):
            records=self.records();observed.append(records[-1]['kind'])
            raise OSError(KEY+' private provider failure')
        with patch.object(adapter,'_http',side_effect=call): result=adapter.predict(self.request())
        self.assertEqual(observed,['reservation']);self.assertEqual(result['error'],'jev_http_network_error')
        self.assertEqual([r['kind'] for r in self.records()],['policy','reservation'])
        self.assertNotIn(KEY,json.dumps(result))
        cached=adapter.predict(self.request('A different input'))
        self.assertEqual(cached['raw_output'],{'http_attempted':False,'cached_failure':True,
                                            'cause_attempt_id':result['raw_output']['attempt_id']})

    def test_http_status_codes_fatal_and_never_retried(self):
        codes={401:'unauthorized',403:'forbidden',429:'rate_limited',529:'overloaded',422:'unprocessable',
               302:'status_302',500:'status_500'}
        for status,suffix in codes.items():
            with self.subTest(status=status):
                profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(self.root/f'ledger-{status}.jsonl')
                FakeConnection.response=FakeResponse({'error':KEY},status=status)
                before=len(FakeConnection.calls);adapter=self.adapter(profile)
                first=adapter.predict(self.request());second=adapter.predict(self.request())
                self.assertEqual(first['error'],'jev_http_'+suffix);self.assertEqual(second['error'],first['error'])
                self.assertEqual(len(FakeConnection.calls),before+1);self.assertNotIn(KEY,json.dumps(first))
                self.assertIsNone(first['raw_output']['native_result'])
                self.assertTrue(second['raw_output']['cached_failure'])

    def test_provider_shape_version_probabilities_and_usage_rejected(self):
        values=[]
        value=native('jev-9.9.9');values.append((value,'jev_model_version_mismatch'))
        value=native();value['answers']['answer']['choice']='Known';values.append((value,'jev_response_invalid'))
        value=native();value['answers']['answer']['probabilities']['Unknown']=.9;values.append((value,'jev_response_invalid'))
        value=native();value['answers']['answer']['confidence']=True;values.append((value,'jev_response_invalid'))
        value=native();value['usage']['input_tokens']=65537;values.append((value,'jev_usage_invalid'))
        value=native();value['usage']['output_tokens']=True;values.append((value,'jev_usage_invalid'))
        values += [(b'{"model":"x","model":"y"}','jev_response_invalid'),
                   (b'{"model":NaN}','jev_response_invalid'),
                   (b'{"extra":1e999}','jev_response_invalid'),
                   (b'{"model":"\\ud800"}','jev_response_invalid')]
        for index,(value,error) in enumerate(values):
            with self.subTest(index=index):
                profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(self.root/f'malformed-{index}.jsonl')
                FakeConnection.response=FakeResponse(value);result=self.adapter(profile).predict(self.request())
                self.assertEqual(result['error'],error)
                self.assertEqual(len(Path(profile['model']['budget_ledger']).read_text().splitlines()),2)
                self.assertEqual(result['raw_output']['native_result'], value if isinstance(value,dict) else None)
                self.assertIsNone(result['raw_output']['observed_model'])
                self.assertIsNone(result['raw_output']['usage'])

    def test_hundredth_grid_sum_tolerance_preserves_native_probabilities_and_winner(self):
        cases=[({'Known':.19,'Unknown':.8},True,'hundredth_grid'),
               ({'Known':.21,'Unknown':.8},True,'hundredth_grid'),
               ({'Known':.1,'Unknown':.8},False,'hundredth_grid'),
               ({'Known':.204,'Unknown':.786},False,'none'),
               ({'Known':.204,'Unknown':.796},True,'none')]
        for index,(probabilities,accepted,rounding) in enumerate(cases):
            with self.subTest(probabilities=probabilities):
                profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(self.root/f'rounding-{index}.jsonl')
                value=native();value['answers']['answer']['probabilities']=probabilities
                FakeConnection.response=FakeResponse(value)
                result=self.adapter(profile).predict(self.request())
                self.assertEqual(result['status'],'ok' if accepted else 'error')
                self.assertEqual(result['raw_output']['native_result'],value)
                self.assertEqual(result['raw_output']['probability_sum'],sum(probabilities.values()))
                self.assertEqual(result['raw_output']['rounding_assumption'],rounding)
                self.assertAlmostEqual(result['raw_output']['probability_sum_tolerance'],.01 if rounding=='hundredth_grid' else 1e-5)
                records=Path(profile['model']['budget_ledger']).read_text().splitlines()
                self.assertEqual(len(records),3 if accepted else 2)
                if accepted:
                    self.assertEqual(result['output'],{'choice_id':'opaque-second'})
                else:
                    self.assertEqual(result['error'],'jev_response_invalid')
                    self.assertIsNone(result['output'])

    def test_four_option_rounding_and_argmax_are_independent(self):
        request=self.request();request['input']['options']=[{'id':str(i),'description':str(i)} for i in range(4)]
        value=native();value['answers']['answer'].update(choice='3',probabilities={'0':.01,'1':0.0,'2':.05,'3':.93})
        FakeConnection.response=FakeResponse(value);result=self.adapter().predict(request)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['output'],{'choice_id':'3'})
        self.assertAlmostEqual(result['raw_output']['probability_sum'],.99)
        self.assertAlmostEqual(result['raw_output']['probability_sum_tolerance'],.02)
        profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(self.root/'wrong-rounded-winner.jsonl')
        value['answers']['answer']['choice']='2';FakeConnection.response=FakeResponse(value)
        result=self.adapter(profile).predict(request)
        self.assertEqual(result['error'],'jev_response_invalid');self.assertEqual(result['raw_output']['native_result'],value)
        self.assertEqual(len(Path(profile['model']['budget_ledger']).read_text().splitlines()),2)

    def test_argmax_accepts_only_machine_roundoff_not_a_lower_probability(self):
        request=self.request()
        request['input']['options']=[{'id':str(i),'description':str(i)} for i in range(4)]
        for index,(chosen,accepted) in enumerate(((.45999999999999996,True),
                                                 (.46-1e-10,False),(.45,False))):
            with self.subTest(chosen=chosen):
                profile=deepcopy(self.profile)
                profile['model']['budget_ledger']=str(self.root/f'argmax-ulp-{index}.jsonl')
                value=native()
                value['answers']['answer'].update(choice='2',probabilities={
                    '0':.46,'1':.02,'2':chosen,'3':.06})
                FakeConnection.response=FakeResponse(value)
                result=self.adapter(profile).predict(request)
                self.assertEqual(result['status'],'ok' if accepted else 'error')
                self.assertEqual(result['raw_output']['native_result'],value)
                self.assertEqual(len(Path(profile['model']['budget_ledger']).read_text().splitlines()),
                                 3 if accepted else 2)
                if accepted:self.assertEqual(result['output'],{'choice_id':'2'})
                else:self.assertEqual(result['error'],'jev_response_invalid')

    def test_malformed_native_secret_is_rejected_before_retention(self):
        FakeConnection.response=FakeResponse({'invalid':{'provider_echo':KEY}})
        result=self.adapter().predict(self.request())
        self.assertEqual(result['error'],'jev_response_secret_rejected')
        self.assertIsNone(result['raw_output']['native_result'])
        self.assertNotIn(KEY,json.dumps(result));self.assertEqual(len(self.records()),2)

    def test_response_secret_and_request_id_injection_never_archived(self):
        value=native();value['model']=KEY
        FakeConnection.response=FakeResponse(value,headers={'x-typesafe-request-id':KEY})
        result=self.adapter().predict(self.request());self.assertNotIn(KEY,json.dumps(result))
        self.assertEqual(result['error'],'jev_response_secret_rejected')
        self.assertIsNone(result['raw_output'])

    def test_legitimate_body_overflow_and_annotations_do_not_consume_budget(self):
        adapter=self.adapter()
        result=adapter.predict(self.request('x'*131072))
        self.assertEqual(result['status'],'unsupported');self.assertFalse(self.ledger.exists())
        request=self.request();request['input']['reference']={'gold':'private'}
        self.assertEqual(adapter.predict(request)['error'],'jev_input_invalid')
        self.assertFalse(self.ledger.exists());self.assertEqual(FakeConnection.calls,[])
        self.assertEqual(adapter.predict(self.request(KEY))['error'],'jev_input_secret_rejected')
        self.assertFalse(self.ledger.exists())

    def test_timeout_closes_transport_keeps_reservation_and_caches(self):
        FakeConnection.request_error=TimeoutError(KEY)
        adapter=self.adapter();result=adapter.predict(self.request())
        self.assertEqual(result['status'],'timeout');self.assertEqual(result['error'],'jev_http_timeout')
        self.assertTrue(FakeConnection.calls[0].closed);self.assertEqual(len(self.records()),2)
        self.assertTrue(adapter.predict(self.request())['raw_output']['cached_failure'])
        self.assertNotIn(KEY,json.dumps(result))

    def test_response_size_and_total_read_deadline(self):
        FakeConnection.response=FakeResponse(headers={'content-length':str(module.MAX_RESPONSE_BYTES+1)})
        adapter=self.adapter();result=adapter.predict(self.request())
        self.assertEqual(result['error'],'jev_response_too_large');self.assertEqual(len(self.records()),2)
        profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(self.root/'slow.jsonl')
        profile['timeout_seconds']=.03
        response=FakeResponse()
        def slow(size): time.sleep(.015);return b'x'
        response.read1=slow;FakeConnection.response=response
        started=time.monotonic();result=self.adapter(profile).predict(self.request())
        self.assertEqual(result['status'],'timeout');self.assertLess(time.monotonic()-started,.3)
        self.assertTrue(FakeConnection.calls[-1].closed)

    def test_budget_persists_across_instances_and_settles_only_verified_usage(self):
        profile=deepcopy(self.profile);profile['model'].update(max_requests=2,max_input_tokens=65553)
        first=self.adapter(profile);self.assertEqual(first.predict(self.request())['status'],'ok')
        FakeConnection.response=FakeResponse();second=self.adapter(profile)
        self.assertEqual(second.predict(self.request())['status'],'ok')
        third=self.adapter(profile);result=third.predict(self.request())
        self.assertEqual(result['error'],'jev_request_budget_exhausted');self.assertEqual(len(FakeConnection.calls),2)
        self.assertEqual(len(self.records()),5)

    def test_failed_attempt_reserves_full_tokens_for_subsequent_instances(self):
        profile=deepcopy(self.profile);profile['model'].update(max_input_tokens=65536)
        FakeConnection.request_error=OSError('transport failed')
        self.adapter(profile).predict(self.request())
        result=self.adapter(profile).predict(self.request())
        self.assertEqual(result['error'],'jev_input_budget_exhausted');self.assertEqual(len(FakeConnection.calls),1)

    def test_policy_mismatch_symlink_and_corrupt_ledger_fail_closed(self):
        first=self.adapter();self.assertEqual(first.predict(self.request())['status'],'ok')
        profile=deepcopy(self.profile);profile['model']['max_requests']=799
        result=self.adapter(profile).predict(self.request());self.assertEqual(result['error'],'jev_budget_policy_mismatch')
        self.ledger.write_text(self.ledger.read_text()[:-1])
        result=self.adapter().predict(self.request());self.assertEqual(result['error'],'jev_budget_ledger_invalid')
        link=self.root/'linked-ledger';link.symlink_to(self.ledger)
        profile=deepcopy(self.profile);profile['model']['budget_ledger']=str(link)
        self.assertEqual(self.adapter(profile).predict(self.request())['error'],'jev_budget_path_invalid')
        self.assertEqual(len(FakeConnection.calls),1)

    def test_shared_lock_serializes_calls_and_enforces_global_interval(self):
        adapters=[self.adapter(),self.adapter()]
        active=0;maximum=0;starts=[];guard=threading.Lock();results=[]
        def transport(body):
            nonlocal active,maximum
            with guard: active+=1;maximum=max(maximum,active);starts.append(time.time())
            time.sleep(.02)
            with guard: active-=1
            return 200,None,json.dumps(native()).encode(),20
        for adapter in adapters: adapter._http=transport
        threads=[threading.Thread(target=lambda a=a:results.append(a.predict(self.request()))) for a in adapters]
        for thread in threads:thread.start()
        for thread in threads:thread.join(2);self.assertFalse(thread.is_alive())
        self.assertEqual(maximum,1);self.assertGreaterEqual(starts[1]-starts[0],.095)
        self.assertEqual([r['status'] for r in results],['ok','ok']);self.assertEqual(len(self.records()),5)

    def test_clock_rollback_and_keyboard_interrupt_preserve_reservation(self):
        first=self.adapter()
        with patch.object(first,'_http',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):first.predict(self.request())
        self.assertEqual(len(self.records()),2);self.assertTrue(first._closed)
        started=self.records()[-1]['started_at']
        second=self.adapter()
        with patch('deposium_bench.http_budget.time.time',return_value=started-1):
            result=second.predict(self.request())
        self.assertEqual(result['error'],'jev_budget_clock_invalid');self.assertEqual(len(FakeConnection.calls),0)

    def test_lock_wait_is_bounded_without_a_second_reservation(self):
        adapter=self.adapter();policy=deepcopy(adapter._policy);policy['timeout_seconds']=.04
        budget=HTTPBudget(self.ledger,policy);errors=[]
        def competing():
            try:
                with HTTPBudget(self.ledger,policy).reserve(): errors.append('unexpected reservation')
            except BudgetError as error: errors.append(str(error))
        with budget.reserve():
            started=time.monotonic();thread=threading.Thread(target=competing);thread.start();thread.join(.5)
            self.assertFalse(thread.is_alive());self.assertLess(time.monotonic()-started,.5)
            self.assertEqual(errors,['jev_budget_lock_timeout']);self.assertEqual(len(self.records()),2)

    def test_parent_inode_replacement_and_fsync_are_guarded(self):
        adapter=self.adapter();budget=adapter._budget
        actual_fsync=os.fsync
        with patch('deposium_bench.http_budget.os.fsync',wraps=actual_fsync) as sync:
            with budget.reserve() as attempt:
                self.assertGreaterEqual(sync.call_count,2)
                old=self.root/'original-results';self.ledger.parent.rename(old);self.ledger.parent.mkdir()
                os.link(old/self.ledger.name,self.ledger)
                with self.assertRaisesRegex(BudgetError,'jev_budget_ledger_changed'):
                    attempt.settle({'input_tokens':17,'output_tokens':2})
        self.assertEqual(len(self.records()),2)

    def test_unadvertised_response_body_is_bounded(self):
        FakeConnection.response=FakeResponse(b'x'*(module.MAX_RESPONSE_BYTES+1))
        result=self.adapter().predict(self.request())
        self.assertEqual(result['error'],'jev_response_too_large')
        self.assertTrue(FakeConnection.calls[0].closed);self.assertEqual(len(self.records()),2)

    def test_identity_excludes_ledger_and_credential_values_and_guards_sources(self):
        first=self.adapter();profile=deepcopy(self.profile);profile['model']['budget_ledger']='other.jsonl'
        with patch.dict(os.environ,{'TYPESAFE_API_KEY':'another-offline-secret'}):second=self.adapter(profile)
        self.assertEqual(first.provenance['identity_sha256'],second.provenance['identity_sha256'])
        with patch.object(module,'_stat',return_value=('changed',)):
            result=first.predict(self.request())
        self.assertEqual(result['error'],'jev_source_changed');self.assertFalse(self.ledger.exists())
        second.close();self.assertEqual(second.predict(self.request())['error'],'jev_adapter_closed')


if __name__ == '__main__': unittest.main()
