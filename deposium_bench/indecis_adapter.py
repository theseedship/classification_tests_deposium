"""Pinned, untrained Indecis open-choice CPU candidate; inert on import."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

from .cases import _json as validate_json, _no_annotations
from .choice_protocol import CONTEXT_CHOICE_CONTRACT, ordered_choice_ids, validate_choice_input
from .julia_adapter import JuliaAdapter, _encode, _digest, _stat, _small_json

BACKBONE_REPO = 'hotchpotch/bekko-embedding-v1-a8m'
BACKBONE_REVISION = 'c721113d59a1d91b447450324f51c4b3332c924a'
SOURCE_REPO = 'github.com/bornholm/indecis'
SOURCE_REVISION = '339e191405ac9be90f6857f810f478b3312b7f35'
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
MAX_FILES = 10000
MAX_SOURCE_FILES = 1000
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_LINE = 1024 * 1024
INITIALIZATION_SECONDS = 120
WORKER_SOURCE = Path(__file__).resolve().parents[1] / 'bridges' / 'indecis-worker' / 'main.go'
MODEL_FIELDS = {'repo_id','local_dir','assets_manifest','prompt_path','source_dir','source_manifest',
                'source_revision','worker_binary','build_manifest','max_length','threads','max_rss_mb'}
PATH_FIELDS = {'local_dir','assets_manifest','prompt_path','source_dir','source_manifest','worker_binary','build_manifest'}
INDECIS_CHOICE_PROMPT = {'schema_version':'deposium.indecis-choice-prompt/v1','input_protocol':'context_choice',
                       'mode':'open_untrained','state_field':'context','instruction_field':'question',
                       'options_field':'options','output_field':'choice_id',
                       'option_serialization':'description_newline_question','cache_policy':'request_local','trained':False}
BUILD_FIELDS = {'schema_version','source_revision','source_manifest_sha256','worker_source_sha256',
                'binary_sha256','go_version','build_flags','go_env'}


class IndecisProfileError(ValueError):
    """Invalid bounded, pinned Indecis CPU settings."""


def validate_model_profile(profile):
    model = profile.get('model')
    if not isinstance(model, dict) or set(model) != MODEL_FIELDS:
        raise IndecisProfileError('indecis_profile_fields_invalid')
    if (profile.get('adapter') != 'indecis' or profile.get('qualification') != 'model_isolated'
            or profile.get('capabilities') != [CONTEXT_CHOICE_CONTRACT] or profile.get('recordings') is not None):
        raise IndecisProfileError('indecis_profile_contract_invalid')
    if (model['repo_id'] != BACKBONE_REPO or profile.get('revision') != BACKBONE_REVISION
            or model['source_revision'] != SOURCE_REVISION):
        raise IndecisProfileError('indecis_profile_revision_invalid')
    for key in PATH_FIELDS:
        if not isinstance(model[key], str) or not model[key].strip() or '\x00' in model[key]:
            raise IndecisProfileError('indecis_profile_path_invalid')
    for key, ceiling in (('max_length',4096),('threads',4),('max_rss_mb',3072)):
        if type(model[key]) is not int or not 1 <= model[key] <= ceiling:
            raise IndecisProfileError('indecis_profile_resource_invalid')
    timeout = profile.get('timeout_seconds')
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise IndecisProfileError('indecis_profile_timeout_invalid')


def _envelope(status, output=None, raw=None, error=None):
    return {'status':status,'output':output,'raw_output':raw,'error':error}


def _input_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


class IndecisAdapter(JuliaAdapter):
    """Reuse Julia's bounded JSONL I/O, /proc polling and process-group cleanup."""
    capabilities = [CONTEXT_CHOICE_CONTRACT]

    def __init__(self, profile, profile_path):
        initialized = time.monotonic()
        validate_model_profile(profile)
        self._model = copy.deepcopy(profile['model'])
        self._timeout = float(profile['timeout_seconds'])
        self._paths = {key:Path(profile_path).resolve().parent/self._model[key] for key in PATH_FIELDS}
        self._process = None
        self._buffer = bytearray()
        self._states = {}
        self._asset_paths = set()
        self._source_paths = set()
        self._failure = None
        self._closed = False
        self._sequence = 0
        self._peak_rss_mb = 0.0
        self._artifact_bytes = 0
        self._lock = threading.Lock()
        self._initialization_deadline = initialized + INITIALIZATION_SECONDS
        self.provenance = {'profile_sha256':_digest(profile),'adapter_sha256':self._remember(Path(__file__)),
                           'adapter':'indecis','qualification':'model_isolated','model':copy.deepcopy(self._model),
                           'model_revision':profile['revision'],'source_revision':self._model['source_revision'],
                           'capabilities':list(self.capabilities),'available':False}
        try:
            self._prepare(profile)
            environment = {'PATH':os.defpath,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
                           'GOMAXPROCS':str(self._model['threads']),'GOTOOLCHAIN':'local','GOPROXY':'off',
                           'CUDA_VISIBLE_DEVICES':'','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
            self._process = subprocess.Popen([str(self._paths['worker_binary'])], stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                             env=environment,start_new_session=True)
            os.set_blocking(self._process.stdin.fileno(),False)
            os.set_blocking(self._process.stdout.fileno(),False)
            config = {'local_dir':str(self._asset_root),'prompt':self._prompt,'revision':profile['revision'],
                      'source_revision':self._model['source_revision'],'max_length':self._model['max_length'],
                      'threads':self._model['threads']}
            ready = self._exchange({'op':'initialize','config':config},max(0,self._initialization_deadline-time.monotonic()))
            self._ready(ready)
            self._guard()
        except TimeoutError:
            self._fail('timeout','indecis_initialization_timeout')
        except FileNotFoundError:
            self._fail('missing','indecis_assets_or_runtime_missing')
        except MemoryError:
            self._fail('error','indecis_rss_limit')
        except (OSError,ValueError,KeyError,TypeError):
            self._fail('error','indecis_initialization_invalid')
        except BaseException:
            self.close()
            raise
        self._initialization_deadline = None
        self.provenance['init_wall_ms'] = (time.monotonic()-initialized)*1000
        identity = {key:value for key,value in self.provenance.items()
                    if key not in {'model','profile_sha256','load_ms','load_rss_mb','init_wall_ms','available','availability_error'}}
        identity['model'] = {key:value for key,value in self._model.items() if key not in PATH_FIELDS}
        self.provenance['identity_sha256'] = _digest(identity)

    def _remember(self, path):
        if not path.is_file():
            raise FileNotFoundError('indecis_artifact_missing')
        before = _stat(path)
        if before[1] > MAX_ARTIFACT_BYTES:
            raise ValueError('indecis_artifact_limit')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):
                if self._initialization_deadline is not None and time.monotonic() >= self._initialization_deadline:
                    raise TimeoutError('indecis_preflight_timeout')
                digest.update(chunk)
        if _stat(path) != before:
            raise ValueError('indecis_artifact_changed')
        self._states[path] = before
        return digest.hexdigest()

    def _files(self, root, source=False):
        files = set()
        entries = 0
        for base, directories, names in os.walk(root,followlinks=False):
            excluded = {'.cache','__pycache__'} | ({'.git'} if source else set())
            directories[:] = [name for name in directories if name not in excluded]
            for name in directories+names:
                path = Path(base)/name
                entries += 1
                if entries > MAX_FILES or path.is_symlink():
                    raise ValueError('indecis_artifact_inventory_invalid')
                if path.is_file() and (not source or path.suffix in {'.go','.s','.h'} or path.name in {'go.mod','go.sum','LICENSE'}):
                    files.add(path.relative_to(root))
                    if source and len(files) > MAX_SOURCE_FILES:
                        raise ValueError('indecis_artifact_inventory_invalid')
        return files

    def _manifest(self, path, root, expected_schema, repo, revision, source=False):
        manifest,digest = _small_json(path)
        if self._remember(path) != digest:
            raise ValueError('indecis_manifest_changed')
        expected_fields = {'schema_version','repo_id','revision','files'} | ({'total_bytes'} if source else set())
        if (set(manifest) != expected_fields
                or manifest['schema_version'] != expected_schema or manifest['repo_id'] != repo
                or manifest['revision'] != revision or not isinstance(manifest['files'],list)
                or not 1 <= len(manifest['files']) <= (MAX_SOURCE_FILES if source else MAX_FILES)):
            raise ValueError('indecis_manifest_invalid')
        indexed = {}
        total_bytes = 0
        for item in manifest['files']:
            if (not isinstance(item,dict) or set(item) != {'path','sha256','size'}
                    or not isinstance(item['path'],str) or not isinstance(item['sha256'],str)
                    or not re.fullmatch('[0-9a-f]{64}',item['sha256'])
                    or type(item['size']) is not int or item['size'] < 0):
                raise ValueError('indecis_manifest_invalid')
            relative = Path(item['path'])
            if (relative.is_absolute() or not relative.parts or relative.as_posix() != item['path']
                    or any(part in {'.','..','.git','.cache','__pycache__'} for part in relative.parts)
                    or relative.as_posix() in indexed):
                raise ValueError('indecis_manifest_path_invalid')
            artifact = root/relative
            if artifact.is_symlink() or not artifact.resolve().is_relative_to(root):
                raise ValueError('indecis_manifest_path_invalid')
            total_bytes += item['size']
            if source and total_bytes > MAX_SOURCE_BYTES:
                raise ValueError('indecis_source_limit')
            self._artifact_bytes += item['size']
            if self._artifact_bytes > MAX_ARTIFACT_BYTES:
                raise ValueError('indecis_artifact_limit')
            if self._remember(artifact) != item['sha256'] or artifact.stat().st_size != item['size']:
                raise ValueError('indecis_artifact_hash_mismatch')
            indexed[relative.as_posix()] = {'sha256':item['sha256'],'size':item['size']}
        if source and (type(manifest['total_bytes']) is not int or manifest['total_bytes'] != total_bytes):
            raise ValueError('indecis_manifest_invalid')
        files = self._files(root,source)
        if files != {Path(name) for name in indexed}:
            raise ValueError('indecis_unlisted_artifact')
        return manifest,digest,files,_digest(indexed)

    def _prepare(self, profile):
        if not self._paths['worker_binary'].is_file() or not os.access(self._paths['worker_binary'],os.X_OK):
            raise FileNotFoundError('indecis_binary_missing')
        self._asset_root = self._paths['local_dir'].resolve()
        self._source_root = self._paths['source_dir'].resolve()
        assets,digest,self._asset_paths,aggregate = self._manifest(self._paths['assets_manifest'],self._asset_root,
                'deposium.model-assets/v1',BACKBONE_REPO,profile['revision'])
        if {'config.json','tokenizer.json','model.safetensors'} != {p.as_posix() for p in self._asset_paths}:
            raise ValueError('indecis_required_asset_missing')
        self.provenance.update(assets_manifest=assets,assets_manifest_sha256=digest,model_assets_sha256=aggregate)
        sources,digest,self._source_paths,aggregate = self._manifest(self._paths['source_manifest'],self._source_root,
                'deposium.indecis-source/v1',SOURCE_REPO,self._model['source_revision'],source=True)
        if not {'go.mod','model.go','decide_open.go','open.go'} <= {p.as_posix() for p in self._source_paths}:
            raise ValueError('indecis_required_source_missing')
        self.provenance.update(source_manifest=sources,source_manifest_sha256=digest,source_files_sha256=aggregate)
        prompt,digest = _small_json(self._paths['prompt_path'])
        if prompt != INDECIS_CHOICE_PROMPT or self._remember(self._paths['prompt_path']) != digest:
            raise ValueError('indecis_prompt_invalid')
        self._prompt = prompt
        self.provenance.update(prompt=prompt,prompt_sha256=digest,prompt_schema_version=prompt['schema_version'],
                               input_protocol=prompt['input_protocol'])
        binary_hash = self._remember(self._paths['worker_binary'])
        self._artifact_bytes += self._paths['worker_binary'].stat().st_size
        if self._artifact_bytes > MAX_ARTIFACT_BYTES:
            raise ValueError('indecis_artifact_limit')
        worker_hash = _input_digest({name:self._remember(WORKER_SOURCE.with_name(name))
                                     for name in ('main.go','main_test.go','go.mod')})
        build,digest = _small_json(self._paths['build_manifest'])
        if self._remember(self._paths['build_manifest']) != digest:
            raise ValueError('indecis_build_changed')
        if (set(build) != BUILD_FIELDS or build['schema_version'] != 'deposium.indecis-build/v1'
                or build['source_revision'] != self._model['source_revision']
                or build['source_manifest_sha256'] != self.provenance['source_manifest_sha256']
                or build['worker_source_sha256'] != worker_hash or build['binary_sha256'] != binary_hash
                or not isinstance(build['go_version'],str) or not re.fullmatch(r'go1\.27\.1-X:simd',build['go_version'])
                or build['build_flags'] != ['-p','2','-trimpath','-buildvcs=false']
                or not isinstance(build['go_env'],dict) or set(build['go_env']) != {'GOOS','GOARCH','CGO_ENABLED','GOTOOLCHAIN','GOEXPERIMENT','GOPROXY','GOSUMDB'}
                or build['go_env']['CGO_ENABLED'] != '0' or build['go_env']['GOTOOLCHAIN'] != 'local'
                or build['go_env']['GOEXPERIMENT'] != 'simd'
                or build['go_env']['GOPROXY'] != 'off' or build['go_env']['GOSUMDB'] != 'off'
                or any(not isinstance(value,str) or (not value and key != 'GOEXPERIMENT') for key,value in build['go_env'].items())):
            raise ValueError('indecis_build_invalid')
        self._build = build
        self.provenance.update(build_manifest=build,build_manifest_sha256=digest,binary_sha256=binary_hash,worker_sha256=worker_hash)
        helper_hashes = {name:self._remember(Path(__file__).with_name(name))
                         for name in ('julia_adapter.py','cases.py','choice_protocol.py')}
        self.provenance.update(helper_sha256=helper_hashes,
                               settings={'mode':'open_untrained','trained':False,'max_length':self._model['max_length'],
                                         'threads':self._model['threads'],'max_rss_mb':self._model['max_rss_mb'],
                                         'strict_encoding':True,'cache_policy':'request_local'})

    def _ready(self, ready):
        if (not isinstance(ready,dict) or set(ready) != {'status','runtime','load_ms','rss_mb','binary_sha256'}
                or ready['status'] != 'ready' or ready['binary_sha256'] != self.provenance['binary_sha256']
                or not isinstance(ready['runtime'],dict)
                or set(ready['runtime']) != {'go','goos','goarch','indecis_revision','backbone_revision'}
                or ready['runtime']['go'] != self._build['go_version']
                or ready['runtime']['goos'] != self._build['go_env']['GOOS']
                or ready['runtime']['goarch'] != self._build['go_env']['GOARCH']
                or ready['runtime']['indecis_revision'] != self._model['source_revision']
                or ready['runtime']['backbone_revision'] != BACKBONE_REVISION
                or not self._nonnegative(ready['load_ms']) or not self._nonnegative(ready['rss_mb'])):
            if isinstance(ready,dict) and ready.get('error') == 'indecis_assets_or_runtime_missing':
                raise FileNotFoundError('indecis_assets_or_runtime_missing')
            raise ValueError('indecis_ready_invalid')
        if max(self._peak_rss_mb,ready['rss_mb']) > self._model['max_rss_mb']:
            raise MemoryError('indecis_rss_limit')
        self.provenance.update(available=True,runtime={'parent_python':sys.version.split()[0],**ready['runtime']},
                               load_ms=ready['load_ms'],load_rss_mb=max(self._peak_rss_mb,ready['rss_mb']))

    def _guard(self):
        if (self._paths['local_dir'].resolve() != self._asset_root or self._paths['source_dir'].resolve() != self._source_root
                or self._asset_paths != self._files(self._asset_root) or self._source_paths != self._files(self._source_root,source=True)
                or any(_stat(path) != state for path,state in self._states.items())):
            raise ValueError('indecis_artifacts_changed')
        self._rss()

    def _fail(self, status, code, raw=None):
        self._failure = _envelope(status,raw=raw,error=code)
        self.provenance.update(available=False,availability_error=code)
        if self._initialization_deadline is not None:
            for key in ('runtime','load_ms','load_rss_mb'):
                self.provenance.pop(key,None)
        self.close()

    def close(self):
        self._closed = True
        super().close()

    def predict(self, request):
        if not isinstance(request,dict) or request.get('contract_id') != CONTEXT_CHOICE_CONTRACT:
            return _envelope('unsupported',error='unsupported_contract')
        value = request.get('input')
        try:
            validate_json(value);_no_annotations(value);validate_choice_input(value);_input_digest(value)
        except (ValueError,TypeError,UnicodeError):
            return _envelope('error',error='indecis_input_invalid')
        with self._lock:
            if self._failure is not None:
                cached = copy.deepcopy(self._failure)
                cached['raw_output'] = {'forward_executed':False,'cached_failure':True}
                return cached
            if self._closed:
                return _envelope('error',error='indecis_adapter_closed')
            message = {'op':'predict','sequence':self._sequence+1,'input':value}
            if len(_encode(message)) > MAX_LINE:
                return _envelope('unsupported',error='indecis_request_too_large')
            self._sequence += 1
            try:
                self._guard()
                response = self._exchange(message,self._timeout)
                self._guard()
                self._audit_response(response,value)
                envelope = {key:response[key] for key in ('status','output','raw_output','error')}
                if response['status'] == 'error':
                    self._fail('error',response['error'],response['raw_output'])
                return envelope
            except TimeoutError:
                self._fail('timeout','indecis_inference_timeout')
            except MemoryError:
                self._fail('error','indecis_rss_limit')
            except FileNotFoundError:
                self._fail('missing','indecis_runtime_missing')
            except (OSError,ValueError,TypeError,KeyError):
                self._fail('error','indecis_runtime_or_protocol_changed')
            except BaseException:
                self.close()
                raise
            return copy.deepcopy(self._failure)

    def _audit_response(self, response, value):
        if (not isinstance(response,dict) or set(response) != {'sequence','status','output','raw_output','error'}
                or type(response['sequence']) is not int or response['sequence'] != self._sequence
                or response['status'] not in {'ok','unsupported','error'}):
            raise ValueError('indecis_result_invalid')
        raw = response['raw_output']
        if response['status'] == 'error' and raw is None:
            if response['output'] is not None or response['error'] not in {'indecis_inference_failed','indecis_encoding_mismatch','indecis_input_invalid','indecis_output_invalid','indecis_output_limit'}:
                raise ValueError('indecis_result_invalid')
            return
        required = {'native_result','ordered_ids','input_sha256','probabilities','decision_ms','inference_ms',
                    'rss_mb','encoding_info','token_components','forward_executed'}
        if (not isinstance(raw,dict) or set(raw) != required or raw['ordered_ids'] != ordered_choice_ids(value)
                or raw['input_sha256'] != _input_digest(value) or not self._nonnegative(raw['decision_ms'])
                or not self._nonnegative(raw['rss_mb']) or type(raw['forward_executed']) is not bool):
            raise ValueError('indecis_audit_invalid')
        if raw['rss_mb'] > self._model['max_rss_mb']:
            raise MemoryError('indecis_rss_limit')
        encoding,components = raw['encoding_info'],raw['token_components']
        if (not isinstance(components,dict) or set(components) != {'context_tokens','option_tokens','total_tokens','max_sequence_tokens'}
                or any(type(components[key]) is not int or components[key] < 1 for key in ('context_tokens','total_tokens','max_sequence_tokens'))
                or not isinstance(components['option_tokens'],list) or len(components['option_tokens']) != len(value['options'])
                or any(type(tokens) is not int or tokens < 1 for tokens in components['option_tokens'])
                or components['total_tokens'] != components['context_tokens']+sum(components['option_tokens'])
                or components['max_sequence_tokens'] != max([components['context_tokens'],*components['option_tokens']])
                or not isinstance(encoding,dict) or set(encoding) != {'tokens','stateTruncated','optionsTruncated'}
                or type(encoding['tokens']) is not int or encoding['tokens'] != components['max_sequence_tokens']
                or encoding['stateTruncated'] is not False or encoding['optionsTruncated'] is not False):
            raise ValueError('indecis_encoding_audit_invalid')
        if response['status'] == 'unsupported':
            if (response['error'] not in {'indecis_context_overflow','indecis_option_overflow'} or response['output'] is not None
                    or raw['forward_executed'] is not False or raw['inference_ms'] is not None
                    or raw['native_result'] is not None or raw['probabilities'] is not None
                    or components['max_sequence_tokens'] <= self._model['max_length']
                    or (response['error'] == 'indecis_context_overflow' and components['context_tokens'] <= self._model['max_length'])
                    or (response['error'] == 'indecis_option_overflow' and max(components['option_tokens']) <= self._model['max_length'])):
                raise ValueError('indecis_overflow_audit_invalid')
            return
        if response['status'] == 'error':
            if (response['error'] not in {'indecis_inference_failed','indecis_encoding_mismatch','indecis_input_invalid','indecis_output_invalid','indecis_output_limit'} or response['output'] is not None
                    or raw['native_result'] is not None or raw['probabilities'] is not None
                    or (raw['inference_ms'] is not None and (not self._nonnegative(raw['inference_ms']) or raw['inference_ms'] > raw['decision_ms']))):
                raise ValueError('indecis_error_audit_invalid')
            return
        descriptions = [option['description'] for option in value['options']]
        probabilities = raw['probabilities']
        if (response['error'] is not None or raw['forward_executed'] is not True
                or not self._nonnegative(raw['inference_ms']) or raw['inference_ms'] > raw['decision_ms']
                or components['max_sequence_tokens'] > self._model['max_length']
                or not isinstance(probabilities,dict) or set(probabilities) != set(descriptions)
                or any(not self._nonnegative(probability) or probability > 1 for probability in probabilities.values())
                or abs(sum(probabilities.values())-1) > 1e-10):
            raise ValueError('indecis_result_invalid')
        winner = max(descriptions,key=probabilities.__getitem__)
        winner_index = descriptions.index(winner)
        native = raw['native_result']
        if (not isinstance(native,dict) or not {'question','kind','choice','probs','confidence'} <= set(native)
                or set(native)-{'question','kind','choice','probs','confidence','score','margin'}
                or native['question'] != 'answer' or native['kind'] != 'choice' or native['choice'] != winner
                or not isinstance(native['probs'],dict) or any(not self._nonnegative(p) for p in native['probs'].values())
                or native['probs'] != probabilities
                or not self._nonnegative(native['confidence']) or native['confidence'] != probabilities[winner]
                or any(type(native[key]) not in (int,float) or not math.isfinite(native[key]) for key in ('score','margin') if key in native)
                or response['output'] != {'choice_id':value['options'][winner_index]['id']}):
            raise ValueError('indecis_native_result_invalid')
