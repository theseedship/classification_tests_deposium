"""Bounded GLiNER parent transport using a tiny fake worker, no models/services."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from deposium_bench import gliner_adapter as adapter_module
from deposium_bench.gliner_adapter import (GLiNERAdapter, GLiNERProfileError,
                                          GLINER_CHOICE_PROMPT, _lock_pins, validate_model_profile)

REVISION = "a35a0cd3b7a0f00f2effc576f454cd48fa98aa5f"

FAKE_WORKER = r'''import hashlib,json,os,sys,time
from pathlib import Path
CAPTURE=Path(__CAPTURE__)
def emit(x): print(json.dumps(x),flush=True)
request=json.loads(sys.stdin.readline())
config=request['config']
runtime_root=CAPTURE.parent/'runtime'
sources={p.relative_to(runtime_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted((runtime_root/'gliner2').rglob('*.py'))}
sources_digest=hashlib.sha256(json.dumps(sources,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
packages={x:'1.0.test' for x in ('torch','transformers','tokenizers','numpy','gliner2','dependency')}
packages.update(config.get('fake_packages',{}))
CAPTURE.write_text(json.dumps({'config':config,'environment':dict(os.environ),'rows':[]}))
emit({'status':'ready','runtime':{'python':'fixture',**{x:packages[x] for x in packages if x!='dependency'}},
      'runtime_packages':packages,'runtime_sources':sources,'runtime_sources_root':str(runtime_root.resolve()),
      'runtime_sources_sha256':sources_digest,'load_ms':1,'rss_mb':1})
for line in sys.stdin:
 request=json.loads(line);v=request['input'];context=v['context'];ids=[o['id'] for o in v['options']]
 capture=json.loads(CAPTURE.read_text());capture['rows'].append({'text':context,'prompt':v['question'],
      'labels':[o['description'] for o in v['options']]});CAPTURE.write_text(json.dumps(capture))
 if context=='delay': time.sleep(2)
 if context=='oversize': emit({'garbage':'x'*(2*1024*1024)});continue
 if context=='spawn':
  import subprocess
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
  capture['child_pid']=child.pid;CAPTURE.write_text(json.dumps(capture));time.sleep(2)
 if context=='oom': memory=bytearray(180*1024*1024);time.sleep(.3)
 if context=='raise':
  emit({'sequence':request['sequence'],'status':'error','output':None,'raw_output':None,'error':'gliner_inference_failed'});continue
 model_text=context if context.endswith(('.', '!', '?')) else context+'.'
 overflow=context=='overflow';tokens=4097 if overflow else 50
 winner=next((o for o in v['options'] if o['description']=='Unknown'),v['options'][0])
 raw={'native_result':None if overflow else {'answer':{'label':winner['description'],'confidence':.7}},
      'ordered_ids':ids,'input_sha256':hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
      'model_text_sha256':hashlib.sha256(model_text.encode()).hexdigest(),
      'preprocessing':{'appended_punctuation':model_text!=context,'lowercase':True},
      'decision_ms':2,'inference_ms':None if overflow else 1,'rss_mb':1,
      'encoding_info':{'tokens':tokens,'stateTruncated':False,'optionsTruncated':False},
      'token_components':{'schema_tokens':20,'content_tokens':tokens-20,'total_tokens':tokens,'padded_tokens':tokens,'content_words':len(context.split())},
      'forward_executed':not overflow}
 emit({'sequence':request['sequence'],'status':'unsupported' if overflow else 'ok',
       'output':None if overflow else {'choice_id':winner['id']},'raw_output':raw,
       'error':'gliner_context_overflow' if overflow else None})
'''


class GLiNERAdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / 'model'
        self.model.mkdir()
        (self.model / 'config.json').write_text('{}')
        self.capture = self.root / 'capture.json'
        self.runtime = self.root / 'runtime'
        package = self.runtime / 'gliner2'
        (package / 'models/boundary').mkdir(parents=True)
        (package / 'auto.py').write_text('fixture=1\n')
        (package / 'models/boundary/model.py').write_text('fixture=1\n')
        self.worker = self.root / 'worker.py'
        self.worker.write_text(FAKE_WORKER.replace('__CAPTURE__', repr(str(self.capture))))
        self.assets = self.root / 'assets.json'
        self.write_manifest()
        self.prompt = self.root / 'prompt.json'
        self.prompt.write_text(json.dumps(GLINER_CHOICE_PROMPT))
        self.lock = self.root / 'runtime.lock'
        self.lock.write_text(''.join(name+'==1.0.test\n' for name in
                                    ('torch','transformers','tokenizers','numpy','gliner2','dependency')))
        self.profile_path = self.root / 'profile.json'
        self.profile = {'schema_version':'deposium.candidate/v1','profile_id':'offline-gliner',
                        'adapter':'gliner','qualification':'model_isolated','capabilities':['bench.context-choice'],
                        'revision':REVISION,'timeout_seconds':2,'recordings':None,
                        'model':{'repo_id':'fastino/GLiNER2.5-multi-Decide','local_dir':'model',
                                 'runtime_python':sys.executable,'assets_manifest':'assets.json',
                                 'prompt_path':'prompt.json','runtime_lock':'runtime.lock',
                                 'max_length':4096,'threads':2,'max_rss_mb':3072}}
        self.profile_path.write_text(json.dumps(self.profile))
        replacement = patch.object(adapter_module, 'WORKER', self.worker)
        replacement.start()
        self.addCleanup(replacement.stop)

    def write_manifest(self):
        files = [{'path':p.relative_to(self.model).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                  'size':p.stat().st_size} for p in sorted(self.model.rglob('*')) if p.is_file()]
        self.assets.write_text(json.dumps({'schema_version':'deposium.model-assets/v1',
                                          'repo_id':'fastino/GLiNER2.5-multi-Decide',
                                          'revision':REVISION,'files':files}))

    def adapter(self):
        adapter = GLiNERAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        return adapter

    def request(self, context='ordinary'):
        return {'case_id':'semantic-gold-must-not-leak','contract_id':'bench.context-choice',
                'input':{'context':context,'question':'Select the compatible choice',
                         'options':[{'id':'catalog','description':'Known'},
                                    {'id':'abstain','description':'Unknown'}]}}

    def test_profile_syntax_and_resources_are_bounded_without_io(self):
        validate_model_profile(self.profile)
        mutations = [lambda p:p.update(capabilities=['mcps.document-plan']),lambda p:p.update(revision='main'),
                     lambda p:p.update(recordings='file'),lambda p:p.update(timeout_seconds=float('inf')),
                     lambda p:p['model'].update(max_length=4097),lambda p:p['model'].update(threads=True),
                     lambda p:p['model'].update(threads=5),lambda p:p['model'].update(max_rss_mb=3073),
                     lambda p:p['model'].update(head_length=512),lambda p:p['model'].update(repo_id='other')]
        for mutate in mutations:
            profile=deepcopy(self.profile);mutate(profile)
            with self.subTest(profile=profile), self.assertRaises(GLiNERProfileError):
                validate_model_profile(profile)

    def test_success_unknown_label_ids_hidden_and_cpu_environment(self):
        adapter=self.adapter();self.assertTrue(adapter.provenance['available'])
        response=adapter.predict(self.request())
        self.assertEqual(response['status'],'ok');self.assertEqual(response['output'],{'choice_id':'abstain'})
        capture=json.loads(self.capture.read_text())
        self.assertEqual(capture['rows'][0],{'text':'ordinary','prompt':'Select the compatible choice','labels':['Known','Unknown']})
        self.assertNotIn('semantic-gold',json.dumps(capture['config']))
        self.assertEqual(capture['environment']['HF_HUB_OFFLINE'],'1')
        self.assertEqual(capture['environment']['CUDA_VISIBLE_DEVICES'],'')
        self.assertTrue(adapter.provenance['runtime_lock_verified'])
        self.assertIn('dependency',adapter.provenance['runtime_packages'])
        self.assertEqual(adapter.provenance['prompt'],GLINER_CHOICE_PROMPT)
        self.assertNotIn('logits',response['raw_output'])

    def test_overflow_has_audit_before_forward_and_worker_remains_usable(self):
        adapter=self.adapter();pid=adapter._process.pid
        response=adapter.predict(self.request('overflow'))
        self.assertEqual((response['status'],response['error']),('unsupported','gliner_context_overflow'))
        self.assertIs(response['raw_output']['forward_executed'],False)
        self.assertIsNone(response['raw_output']['inference_ms'])
        self.assertEqual(adapter.predict(self.request())['status'],'ok')
        self.assertEqual(adapter._process.pid,pid)

    def test_every_lock_pin_is_verified_including_transitive_dependencies(self):
        self.lock.write_text(self.lock.read_text().replace('dependency==1.0.test','dependency==2.0.test'))
        adapter=self.adapter()
        self.assertFalse(adapter.provenance['available'])
        self.assertEqual(adapter.predict(self.request())['error'],'gliner_runtime_lock_mismatch')
        self.assertIsNone(adapter._process)

    def test_uv_hashed_lock_and_cpu_direct_wheel_version(self):
        text=self.lock.read_text().replace('torch==1.0.test',
            'torch @ https://download.pytorch.org/whl/cpu/torch-1.0.test-cp312-cp312-manylinux_x86_64.whl#sha256=abc')
        self.assertEqual(_lock_pins(text)['torch'],'1.0.test')
        text=text.replace('numpy==1.0.test','numpy==1.0.test \\\n    --hash=sha256:abc \\\n    --hash=sha256:def')
        self.assertEqual(_lock_pins(text)['numpy'],'1.0.test')
        for invalid in (text+'\nnumpy==2\n',text.replace('gliner2==1.0.test','gliner2>=1'),
                        text.replace('gliner2==1.0.test',''),text.replace('torch-1.0.test','other-1.0.test')):
            with self.assertRaises(ValueError):_lock_pins(invalid)

    def test_exhaustive_assets_mismatch_and_escaping_symlink_fail_initialization(self):
        (self.model/'unlisted').write_text('changed')
        self.assertEqual(self.adapter().provenance['availability_error'],'gliner_initialization_invalid')
        self.write_manifest();(self.model/'config.json').write_text('different')
        self.assertEqual(self.adapter().provenance['availability_error'],'gliner_initialization_invalid')
        (self.model/'escape').symlink_to(self.lock)
        self.assertEqual(self.adapter().provenance['availability_error'],'gliner_initialization_invalid')

    def test_assets_prompt_lock_worker_and_helper_drift_close_before_request(self):
        for target in (self.model/'config.json',self.prompt,self.lock,self.worker,self.runtime/'gliner2/auto.py'):
            before=target.read_bytes();adapter=self.adapter();self.assertTrue(adapter.provenance['available'])
            target.write_bytes(before+b' ')
            self.assertEqual(adapter.predict(self.request())['error'],'gliner_runtime_or_protocol_changed')
            self.assertIsNone(adapter._process)
            target.write_bytes(before)
        helper=self.root/'choice.py';helper.write_text('marker=1\n')
        with patch.object(adapter_module,'CHOICE_PROTOCOL',helper):
            adapter=self.adapter();helper.write_text('marker=2\n')
            self.assertEqual(adapter.predict(self.request())['status'],'error')

    def test_new_runtime_source_or_retargeted_model_root_is_rejected(self):
        adapter=self.adapter()
        (self.runtime/'gliner2/new.py').write_text('unexpected=1\n')
        self.assertEqual(adapter.predict(self.request())['status'],'error')
        (self.runtime/'gliner2/new.py').unlink()
        original=self.model
        alias=self.root/'model-link';alias.symlink_to(original,target_is_directory=True)
        self.profile['model']['local_dir']='model-link'
        adapter=self.adapter()
        other=self.root/'other';other.mkdir();(other/'config.json').write_bytes((original/'config.json').read_bytes())
        alias.unlink();alias.symlink_to(other,target_is_directory=True)
        self.assertEqual(adapter.predict(self.request())['status'],'error')

    def test_generic_error_can_retain_actual_audit_without_inventing_scores(self):
        adapter=self.adapter();good=adapter.predict(self.request())
        response={'sequence':adapter._sequence,**good}
        response.update(status='error',output=None,error='gliner_inference_failed')
        response['raw_output']['native_result']=None
        adapter._audit_response(response,self.request()['input'])
        response['raw_output'].update(forward_executed=False,inference_ms=None)
        adapter._audit_response(response,self.request()['input'])

    def test_annotations_and_duplicate_options_never_reach_worker(self):
        adapter=self.adapter()
        for change in (lambda v:v.update(reference='gold'),lambda v:v['options'].append(v['options'][0])):
            request=self.request();change(request['input'])
            with self.assertRaises(ValueError):adapter.predict(request)
        self.assertEqual(json.loads(self.capture.read_text())['rows'],[])

    def test_timeout_and_close_reap_process(self):
        self.profile['timeout_seconds']=.08;adapter=self.adapter();process=adapter._process
        response=adapter.predict(self.request('delay'))
        self.assertEqual((response['status'],response['error']),('timeout','gliner_inference_timeout'))
        self.assertIsNotNone(process.poll());self.assertIsNone(adapter._process);adapter.close()

    def test_timeout_cleans_process_group_descendants(self):
        self.profile['timeout_seconds']=.15;adapter=self.adapter()
        response=adapter.predict(self.request('spawn'))
        self.assertEqual(response['status'],'timeout')
        child=json.loads(self.capture.read_text())['child_pid']
        self.addCleanup(lambda: self._kill_if_running(child))
        deadline=time.monotonic()+1
        while self._running(child) and time.monotonic()<deadline:
            time.sleep(.01)
        self.assertFalse(self._running(child))

    @staticmethod
    def _running(pid):
        path=Path(f'/proc/{pid}/stat')
        return path.exists() and path.read_text().split()[2]!='Z'

    @staticmethod
    def _kill_if_running(pid):
        if GLiNERAdapterTests._running(pid):
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass

    def test_bounded_protocol_rejects_oversize_input_or_worker_output(self):
        adapter=self.adapter()
        response=adapter.predict(self.request('oversize'))
        self.assertEqual(response['error'],'gliner_runtime_or_protocol_changed')
        self.assertIsNone(adapter._process)
        adapter=self.adapter()
        response=adapter.predict(self.request('x'*(1024*1024)))
        self.assertEqual(response['status'],'error');self.assertIsNone(adapter._process)

    def test_memory_guard_observes_worker_and_reaps_it(self):
        self.profile['model']['max_rss_mb']=64;adapter=self.adapter();process=adapter._process
        self.assertTrue(adapter.provenance['available'])
        response=adapter.predict(self.request('oom'))
        self.assertEqual(response['error'],'gliner_rss_limit');self.assertIsNotNone(process.poll())

    def test_malformed_audits_are_rejected(self):
        adapter=self.adapter()
        good=adapter.predict(self.request())
        response={'sequence':adapter._sequence,**good}
        changes=[lambda r:r['raw_output']['encoding_info'].update(stateTruncated=True),
                 lambda r:r['raw_output']['token_components'].update(total_tokens=99),
                 lambda r:r['raw_output']['native_result']['answer'].update(confidence=2),
                 lambda r:r['raw_output']['native_result']['answer'].update(label='not an option'),
                 lambda r:r['raw_output'].update(forward_executed=False),
                 lambda r:r['raw_output'].update(model_text_sha256='0'*64),
                 lambda r:r.update(sequence=999),lambda r:r.update(error='secret')]
        for change in changes:
            result=deepcopy(response);change(result)
            with self.subTest(result=result),self.assertRaises(ValueError):
                adapter._audit_response(result,self.request()['input'])

    def test_missing_files_initialization_timeout_and_interruption_are_distinct(self):
        missing=deepcopy(self.profile);missing['model']['assets_manifest']='missing'
        adapter=GLiNERAdapter(missing,self.profile_path);self.addCleanup(adapter.close)
        self.assertEqual(adapter.predict(self.request())['status'],'missing')
        self.worker.write_text('import time\ntime.sleep(2)\n')
        with patch.object(adapter_module,'INITIALIZATION_SECONDS',.08):
            adapter=self.adapter()
        self.assertEqual(adapter.predict(self.request())['error'],'gliner_initialization_timeout')
        self.worker.write_text(FAKE_WORKER.replace('__CAPTURE__',repr(str(self.capture))))
        adapter=self.adapter();process=adapter._process
        with patch.object(adapter,'_exchange',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            adapter.predict(self.request())
        self.assertIsNotNone(process.poll())

    def test_errors_redacted_and_unsupported_contract_never_calls_worker(self):
        adapter=self.adapter()
        request=self.request();request['contract_id']='mcps.document-plan'
        self.assertEqual(adapter.predict(request)['status'],'unsupported')
        self.assertEqual(json.loads(self.capture.read_text())['rows'],[])
        response=adapter.predict(self.request('raise'))
        self.assertEqual(response['error'],'gliner_inference_failed');self.assertIsNone(response['raw_output'])
        self.assertEqual(adapter.predict(self.request())['status'],'ok')
