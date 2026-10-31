"""D3 CPU boundary checks without importing publisher code or loading weights."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from deposium_bench.adapters import parse_profile
from deposium_bench.campaigns import _prepare_profile
from deposium_bench.choice_protocol import CONTEXT_CHOICE_PROMPT
from deposium_bench import d3_adapter as module
from deposium_bench import mastra_observation as observation
from deposium_bench.mastra_pilot import DATASET

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
INPUT = {"context": "Une demande en français.", "question": "Quelle action ?",
         "options": [{"id": "private-a", "description": "Rechercher"},
                     {"id": "private-b", "description": "Compter"}]}
WORKER = r'''import hashlib,json,math,sys
mode=MODE
def send(v): print(json.dumps(v,allow_nan=False),flush=True)
config=json.loads(sys.stdin.readline())['config']
repo=config['repo_id']; name=repo.rsplit('/',1)[-1]
count={'vllm-sr/d3-edge':594321600,'vllm-sr/d3-lite':852985920,
       'vllm-sr/d3-nano':2213241664,'vllm-sr/d3-mini':4539265536,
       'vllm-sr/d3-flash':8392695024}[repo]
shape={'vllm-sr/d3-edge':[255,1024],'vllm-sr/d3-lite':[255,1024],
       'vllm-sr/d3-nano':[255,2048],'vllm-sr/d3-mini':[255,2560],
       'vllm-sr/d3-flash':[255,4096]}[repo]
if mode=='bad_count': count+=1
if mode=='bad_shape': shape=[255,shape[1]+1]
send({'status':'ready','runtime':config['pins'],'load_ms':1.0,'rss_mb':10.0,
      'native_max_input_tokens':4096,'checkpoint_max_input_tokens':None,
      'backbone_dtype':'bfloat16','readout_dtype':'float32',
      'device':'cpu','loading_mode':'native-d3-bf16-readout-fp32',
      'backbone_parameters':count,'readout_shape':shape})
for line in sys.stdin:
 request=json.loads(line); value=request['input'];ids=[o['id'] for o in value['options']]
 blob=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
 probabilities={'c0':0.25,'c1':0.75}
 confidence=1+sum(p*math.log(p) for p in probabilities.values())/math.log(2)
 answer={'type':'choice','choice':'c1','probabilities':probabilities,'confidence':confidence}
 if mode=='bad_id': answer['choice']='private-b'
 if mode=='bad_probability': answer['probabilities']['c0']=-0.25
 if mode=='bad_confidence': answer['confidence']=0.5
 native={'model':name,'answers':{'decision':answer},'usage':{'input_tokens':40,'output_tokens':0}}
 raw={'native_result':native,'native_tokens':40,'input_sha256':hashlib.sha256(blob).hexdigest(),
      'ordered_ids':ids,'encoding_info':{'tokens':40,'stateTruncated':False,'optionsTruncated':False},
      'forward_executed':True,'decision_ms':4.0,'inference_ms':3.0,'rss_mb':10.0}
 send({'sequence':request['sequence'],'status':'ok','output':{'choice_id':ids[1]},'raw_output':raw,'error':None})
'''


class D3AdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        model = self.root / 'model'; model.mkdir()
        (model / 'config.json').write_text('{}\n')
        (self.root / 'prompt.json').write_text(json.dumps(CONTEXT_CHOICE_PROMPT))
        (self.root / 'runtime.lock').write_text('torch==2.14.0+cpu\ntransformers==5.17.0\n'
            'tokenizers==0.23.2\nsafetensors==0.8.0\naccelerate==1.1.0\neinops==0.8.0\n')
        self.worker = self.root / 'worker.py'
        self.worker.write_text(WORKER.replace('MODE', repr('ok')))
        self.profile = {'schema_version':'deposium.candidate/v1','profile_id':'d3-test',
            'adapter':'d3','qualification':'model_isolated','capabilities':['bench.context-choice'],
            'recordings':None,'revision':module.MODELS[module.REPO_ID][0], 'timeout_seconds':3,
            'model':{'repo_id':module.REPO_ID,'local_dir':'model','runtime_python':sys.executable,
                     'assets_manifest':'assets.json','prompt_path':'prompt.json','runtime_lock':'runtime.lock',
                     'max_length':4096,'threads':2,'max_rss_mb':6144}}
        self.manifest = self.root / 'assets.json'
        self._manifest()

    def _manifest(self):
        blob = (self.root / 'model/config.json').read_bytes()
        self.manifest.write_text(json.dumps({'schema_version':'deposium.model-assets/v1',
            'repo_id':self.profile['model']['repo_id'],'revision':self.profile['revision'],
            'files':[{'path':'config.json','size':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}]}))

    def adapter(self):
        with patch.object(module, 'WORKER', self.worker), patch.object(
                module.D3Adapter, '_host_available_mb', return_value=100000):
            adapter = module.D3Adapter(self.profile, self.root / 'profile.json')
        memory = patch.object(adapter, '_host_available_mb', return_value=100000)
        memory.start()
        self.addCleanup(memory.stop)
        self.addCleanup(adapter.close)
        return adapter

    def test_all_variants_and_fixed_guards(self):
        guards = {'vllm-sr/d3-edge':(6144,8192,180),
                  'vllm-sr/d3-lite':(6144,8192,180),
                  'vllm-sr/d3-nano':(12288,16384,240),
                  'vllm-sr/d3-mini':(14336,18432,300),
                  'vllm-sr/d3-flash':(18432,22528,360)}
        self.assertEqual(set(module.MODELS), set(guards))
        for repo, (_, _, ceiling, floor, init) in module.MODELS.items():
            with self.subTest(repo=repo):
                self.profile['model']['repo_id'] = repo
                self.profile['revision'] = module.MODELS[repo][0]
                self.profile['model']['max_rss_mb'] = ceiling
                self._manifest()
                parse_profile(json.dumps(self.profile).encode())
                self.assertEqual((ceiling, floor, init), guards[repo])
                self.assertEqual(module.minimum_available_mib(repo), guards[repo][1])
                provenance = self.adapter().provenance
                self.assertTrue(provenance['available'])
                self.assertEqual((provenance['backbone_parameters'], provenance['readout_shape']),
                                 module.MODEL_TENSORS[repo])
                for key, invalid in [('max_length',4095),('threads',3),('max_rss_mb',ceiling+1)]:
                    changed=json.loads(json.dumps(self.profile));changed['model'][key]=invalid
                    with self.assertRaises(ValueError): parse_profile(json.dumps(changed).encode())
        self.profile['timeout_seconds']=301
        with self.assertRaises(ValueError): parse_profile(json.dumps(self.profile).encode())

    def test_new_variants_reject_wrong_ready_tensor_identity(self):
        for repo in ('vllm-sr/d3-mini', 'vllm-sr/d3-flash'):
            self.profile['model']['repo_id'] = repo
            self.profile['revision'] = module.MODELS[repo][0]
            self.profile['model']['max_rss_mb'] = module.MODELS[repo][2]
            self._manifest()
            for mode in ('bad_count', 'bad_shape'):
                with self.subTest(repo=repo, mode=mode):
                    self.worker.write_text(WORKER.replace('MODE', repr(mode)))
                    provenance = self.adapter().provenance
                    self.assertFalse(provenance['available'])
                    self.assertEqual(provenance['availability_error'], 'd3_initialization_invalid')

    @unittest.skipUnless(Draft202012Validator, 'optional jsonschema is not installed')
    def test_new_variant_candidate_and_campaign_provenance_schemas(self):
        candidate_schema = json.loads((ROOT/'schemas/candidate-v1.schema.json').read_text())
        campaign_schema = json.loads((ROOT/'schemas/campaign-v1.schema.json').read_text())
        candidate = Draft202012Validator(candidate_schema)
        provenance = Draft202012Validator({'$defs': campaign_schema['$defs'],
                                           '$ref': '#/$defs/d3_provenance'})
        for repo in ('vllm-sr/d3-mini', 'vllm-sr/d3-flash'):
            with self.subTest(repo=repo):
                revision, _, ceiling, _, _ = module.MODELS[repo]
                self.profile['model']['repo_id'] = repo
                self.profile['revision'] = revision
                self.profile['model']['max_rss_mb'] = ceiling
                self._manifest()
                self.assertTrue(candidate.is_valid(self.profile))
                ready = self.adapter().provenance
                self.assertTrue(provenance.is_valid(ready))
                wrong = json.loads(json.dumps(self.profile))
                wrong['model']['max_rss_mb'] -= 1
                self.assertFalse(candidate.is_valid(wrong))
                wrong = json.loads(json.dumps(self.profile))
                wrong['revision'] = '0' * 40
                self.assertFalse(candidate.is_valid(wrong))
                wrong = json.loads(json.dumps(ready))
                wrong['readout_shape'][1] += 1
                self.assertFalse(provenance.is_valid(wrong))
                wrong = json.loads(json.dumps(ready))
                wrong['backbone_parameters'] += 1
                self.assertFalse(provenance.is_valid(wrong))
                wrong = json.loads(json.dumps(ready))
                wrong['model_assets']['revision'] = '0' * 40
                self.assertFalse(provenance.is_valid(wrong))

    def test_missing_and_invalid_assets_before_worker(self):
        self.manifest.unlink()
        missing=self.adapter()
        self.assertEqual(missing.provenance['availability_error'],'d3_assets_or_runtime_missing')
        self.manifest.mkdir()
        invalid=self.adapter()
        self.assertEqual(invalid.provenance['availability_error'],'d3_initialization_invalid')
        self.manifest.rmdir();self._manifest()
        (self.root/'model/config.json').write_text('{"changed":true}\n')
        changed=self.adapter()
        self.assertEqual(changed.provenance['availability_error'],'d3_initialization_invalid')

    def test_choice_is_remapped_and_native_distribution_retained(self):
        adapter=self.adapter()
        result=adapter.predict({'contract_id':'bench.context-choice','input':INPUT})
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['output'],{'choice_id':'private-b'})
        self.assertEqual(result['raw_output']['native_result']['answers']['decision']['choice'],'c1')
        self.assertEqual(result['raw_output']['native_result']['answers']['decision']['probabilities'],{'c0':.25,'c1':.75})
        for mode in ('bad_id','bad_probability','bad_confidence'):
            self.worker.write_text(WORKER.replace('MODE',repr(mode)))
            bad=self.adapter().predict({'contract_id':'bench.context-choice','input':INPUT})
            self.assertEqual((bad['status'],bad['error']),('error','d3_runtime_or_protocol_changed'))

    def test_macos_probes_use_vm_stat_estimate_and_process_group_rss(self):
        with patch.object(module.platform, 'system', return_value='Darwin'), \
                patch('deposium_bench.native_resources.memory_snapshot',
                      return_value={'MemAvailable_mib': 12345.5, 'MemTotal_mib': 65536.0}):
            self.assertEqual(module.D3Adapter._host_available_mb(), 12345.5)
        with patch.object(module.platform, 'system', return_value='Darwin'), \
                patch('deposium_bench.native_resources.memory_snapshot', side_effect=OSError('vm_stat')):
            with self.assertRaisesRegex(OSError, 'd3_host_memory_unknown'):
                module.D3Adapter._host_available_mb()
        adapter = self.adapter()
        adapter._process = Mock(pid=424242)
        adapter._process.poll.return_value = None
        with patch.object(module.platform, 'system', return_value='Darwin'), \
                patch.object(module.Path, 'read_text', side_effect=FileNotFoundError()), \
                patch('deposium_bench.native_resources.process_group_rss_mib', return_value=321.0) as group:
            adapter._rss()
            group.assert_called_once_with(424242)
            self.assertEqual(adapter._peak_rss_mb, 321.0)
            with patch('deposium_bench.native_resources.process_group_rss_mib', return_value=adapter._model['max_rss_mb'] + 1):
                with self.assertRaisesRegex(MemoryError, 'd3_rss_limit'):
                    adapter._rss()
        with patch.object(module.platform, 'system', return_value='Linux'), \
                patch.object(module.Path, 'read_text', side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(OSError, 'd3_rss_unavailable'):
                adapter._rss()
        adapter._process = None

    def test_worker_rss_divisor_follows_the_platform(self):
        spec = importlib.util.spec_from_file_location('d3_worker_rss_test', ROOT / 'bridges/d3-worker.py')
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        usage = Mock(ru_maxrss=2 * 1048576)
        with patch.object(worker.resource, 'getrusage', return_value=usage):
            with patch.object(worker.sys, 'platform', 'darwin'):
                self.assertEqual(worker._rss(), 2.0)
            with patch.object(worker.sys, 'platform', 'linux'):
                self.assertEqual(worker._rss(), 2048.0)

    def test_fake_worker_prediction_is_independent_of_host_available_memory(self):
        with patch.object(module.D3Adapter, '_host_available_mb', return_value=1024):
            adapter = self.adapter()
            result = adapter.predict({'contract_id': 'bench.context-choice', 'input': INPUT})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['output'], {'choice_id': 'private-b'})
        self.assertTrue(result['raw_output']['forward_executed'])

    def test_mastra_floor_precedes_archive_and_worker(self):
        for repo, (_, _, ceiling, floor, _) in module.MODELS.items():
            self.profile['model']['repo_id']=repo;self.profile['revision']=module.MODELS[repo][0]
            self.profile['model']['max_rss_mb']=ceiling
            path=self.root/'profile.json';path.write_text(json.dumps(self.profile))
            output=self.root/('archive-'+repo.rsplit('-',1)[-1])
            with patch.object(observation,'memory_snapshot',return_value={'MemAvailable_mib':floor-1}), \
                    patch.object(observation,'_stack_context',side_effect=AssertionError('stack accessed')), \
                    patch.object(observation,'create_adapter',side_effect=AssertionError('worker started')):
                with self.assertRaisesRegex(ValueError,'available RAM'):
                    observation.observe_local(DATASET,path,output)
            self.assertFalse(output.exists())

    def test_mastra_600_seconds_is_d3_only(self):
        path=self.root/'profile.json';path.write_text(json.dumps(self.profile))
        with patch.object(observation,'memory_snapshot',return_value={'MemAvailable_mib':8191}):
            with self.assertRaisesRegex(ValueError,'available RAM'):
                observation.observe_local(DATASET,path,self.root/'d3-600',max_seconds=600)
        self.assertFalse((self.root/'d3-600').exists())
        other=json.loads((ROOT/'profiles/vela2-03-cpu-context.json').read_text())
        path.write_text(json.dumps(other))
        with self.assertRaisesRegex(ValueError,'1..300'):
            observation.observe_local(DATASET,path,self.root/'other-600',max_seconds=600)


class D3WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('d3_worker_test',ROOT/'bridges/d3-worker.py')
        cls.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.worker)

    def test_named_parameter_tuples_dtype_device_shape_and_count(self):
        worker=self.worker
        for repo,(_, count,shape,_) in worker.MODELS.items():
            for invalid in (None,'dtype','device','count','shape','readout_dtype'):
                tensor=types.SimpleNamespace(numel=lambda:count+(invalid=='count'),
                    dtype='fp32' if invalid=='dtype' else 'bf16',
                    device=types.SimpleNamespace(type='cuda' if invalid=='device' else 'cpu'))
                readout=types.SimpleNamespace(shape=[255,999] if invalid=='shape' else shape,
                    dtype='bf16' if invalid=='readout_dtype' else 'fp32',
                    device=types.SimpleNamespace(type='cpu'))
                model=types.SimpleNamespace(backbone=types.SimpleNamespace(named_parameters=lambda:[('x',tensor)]),
                    readout=readout,batch_size=1,max_length=4096,permutation_average=False,fast=None,
                    manifest={'repo_id':repo},model_name=repo.rsplit('/',1)[-1],config={'max_length':None})
                torch=types.SimpleNamespace(bfloat16='bf16',float32='fp32')
                with self.subTest(repo=repo,invalid=invalid):
                    if invalid:
                        with self.assertRaises(ValueError):worker._check_model(model,repo,torch)
                    else:self.assertEqual(worker._check_model(model,repo,torch),1)

    def test_full_native_prepare_rejects_overflow_without_run_and_restores_cap(self):
        worker=self.worker
        class Model:
            max_length=4096
            model_name='d3-edge'
            def prepare(self,state,questions):
                self.seen_cap=self.max_length
                return types.SimpleNamespace(keys=['decision'],errors={},sequences={'decision':[1]*4097},
                    images=[],videos=[],reversed_sequences={})
            def run(self,_):raise AssertionError('forward attempted')
        model=Model()
        with patch.object(worker,'_rss',return_value=1.0):
            result=worker._predict(model,INPUT,4096,types.SimpleNamespace())
        self.assertEqual(result['status'],'unsupported')
        self.assertFalse(result['raw_output']['forward_executed'])
        self.assertEqual(result['raw_output']['encoding_info']['tokens'],4097)
        self.assertIsNone(model.seen_cap);self.assertEqual(model.max_length,4096)

    def test_actual_backbone_input_and_mask_alteration_is_rejected(self):
        worker=self.worker
        class Tensor:
            dtype='long';device=types.SimpleNamespace(type='cpu')
            def __init__(self,data):self.data=data;self.shape=[1,len(data)]
            def __getitem__(self,_):return types.SimpleNamespace(tolist=lambda:self.data)
        class Backbone:
            def register_forward_pre_hook(self,fn,with_kwargs=False):
                self.hook=fn;return types.SimpleNamespace(remove=lambda:None)
        class Model:
            backbone=Backbone()
            altered=True
            def run(self,prepared):
                self.backbone.hook(self.backbone,(),{'input_ids':Tensor([1,9 if self.altered else 2]),
                    'attention_mask':Tensor([1,1]),'use_cache':False})
                return {'decision':[.2,.8]},2
        fake_torch=types.SimpleNamespace(Tensor=Tensor,long='long')
        with self.assertRaisesRegex(ValueError,'d3_forward_payload_invalid'):
            worker._checked_run(Model(),object(),(1,2),fake_torch,{'forward_executed':False})
        good=Model();good.altered=False
        raw={'forward_executed':False}
        self.assertEqual(worker._checked_run(good,object(),(1,2),fake_torch,raw),
                         ({'decision':[.2,.8]},2))
        self.assertTrue(raw['forward_executed'])

    def test_invalid_native_answer_is_rejected(self):
        worker=self.worker
        answer={'type':'choice','choice':'c1','probabilities':{'c0':.25,'c1':.75},
                'confidence':1+(.25*__import__('math').log(.25)+.75*__import__('math').log(.75))/__import__('math').log(2)}
        native={'model':'d3-edge','answers':{'decision':answer},'usage':{'input_tokens':40,'output_tokens':0}}
        self.assertEqual(worker._valid_native(native,['c0','c1'],40,'d3-edge'),'c1')
        for key,value in [('choice','wrong'),('confidence',.5),('probabilities',{'c0':2,'c1':-1})]:
            changed=json.loads(json.dumps(native));changed['answers']['decision'][key]=value
            with self.assertRaises(ValueError):worker._valid_native(changed,['c0','c1'],40,'d3-edge')
