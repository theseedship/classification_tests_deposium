"""Offline Indecis admission, archival identity and resident process guards."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import indecis_adapter as module
from deposium_bench.indecis_adapter import IndecisAdapter, IndecisProfileError, validate_model_profile, INDECIS_CHOICE_PROMPT

FAKE_WORKER = r'''#!/usr/bin/env python3
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
CAPTURE=Path(__CAPTURE__)
def emit(value): print(json.dumps(value),flush=True)
request=json.loads(sys.stdin.readline());config=request['config']
CAPTURE.write_text(json.dumps({'config':config,'environment':dict(os.environ),'rows':[]}))
binary_hash=hashlib.sha256(Path(sys.argv[0]).read_bytes()).hexdigest()
runtime={'go':'go1.27.1-X:simd','goos':'linux','goarch':'amd64','indecis_revision':config['source_revision'],'backbone_revision':config['revision']}
emit({'status':'ready','runtime':runtime,'binary_sha256':binary_hash,'load_ms':1,'rss_mb':1})
for line in sys.stdin:
 request=json.loads(line);v=request['input'];context=v['context'];options=v['options'];ids=[o['id'] for o in options]
 capture=json.loads(CAPTURE.read_text());capture['rows'].append({'state':context,'option_texts':[o['description']+'\n'+v['question'] for o in options]});CAPTURE.write_text(json.dumps(capture))
 if context=='delay': time.sleep(2)
 if context=='huge-output': emit({'garbage':'x'*(2*1024*1024)});continue
 if context=='spawn':
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
  capture['child_pid']=child.pid;CAPTURE.write_text(json.dumps(capture));time.sleep(2)
 if context=='oom': memory=bytearray(180*1024*1024);time.sleep(.3)
 if context in ('raise','invalid-output'):
  emit({'sequence':request['sequence'],'status':'error','output':None,'raw_output':None,'error':'indecis_inference_failed' if context=='raise' else 'indecis_output_invalid'});continue
 context_tokens=4097 if context=='context-overflow' else 12
 option_tokens=[4097 if context=='option-overflow' else 8 for o in options]
 tokens=max([context_tokens,*option_tokens]);overflow=tokens>config['max_length'];winner=len(options)-1
 probabilities=[.2/(len(options)-1)]*(len(options)-1)+[.8]
 native={'question':'answer','kind':'choice','choice':options[winner]['description'],'confidence':.8,
         'probs':dict(zip([o['description'] for o in options],probabilities)),'score':.6,'margin':.6}
 raw={'native_result':None if overflow else native,'ordered_ids':ids,'probabilities':None if overflow else native['probs'],
      'input_sha256':hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
      'decision_ms':2,'inference_ms':None if overflow else 1,'rss_mb':1,
      'encoding_info':{'tokens':tokens,'stateTruncated':False,'optionsTruncated':False},
      'token_components':{'context_tokens':context_tokens,'option_tokens':option_tokens,'total_tokens':context_tokens+sum(option_tokens),'max_sequence_tokens':tokens},
      'forward_executed':not overflow}
 if context=='bad-hash': raw['input_sha256']='0'*64
 if context=='wrong-winner': native['choice']=options[0]['description']
 if context=='bad-components': raw['token_components']['total_tokens']+=1
 if context=='truncated': raw['encoding_info']['stateTruncated']=True
 if context=='bad-forward': raw['forward_executed']=False
 emit({'sequence':request['sequence'],'status':'unsupported' if overflow else 'ok',
       'output':None if overflow else {'choice_id':ids[winner]},'raw_output':raw,
       'error':('indecis_context_overflow' if context_tokens>config['max_length'] else 'indecis_option_overflow') if overflow else None})
'''


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


class IndecisAdapterTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.capture=self.root/'capture.json';self.model=self.root/'model';self.model.mkdir()
        for name in ('config.json','model.safetensors','tokenizer.json'):(self.model/name).write_text('{}')
        (self.model/'.cache/huggingface').mkdir(parents=True);(self.model/'.cache/huggingface/download-metadata').write_text('metadata')
        self.source=self.root/'source';self.source.mkdir()
        for name in ('go.mod','model.go','decide_open.go','open.go','LICENSE'):(self.source/name).write_text('fixture=1\n')
        (self.source/'.git').mkdir();(self.source/'.git/HEAD').write_text('ref: refs/heads/main\n')
        (self.source/'README.md').write_text('not runtime code')
        self.worker_source=self.root/'worker-source';self.worker_source.mkdir()
        for name in ('main.go','main_test.go','go.mod'):(self.worker_source/name).write_text('fixture=1\n')
        # Use the test interpreter without relying on the worker's restricted PATH.
        worker=FAKE_WORKER.replace('#!/usr/bin/env python3','#!'+sys.executable,1)
        self.binary=self.root/'indecis-worker';self.binary.write_text(worker.replace('__CAPTURE__',repr(str(self.capture))));self.binary.chmod(0o755)
        self.assets=self.root/'assets.json';self.sources=self.root/'sources.json';self.prompt=self.root/'prompt.json';self.build=self.root/'build.json'
        self.prompt.write_text(json.dumps(INDECIS_CHOICE_PROMPT));self.write_manifests()
        self.profile_path=self.root/'profile.json'
        self.profile={'schema_version':'deposium.candidate/v1','profile_id':'offline-indecis','adapter':'indecis',
                      'qualification':'model_isolated','capabilities':['bench.context-choice'],'revision':module.BACKBONE_REVISION,
                      'recordings':None,'timeout_seconds':.3,'model':{'repo_id':module.BACKBONE_REPO,'local_dir':'model',
                          'assets_manifest':'assets.json','prompt_path':'prompt.json','source_dir':'source','source_manifest':'sources.json',
                          'source_revision':module.SOURCE_REVISION,'worker_binary':'indecis-worker','build_manifest':'build.json',
                          'max_length':4096,'threads':2,'max_rss_mb':3072}}
        self.profile_path.write_text(json.dumps(self.profile))
        replacement=patch.object(module,'WORKER_SOURCE',self.worker_source/'main.go');replacement.start();self.addCleanup(replacement.stop)

    def write_manifests(self):
        assets=[{'path':p.name,'sha256':sha(p),'size':p.stat().st_size} for p in sorted(self.model.iterdir()) if p.is_file()]
        self.assets.write_text(json.dumps({'schema_version':'deposium.model-assets/v1','repo_id':module.BACKBONE_REPO,
                                         'revision':module.BACKBONE_REVISION,'files':assets}))
        sources=[{'path':p.name,'sha256':sha(p),'size':p.stat().st_size} for p in sorted(self.source.iterdir())
                 if p.is_file() and p.name!='README.md']
        self.sources.write_text(json.dumps({'schema_version':'deposium.indecis-source/v1','repo_id':module.SOURCE_REPO,
                                           'revision':module.SOURCE_REVISION,'files':sources,'total_bytes':sum(p['size'] for p in sources)}))
        source_hash=compact_sha({name:sha(self.worker_source/name) for name in ('main.go','main_test.go','go.mod')})
        self.build.write_text(json.dumps({'schema_version':'deposium.indecis-build/v1','source_revision':module.SOURCE_REVISION,
                  'source_manifest_sha256':sha(self.sources),'worker_source_sha256':source_hash,'binary_sha256':sha(self.binary),
                  'go_version':'go1.27.1-X:simd','build_flags':['-p','2','-trimpath','-buildvcs=false'],
                  'go_env':{'GOOS':'linux','GOARCH':'amd64','CGO_ENABLED':'0','GOTOOLCHAIN':'local',
                            'GOEXPERIMENT':'simd','GOPROXY':'off','GOSUMDB':'off'}}))

    def adapter(self, profile=None):
        value=IndecisAdapter(profile or self.profile,self.profile_path);self.addCleanup(value.close);return value
    def request(self, context='ordinary'):
        return {'case_id':'GOLD_SEMANTIC_DO_NOT_LEAK','contract_id':'bench.context-choice',
                'input':{'context':context,'question':'Choose the compatible answer',
                         'options':[{'id':'catalog','description':'Known'},{'id':'abstain','description':'Unknown'}]}}

    def test_profile_pinned_and_bounded_without_runtime(self):
        validate_model_profile(self.profile)
        changes=[lambda p:p.update(revision='main'),lambda p:p['model'].update(source_revision='0'*40),
                 lambda p:p['model'].update(max_length=4097),lambda p:p['model'].update(threads=5),
                 lambda p:p['model'].update(max_rss_mb=3073),lambda p:p.update(timeout_seconds=31),
                 lambda p:p['model'].update(threads=True),lambda p:p.update(recordings='fixture'),
                 lambda p:p['model'].update(repo_id='different'),lambda p:p['model'].update(extra='unexpected')]
        for change in changes:
            value=deepcopy(self.profile);change(value)
            with self.subTest(value=value),self.assertRaises(IndecisProfileError):validate_model_profile(value)
        self.assertFalse(self.capture.exists())

    def test_missing_runtime_is_distinct_and_never_starts_process(self):
        self.binary.unlink()
        with patch.object(module.subprocess,'Popen') as start:
            adapter=self.adapter();result=adapter.predict(self.request())
        start.assert_not_called();self.assertEqual(result['status'],'missing')
        self.assertEqual(result['error'],'indecis_assets_or_runtime_missing');self.assertFalse(adapter.provenance['available'])
        self.assertNotIn('runtime',adapter.provenance);self.assertNotIn('load_ms',adapter.provenance)
        self.assertEqual(result['raw_output'],{'forward_executed':False,'cached_failure':True})

    def test_success_uses_native_open_schema_and_inert_metadata(self):
        with patch.dict(os.environ,{'TYPESAFE_API_KEY':'secret-not-in-worker','OTHER_TOKEN':'private'}):adapter=self.adapter()
        self.assertTrue(adapter.provenance['available']);self.assertEqual(adapter.provenance['runtime']['go'],'go1.27.1-X:simd')
        result=adapter.predict(self.request());self.assertEqual(result['status'],'ok')
        self.assertEqual(result['output'],{'choice_id':'abstain'})
        captured=json.loads(self.capture.read_text())
        self.assertEqual(captured['rows'],[{'state':'ordinary','option_texts':['Known\nChoose the compatible answer','Unknown\nChoose the compatible answer']}])
        self.assertNotIn('GOLD',json.dumps(captured));self.assertNotIn('catalog',json.dumps(captured['rows']))
        self.assertNotIn('TYPESAFE_API_KEY',captured['environment']);self.assertNotIn('OTHER_TOKEN',captured['environment'])
        raw=result['raw_output'];self.assertEqual(raw['encoding_info']['tokens'],12)
        self.assertEqual(raw['token_components']['total_tokens'],28)
        self.assertEqual(raw['token_components']['max_sequence_tokens'],12)
        self.assertNotIn('padded',raw['token_components']);self.assertTrue(raw['forward_executed'])
        self.assertEqual(set(adapter.provenance['helper_sha256']),{'julia_adapter.py','cases.py','choice_protocol.py'})
        self.assertEqual(adapter.provenance['prompt'],INDECIS_CHOICE_PROMPT)
        self.assertEqual(adapter.provenance['assets_manifest']['revision'],module.BACKBONE_REVISION)

    def test_overflow_never_forwards_and_keeps_worker_usable(self):
        adapter=self.adapter()
        for context,error in (('context-overflow','indecis_context_overflow'),('option-overflow','indecis_option_overflow')):
            with self.subTest(context=context):
                result=adapter.predict(self.request(context));self.assertEqual(result['status'],'unsupported')
                self.assertEqual(result['error'],error);self.assertFalse(result['raw_output']['forward_executed'])
                self.assertIsNone(result['raw_output']['inference_ms']);self.assertIsNone(result['raw_output']['native_result'])
                self.assertIsNotNone(adapter._process)
        self.assertEqual(adapter.predict(self.request())['status'],'ok')

    def test_input_admission_rejects_annotations_duplicates_and_transport_overflow(self):
        adapter=self.adapter()
        request=self.request();request['input']['reference']={'gold':'private'}
        self.assertEqual(adapter.predict(request)['error'],'indecis_input_invalid')
        request=self.request();request['input']['options'][1]['description']='Known'
        self.assertEqual(adapter.predict(request)['error'],'indecis_input_invalid')
        self.assertEqual(adapter.predict(self.request('x'*(2*1024*1024)))['status'],'unsupported')
        self.assertEqual(json.loads(self.capture.read_text())['rows'],[])
        self.assertEqual(adapter.predict({'contract_id':'other'})['error'],'unsupported_contract')
        self.assertEqual(adapter.predict(self.request('\ud800'))['error'],'indecis_input_invalid')

    def test_artifact_hash_and_build_pin_refusals_before_spawn(self):
        for name in ('assets','sources','build','prompt'):
            with self.subTest(name=name):
                path=getattr(self,name);original=path.read_bytes();value=json.loads(original)
                if name=='assets':value['files'][0]['sha256']='0'*64
                elif name=='sources':value['revision']='0'*40
                elif name=='build':value['go_env']['CGO_ENABLED']='1'
                else:value['option_serialization']='question_newline_description'
                path.write_text(json.dumps(value))
                with patch.object(module.subprocess,'Popen') as start:adapter=self.adapter()
                start.assert_not_called();self.assertFalse(adapter.provenance['available'])
                self.assertEqual(adapter.predict(self.request())['error'],'indecis_initialization_invalid')
                path.write_bytes(original)

    def test_go_version_and_experiment_must_agree_before_spawn(self):
        build=json.loads(self.build.read_text());build['go_env']['GOEXPERIMENT']=''
        self.build.write_text(json.dumps(build))
        with patch.object(module.subprocess,'Popen') as start:adapter=self.adapter()
        start.assert_not_called();self.assertEqual(adapter.predict(self.request())['error'],'indecis_initialization_invalid')

    def test_base_go_build_is_refused_without_qualifying_a_fallback(self):
        build=json.loads(self.build.read_text());build['go_version']='go1.27.1';build['go_env']['GOEXPERIMENT']=''
        self.build.write_text(json.dumps(build))
        with patch.object(module.subprocess,'Popen') as start:adapter=self.adapter()
        start.assert_not_called();self.assertFalse(adapter.provenance['available'])
        self.assertEqual(adapter.predict(self.request())['error'],'indecis_initialization_invalid')

    def test_symlink_escape_and_unlisted_source_are_refused(self):
        (self.model/'tokenizer.json').unlink();(self.model/'tokenizer.json').symlink_to(self.prompt)
        self.assertEqual(self.adapter().predict(self.request())['error'],'indecis_initialization_invalid')
        (self.model/'tokenizer.json').unlink();(self.model/'tokenizer.json').write_text('{}')
        (self.source/'unlisted.go').write_text('unexpected runtime source')
        self.assertEqual(self.adapter().predict(self.request())['error'],'indecis_initialization_invalid')
        self.assertFalse(self.capture.exists())

    def test_model_binary_source_and_prompt_drift_stop_worker(self):
        for name,path in (('model',self.model/'config.json'),('source',self.source/'model.go'),
                          ('binary',self.binary),('prompt',self.prompt),('worker',self.worker_source/'main.go')):
            with self.subTest(name=name):
                adapter=self.adapter();self.assertTrue(adapter.provenance['available']);original=path.read_bytes()
                path.write_bytes(original+b' ')
                result=adapter.predict(self.request());self.assertEqual(result['error'],'indecis_runtime_or_protocol_changed')
                self.assertIsNone(adapter._process)
                self.assertEqual(adapter.predict(self.request())['raw_output'],{'forward_executed':False,'cached_failure':True})
                path.write_bytes(original)

    def test_protocol_shape_hash_forward_tokens_and_winner_are_audited(self):
        for context in ('bad-hash','wrong-winner','bad-components','truncated','bad-forward','huge-output'):
            with self.subTest(context=context):
                adapter=self.adapter();result=adapter.predict(self.request(context))
                self.assertEqual(result['error'],'indecis_runtime_or_protocol_changed');self.assertIsNone(adapter._process)

    def test_native_error_is_fatal_and_cached_without_repeated_cost(self):
        adapter=self.adapter();result=adapter.predict(self.request('raise'))
        self.assertEqual(result['error'],'indecis_inference_failed');self.assertIsNone(adapter._process)
        self.assertEqual(adapter.predict(self.request())['raw_output'],{'forward_executed':False,'cached_failure':True})
        self.assertEqual(len(json.loads(self.capture.read_text())['rows']),1)

    def test_native_output_failure_is_a_fixed_fatal_error(self):
        adapter=self.adapter();result=adapter.predict(self.request('invalid-output'))
        self.assertEqual(result['error'],'indecis_output_invalid');self.assertIsNone(adapter._process)
        self.assertEqual(adapter.predict(self.request())['raw_output'],{'forward_executed':False,'cached_failure':True})

    def test_failed_post_handshake_guard_removes_ready_only_provenance(self):
        with patch.object(IndecisAdapter,'_guard',side_effect=ValueError('fixture drift')):adapter=self.adapter()
        self.assertFalse(adapter.provenance['available']);self.assertIsNone(adapter._process)
        self.assertNotIn('runtime',adapter.provenance);self.assertNotIn('load_ms',adapter.provenance)
        self.assertNotIn('load_rss_mb',adapter.provenance)

    def test_timeout_and_rss_guards_stop_process(self):
        adapter=self.adapter();result=adapter.predict(self.request('delay'))
        self.assertEqual(result['status'],'timeout');self.assertIsNone(adapter._process)
        profile=deepcopy(self.profile);profile['model']['max_rss_mb']=64
        # This half tests RSS enforcement, not the 300 ms timeout above.
        # Give the fake worker time to allocate on a busy host.
        profile['timeout_seconds']=2
        adapter=self.adapter(profile);result=adapter.predict(self.request('oom'))
        self.assertEqual(result['error'],'indecis_rss_limit');self.assertIsNone(adapter._process)

    def test_process_group_cleanup_includes_spawned_child_and_close(self):
        adapter=self.adapter();result=adapter.predict(self.request('spawn'))
        self.assertEqual(result['status'],'timeout');self.assertIsNone(adapter._process)
        child=json.loads(self.capture.read_text())['child_pid']
        status=Path(f'/proc/{child}/status')
        if status.exists():self.assertIn('State:\tZ',status.read_text())
        second=self.adapter();second.close();second.close()
        self.assertEqual(second.predict(self.request())['error'],'indecis_adapter_closed')

    def test_identity_contains_content_and_excludes_artifact_locations(self):
        first=self.adapter();self.assertTrue(first.provenance['available'])
        copied=self.root/'clone';copied.mkdir()
        import shutil
        for name in ('model','source','indecis-worker','assets.json','sources.json','build.json','prompt.json'):
            origin=self.root/name;destination=copied/name
            if origin.is_dir():shutil.copytree(origin,destination)
            else:shutil.copy2(origin,destination)
        second=IndecisAdapter(self.profile,copied/'profile.json');self.addCleanup(second.close)
        self.assertTrue(second.provenance['available']);self.assertEqual(first.provenance['identity_sha256'],second.provenance['identity_sha256'])


if __name__=='__main__':unittest.main()
