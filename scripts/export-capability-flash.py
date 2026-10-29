#!/usr/bin/env python3
"""Export reviewed aggregate views from sealed Flash study archives; no inference.

The shared context analyzer supplies scores. Only allowlisted counts, public
model identities and aggregate resource evidence leave the private study.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

HEAD = '7e61b6d4660bae81ca97d06d464fb02fac4ec4ef'
MODEL_SHA = '7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b'
NATIVE_PIN = 'efe3626b119ff81033e309c3ba07a770bef2c546'
DATASETS = {'anchor': ('datasets/context-choice-v1/cases.jsonl',132,'767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616'),
 'capability': ('datasets/capability-choice-v1/cases.jsonl',192,'0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0')}
STATUSES = ('ok','unsupported','missing','error','timeout','abstain')
AXES = ('benchmark_pack','task_type','use_case','catalogue_variant','language','split','difficulty','domain')
SCALARS = ('total_cases','recorded_cases','scored_cases','passed_cases','failed_scored_cases','coverage_over_all','accuracy_over_all','accuracy_scored','independent_families','scored_families','scenario_count')
STATS = ('count','min','median','p95','max')


def require(value, reason):
    if not value: raise ValueError(reason)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def load(path): return json.loads(path.read_bytes())
def numeric(value): return value is None or (type(value) in (int,float) and math.isfinite(value) and value>=0)
def integer(value): return type(value) is int and value>=0
def hash_value(value): return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None


def stats(value):
    result = {k:value[k] for k in STATS}
    require(all(numeric(v) for v in result.values()), 'invalid statistic')
    require(integer(result['count']), 'invalid statistic count')
    return result


def public_counts(value):
    """Never recursively copy a source analysis: it can contain private fields."""
    result = {k:value[k] for k in SCALARS}
    require(all(numeric(v) for v in result.values()), 'invalid count')
    result['counts_by_status'] = {k:value['counts_by_status'][k] for k in STATUSES}
    total=result['total_cases']
    require(integer(total) and all(integer(v) and v<=total for v in result['counts_by_status'].values())
            and sum(result['counts_by_status'].values())==total, 'invalid public status cells')
    require(set(value['counts_by_split'])<= {'train','calibration','test'}, 'invalid public split')
    result['counts_by_split'] = {split:{k:group[k] for k in ('total_cases','scored_cases','passed_cases')}
                                for split,group in value['counts_by_split'].items()
                                if split in ('train','calibration','test')}
    for group in result['counts_by_split'].values():
        require(all(integer(v) and v<=total for v in group.values())
                and group['passed_cases']<=group['scored_cases']<=group['total_cases'], 'invalid public split cells')
    require(all(sum(g[key] for g in result['counts_by_split'].values())==result[key]
                for key in ('total_cases','scored_cases','passed_cases')), 'inconsistent public split cells')
    for key in ('latency','successful_latency'):
        result[key] = {field:stats(group) for field,group in value[key].items()
                       if field in ('adapter_duration_ms','decision_ms','inference_ms','http_ms')}
    result['per_response_resources'] = {key:stats(value['resources'][key])
                       for key in ('native_tokens','native_padded_tokens','rss_mib')}
    return result


def validate_counts(counts, total):
    require(type(total) is int and total>0 and counts['total_cases']==total, 'unexpected or zero denominator')
    for key in ('scored_cases','passed_cases','recorded_cases'):
        require(type(counts[key]) is int and 0<=counts[key]<=total, 'invalid count bounds')
    require(counts['passed_cases']<=counts['scored_cases'], 'passed exceeds scored')
    require(set(counts['counts_by_status'])==set(STATUSES), 'status membership')
    require(all(type(v) is int and v>=0 for v in counts['counts_by_status'].values())
            and sum(counts['counts_by_status'].values())==total, 'status denominator')
    require(counts['scored_cases']>0, 'zero scored cases cannot qualify a campaign')


def verify_seal(root, name, schema, *, exact=False):
    require(root.is_dir() and not root.is_symlink(), 'invalid archive root')
    seal_path=root/name
    require(seal_path.is_file() and not seal_path.is_symlink(), 'missing seal')
    seal=load(seal_path); require(seal.get('schema_version')==schema, 'seal schema')
    require(isinstance(seal.get('files'),dict) and bool(seal['files']), 'empty seal')
    for relative, expected in seal['files'].items():
        path=Path(relative)
        require(not path.is_absolute() and '..' not in path.parts and relative!=name, 'unsafe seal member')
        target=root/path
        require(target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(root.resolve()), 'invalid sealed file')
        require(re.fullmatch(r'[0-9a-f]{64}',expected) is not None and sha(target.read_bytes())==expected, 'sealed file changed')
    if exact:
        entries=list(root.rglob('*'))
        require(not any(p.is_symlink() for p in entries), 'symlink archive entry')
        require({str(p.relative_to(root)) for p in entries if p.is_file()}==set(seal['files'])|{name}, 'archive inventory changed')
    return sha(seal_path.read_bytes())


def paired_views(cases, score_rows, records, axis='catalogue'):
    """Closed paired tables; technical failures retain their own denominator."""
    scored={r['case_id']:r for r in score_rows}; raw={r['case_id']:r for r in records}
    grouped=defaultdict(dict)
    first,second = ('compact','expanded') if axis=='catalogue' else ('fr','en')
    strata = ('all','fr','en') if axis=='catalogue' else ('all','compact','expanded')
    for c in cases:
        variant=c['evaluation']['oracle']['params'].get('catalogue_variant')
        if variant in ('compact','expanded'):
            stratum = c['language'] if axis=='catalogue' else variant
            view = variant if axis=='catalogue' else c['language']
            grouped[(c['translation_family'],stratum,c['split'])][view]=c
    output=[]
    for split in ('all','train','calibration','test'):
        for stratum in strata:
            counts=Counter({k:0 for k in ('both_correct','first_only_correct','second_only_correct','neither_correct','any_unscored','both_valid_choices','same_choice','different_choice')})
            statuses=Counter(); total=0
            for (_,pair_stratum,part), pair in grouped.items():
                if (split!='all' and part!=split) or (stratum!='all' and pair_stratum!=stratum): continue
                require(set(pair)=={first,second}, 'incomplete planned pair')
                a,b=(scored[pair[v]['case_id']] for v in (first,second))
                total+=1; statuses[(a['status'],b['status'])]+=1
                if not a['scored'] or not b['scored']: counts['any_unscored']+=1
                else:
                    bucket=('both_correct' if a['passed'] and b['passed'] else 'first_only_correct' if a['passed'] else 'second_only_correct' if b['passed'] else 'neither_correct')
                    counts[bucket]+=1
                x,y=(raw.get(pair[v]['case_id'],{}) for v in (first,second))
                choices=[r.get('output',{}).get('choice_id') if isinstance(r.get('output'),dict) else None for r in (x,y)]
                if a['status']==b['status']=='ok' and all(c in 'abcd' if isinstance(c,str) and len(c)==1 else False for c in choices):
                    counts['both_valid_choices']+=1
                    counts['same_choice' if choices[0]==choices[1] else 'different_choice']+=1
            if total:
                output.append({'axis':axis,'split':split,'stratum':stratum,'first_view':first,'second_view':second,'total_pairs':total,**dict(counts),
                 'status_pairs':[{'first':a,'second':b,'pairs':n} for (a,b),n in sorted(statuses.items())]})
    return output


def family_groups(cases, rows):
    index={r['case_id']:r for r in rows}; groups=defaultdict(list)
    for c in cases: groups[c['translation_family']].append(c)
    out=[]
    for split in ('all','train','calibration','test'):
        families=[members for members in groups.values() if split=='all' or members[0]['split']==split]
        if not families: continue
        require(all(len({c['split'] for c in members})==1 for members in families), 'family split leakage')
        all_scored=sum(all(index[c['case_id']]['scored'] for c in members) for members in families)
        all_correct=sum(all(index[c['case_id']]['passed'] for c in members) for members in families)
        none_correct=sum(not any(index[c['case_id']]['passed'] for c in members) for members in families)
        out.append({'split':split,'families':len(families),'variants_per_family':sorted({len(x) for x in families}),
                    'all_scored':all_scored,'all_correct':all_correct,'none_correct':none_correct,
                    'some_correct':len(families)-all_correct-none_correct})
    return out


def backend_evidence(path):
    raw=path.read_bytes(); require(len(raw)<=16*1024*1024, 'engine log exceeds parser envelope')
    text=raw.decode('utf-8',errors='replace')
    offload=sorted({(int(a),int(b)) for a,b in re.findall(r'offloaded (\d+)/(\d+) layers to GPU',text)})
    values=lambda name:sorted(set(map(int,re.findall(r'\b'+name+r'\s*=\s*(\d+)',text))))
    return {'metal_initialization_observed':'ggml_metal' in text.lower(),
            'offloaded_layers':[{'offloaded':a,'total':b} for a,b in offload],
            'context_values':values(r'n_ctx(?:_per_seq)?'),'batch_values':values('n_batch'),
            'physical_batch_values':values('n_ubatch'),'log_sha256':sha(raw)}


def preparation_fingerprints(study):
    build=load(study/'native-build.json')
    source=Path(build['native_source']); native=Path(build['native_runtime_build'])
    dependencies=[]
    external=[]
    for name,digest in build['dependency_files_sha256'].items():
        require(isinstance(name,str) and hash_value(digest), 'invalid dependency fingerprint')
        path=Path(name)
        if path.is_relative_to(source):
            dependencies.append({'kind':'pinned_upstream_source','file':str(path.relative_to(source)),'sha256':digest})
        elif path.is_relative_to(native):
            dependencies.append({'kind':'native_build_input','file':str(path.relative_to(native)),'sha256':digest})
        elif path.name in ('systemone-preflight.cpp','build-systemone-preflight.py'):
            dependencies.append({'kind':'benchmark_helper_source','file':path.name,'sha256':digest})
        else:
            # Compiler/SDK paths are machine-local. Their opaque fingerprints suffice.
            external.append(digest)
    require(all(hash_value(build[key]) for key in ('helper_binary_sha256','helper_source_sha256','builder_sha256'))
            and build['native_revision']==NATIVE_PIN, 'invalid preparation fingerprints')
    return {'build_manifest_sha256':sha((study/'native-build.json').read_bytes()),
        'helper_binary_sha256':build['helper_binary_sha256'],
        'helper_source_sha256':build['helper_source_sha256'],'builder_sha256':build['builder_sha256'],
        'native_revision':build['native_revision'],
        'public_dependency_fingerprints':sorted(dependencies,key=lambda x:(x['kind'],x['file'])),
        'external_compiler_sdk_fingerprints':sorted(external)}


def preparation_summary(value):
    numbers=('request_count','within_limit','unsupported','errors','min_tokens','max_tokens','cases_scored')
    require(all(integer(value[key]) for key in numbers), 'invalid preparation counts')
    require(value['request_count']==value['within_limit']==324 and value['unsupported']==value['errors']==value['cases_scored']==0
            and 0<value['min_tokens']<=value['max_tokens']<=4096, 'preparation coverage differs')
    require(value['native_preparation_observed'] is True and value['live_forward_ids_compared'] is False,
            'invalid preparation scope')
    require(value['negative_control']=='native_prepare_overflow_refused', 'invalid preparation negative control')
    return {**{key:value[key] for key in numbers},'native_preparation_observed':True,
            'live_forward_ids_compared':False,'negative_control':'native_prepare_overflow_refused'}


def phase_export(bench, study, name, phase, output, prepared, package):
    campaigns,analyze_context,native_request=package
    require(re.fullmatch(phase+r'-\d{3}',name) is not None, 'invalid explicit phase name')
    root=study/name
    outer=verify_seal(root,'pilot-seal.json','deposium.native-pilot-seal/v1',exact=True)
    outer_files=load(root/'pilot-seal.json')['files']
    _,manifest,cases,records,parent,payloads=campaigns._archive(root/'campaign')
    total=12 if phase=='canary' else DATASETS[phase][1]
    require(len(cases)==total and parent['sealed'], 'phase denominator or seal')
    if phase!='canary':
        relative,_,expected=DATASETS[phase]
        require(payloads['cases.jsonl']==(bench/relative).read_bytes() and manifest['dataset_sha256']==expected, 'frozen dataset differs')
    else:
        require(payloads['cases.jsonl']==(study/'canary.jsonl').read_bytes() and all(c['split']=='calibration' for c in cases), 'canary differs')
    git=manifest['bench']['git']
    require(git['head']==HEAD and git['dirty'] is False, 'campaign code revision not frozen clean')
    require(manifest['qualification']=='model_isolated' and manifest['input_protocol']=='context_choice', 'campaign qualification')
    require(manifest['scorer']==campaigns._scorer_fingerprint(), 'scorer differs; explicit derived rescore required')
    session=load(root/'session.json'); model=session['model']; runtime=session['runtime']
    require(model['sha256']==MODEL_SHA and model['revision']=='3d53d13778bf8035e6e1e534ce489ed052ee5663'
            and model['repo_id']=='ggml-org/vllm-d3-flash-GGUF' and runtime['revision']==NATIVE_PIN, 'model/runtime binding')
    require(runtime['repository']=='https://github.com/ggml-org/llama.cpp.git'
            and all(hash_value(v) for v in (runtime['sha256'],session['gateway']['sha256'],session['harness']['sha256'],
                                            session['supervisor']['sha256'],session['runtime_pin']['sha256'])), 'invalid runtime fingerprints')
    require(load(root/'profile.json')['model']['session_sha256']==sha((root/'session.json').read_bytes()), 'session binding')
    require(session['settings']=={'context':4096,'parallel':1,'concurrency':1,'questions_per_call':1,
                                 'truncation':'reject_in_pinned_native_engine'},'session scope differs')
    analysis=analyze_context(root/'campaign',output/'private-analysis'/phase)
    validate_counts(analysis['counts'],total)
    require(analysis['dataset_sha256']==manifest['dataset_sha256'], 'analysis dataset differs')
    audit={'planned_cases':total,'recorded_cases':len(records),'unrecorded_cases':total-len(records),
           'http_attempted':0,'http_attempt_unknown':0,'cached_failures':0,'wire_matches':0,
           'wire_unreported':0,'native_count_matches':0,'native_count_unreported':0,
           'native_usage_truncation':{'true':0,'false':0,'unknown':0},
           'physical_forward':{'true':0,'false':0,'unknown':0},
           'live_forward_token_ids_compared':False}
    by_id={c['case_id']:c for c in cases}
    for record in records:
        raw=record.get('raw_output') or {}; key=record['case_id']
        if raw.get('http_attempted') is True:
            audit['http_attempted']+=1
            body,mapping,wire=native_request(by_id[key]['input'],'d3-flash-q8')
            require(raw.get('native_request')==body and raw.get('option_mapping')==mapping
                    and raw.get('request_body_sha256')==sha(wire)==prepared[key]['request_body_sha256'], 'wire differs from native preparation')
            audit['wire_matches']+=1
        elif raw.get('http_attempted') is None: audit['http_attempt_unknown']+=1
        if raw.get('request_body_sha256') is None: audit['wire_unreported']+=1
        audit['cached_failures']+=raw.get('cached_failure') is True
        usage=(raw.get('native_result') or {}).get('usage',{})
        if type(usage.get('input_tokens')) is int:
            require(usage['input_tokens']==prepared[key]['token_count'], 'live/native prepared count differs')
            audit['native_count_matches']+=1
        else: audit['native_count_unreported']+=1
        if record['status']=='ok':
            require(type(usage.get('input_tokens')) is int and raw.get('http_attempted') is True and usage.get('truncated') is not True, 'unqualified successful response')
        for value,target in ((usage.get('truncated'),'native_usage_truncation'),(raw.get('forward_executed'),'physical_forward')):
            audit[target]['true' if value is True else 'false' if value is False else 'unknown']+=1
    pilot=load(root/'pilot.json'); require(pilot['budget']['rss_guard_mib']==18432 and pilot['budget']['min_available_mib']==8192,'fixed guards changed')
    require(pilot['completed'] is True and type(pilot['gateway_exit_code']) is int and pilot['gateway_exit_code']==0
            and pilot['resources']['stop_reason'] is None
            and pilot['campaign_coverage']['technical_full_coverage'] is True
            and load(root/'campaign/summary.json')['completion_status']=='complete',
            'this exporter requires a technically complete phase, not an implicit PASS')
    require(all(type(pilot['resources'][key]) in (int,float) and numeric(pilot['resources'][key])
                for key in ('rss_peak_mib','min_available_mib'))
            and pilot['resources']['rss_peak_mib']<=18432 and pilot['resources']['min_available_mib']>=8192,
            'invalid session resource cells')
    require(type(pilot['budget']['sample_interval_seconds']) in (int,float)
            and pilot['budget']['sample_interval_seconds']==0.25, 'invalid resource sampling interval')
    backend=backend_evidence(root/'engine.log')
    require(runtime['backend_requested']=='metal' and backend['metal_initialization_observed']
            and {'offloaded':33,'total':33} in backend['offloaded_layers']
            and backend['context_values']==backend['batch_values']==backend['physical_batch_values']==[4096],
            'target Metal backend/context/batch not observed')
    identity={'model_repo_id':model['repo_id'],'model_revision':model['revision'],'model_sha256':model['sha256'],
              'runtime_repository':runtime['repository'],'runtime_revision':runtime['revision'],
              'runtime_binary_sha256':runtime['sha256'],'backend_requested':runtime['backend_requested'],
              'gateway_sha256':session['gateway']['sha256'],'launcher_sha256':session['harness']['sha256'],
              'supervisor_sha256':session['supervisor']['sha256'],
              'runtime_pin_sha256':session['runtime_pin']['sha256'],'settings':{k:session['settings'][k] for k in ('context','parallel','concurrency','questions_per_call','truncation')}}
    groups={axis:{key:public_counts(value) for key,value in analysis['groups'][axis].items()} for axis in AXES}
    tracks=defaultdict(list)
    for row in analysis['rows']:
        track=by_id[row['case_id']]['evaluation']['oracle']['params'].get('track')
        if track: tracks[track].append(row)
    # The common analyzer owns all count/scoring semantics, including technical states.
    from deposium_bench.context_analysis import _counts,_stats
    groups['track']={key:public_counts(_counts(rows)) for key,rows in sorted(tracks.items())}
    first=records[0] if records else None
    later=[r for r in records[1:] if r['status']=='ok']
    timing={'scope':'corpus calls after archived synthetic warm-up; fresh worker does not guarantee cold OS cache',
        'first_corpus_call':{'status':first['status'] if first else None,
            'adapter_ms':first['duration_ms'] if first else None,
            'http_ms':(first.get('raw_output') or {}).get('http_ms') if first else None},
        'successful_after_first':{'adapter_ms':stats(_stats([r['duration_ms'] for r in later])),
            'http_ms':stats(_stats([(r.get('raw_output') or {}).get('http_ms') for r in later]))},
        'adapter_initialization_ms':manifest['adapter_provenance'].get('init_wall_ms'),
        'native_startup_ms':None,'server_only_inference_ms':None,
        'unreported_timing_status':'null is unreported, never zero or a synthetic estimate'}
    require(numeric(timing['first_corpus_call']['http_ms']) and numeric(timing['adapter_initialization_ms']),
            'invalid first-call or initialization timing')
    return {'role':'technical_canary_no_quality_gate' if phase=='canary' else 'full_frozen_pack',
       'attempt':int(name.rsplit('-',1)[1]),'completion_status':load(root/'campaign/summary.json')['completion_status'],
       'counts':public_counts(analysis['counts']),'groups':groups,'identity':identity,'encoding_audit':audit,'timing':timing,
       'backend_evidence':backend,
       'session_resources':{'rss_peak_mib':pilot['resources']['rss_peak_mib'],'rss_scope':'sampled owned process-group peak over startup, synthetic smoke and this phase; not per-case or total unified GPU memory',
          'gpu_allocated_mib':None,'gpu_measurement_status':'not_reported','rss_guard_mib':18432,'reserve_mib':8192,
          'min_available_mib':pilot['resources']['min_available_mib'],
          'available_memory_method':'macos_free_inactive_speculative_estimate_not_linux_MemAvailable',
          'sampling_seconds':pilot['budget']['sample_interval_seconds'],'stop_reason':pilot['resources']['stop_reason'],
          'gateway_exit_code':pilot['gateway_exit_code']},
       'sources':{'dataset_sha256':manifest['dataset_sha256'],'manifest_sha256':parent['manifest_sha256'],
          'raw_sha256':parent['raw_sha256'],'campaign_seal_sha256':sha(payloads['seal.json']),
          'pilot_seal_sha256':outer,'scorer_sha256':manifest['scorer']['sha256'],'bench_head':HEAD,
          'bench_source_archive_sha256':outer_files['bench-source.tar'],
          'application_source_archive_sha256':outer_files['service-source.tar'],
          'reference_review':'agent_only_pending_human'},
       'paired_catalogue_views':paired_views(cases,analysis['rows'],records),
       'paired_language_views':paired_views(cases,analysis['rows'],records,axis='language'),
       'families':family_groups(cases,analysis['rows'])}


def csv_text(rows):
    if not rows: return ''
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);return s.getvalue()


def export(args):
    bench=args.bench_root.resolve(strict=True);study=args.study.resolve(strict=True);output=args.output.absolute()
    roots=[bench/'results',study.parent]
    require(not output.exists() and not output.is_symlink() and any(output.resolve().is_relative_to(r.resolve()) for r in roots),'output must be a new local results directory')
    require(not output.resolve().is_relative_to(study),'output must be outside original study')
    sys.path.insert(0,str(bench))
    from deposium_bench import campaigns
    from deposium_bench.context_analysis import analyze_context
    from deposium_bench.systemone_local import native_request
    prep_seal=verify_seal(study,'preparation-seal.json','deposium.preparation-seal/v1')
    inputs=load(study/'inputs.json');require(inputs['bench_head']==HEAD and inputs['model_sha256']==MODEL_SHA,'preparation identity')
    prepared=load(study/'prepared-index.json')
    require(len(prepared)==324 and all(0<v['token_count']<=4096 for v in prepared.values()),'prepared roster')
    require(sha((study/'canary.jsonl').read_bytes())==inputs['canary_sha256'],'canary hash')
    for phase,(relative,total,digest) in DATASETS.items():
        require(sha((bench/relative).read_bytes())==digest,'published dataset changed')
    for phase,name in [('canary',args.canary),('anchor',args.anchor),('capability',args.capability)]:
        verify_seal(study/name,'pilot-seal.json','deposium.native-pilot-seal/v1',exact=True)
    output.mkdir(parents=True)
    package=(campaigns,analyze_context,native_request)
    phases={phase:phase_export(bench,study,name,phase,output,prepared,package)
            for phase,name in [('canary',args.canary),('anchor',args.anchor),('capability',args.capability)]}
    attempts=[]
    for path in sorted(study.glob('*.result.json')):
        item=load(path)
        if item.get('execution_status')=='failed_before_sealed_archive':
            require(item.get('cases_scored')==0,'unsealed attempt cannot carry score')
            require(item.get('phase') in ('canary','anchor','capability') and type(item.get('attempt')) is int,'invalid attempt')
            name=f"{item['phase']}-{item['attempt']:03d}"
            log=study/(name+'.launch.log')
            require(not (study/name).exists() and log.is_file()
                    and 'native_pilot_insufficient_available_memory_before_start' in log.read_text(),
                    'unsealed attempt needs separate inference/coverage review')
            attempts.append({**{key:item[key] for key in ('phase','attempt','execution_status','launcher_exit_code','technical_gate_passed','cases_scored')},
                             'reason':'memory_admission_refused_before_service_start','inference_run':False,
                             'launch_trace_sha256':sha(log.read_bytes()),'result_sha256':sha(path.read_bytes())})
    result={'schema_version':'deposium.capability-flash-results/v1','scope':'isolated_frozen_closed_choice_observations',
       'reference_review':'synthetic_agent_authored_pending_human_review','phases':phases,'prior_unstarted_attempts':attempts,
       'native_preparation':preparation_summary(load(study/'preparation-summary.json')),
       'preparation_seal_sha256':prep_seal,'preparation_fingerprints':preparation_fingerprints(study),
       'aggregate_producer_sha256':sha(Path(__file__).read_bytes()),
       'limitations':['Agent-authored references and translations await independent human review.',
        'Closed choice among four proposals; no tools, executable argument validation, full agent loop or product journey.',
        'A perfect result on these fixtures may indicate a ceiling effect; it does not establish general plugin-selection competence.',
        'All-split totals include train/calibration/test; report old test/66 and new test/96 separately.',
        'Forty-eight new-pack families underlie 192 correlated language/catalogue variants; no post-hoc confidence interval is fitted.',
        'Paired choice agreement differs from correctness; pairs with unscored variants retain their denominator.',
        'Prepared token counts matching live usage do not compare live-forward token IDs; unknown flags remain unknown.',
        'Native session RSS is sampled and does not measure all unified GPU memory; missing GPU allocation is not zero.',
        'Fresh workers can inherit warmed operating-system file caches; latency is not guaranteed production latency.']}
    groups=[];pairs=[];families=[]
    for phase,item in phases.items():
        for axis,values in item['groups'].items():
            for key,c in values.items():
                cells={f'{split}_{metric}':c['counts_by_split'].get(split,{}).get(field)
                    for split in ('train','calibration','test')
                    for metric,field in [('correct','passed_cases'),('scored','scored_cases'),('total','total_cases')]}
                groups.append({'phase':phase,'axis':axis,'group':key,'correct':c['passed_cases'],'scored':c['scored_cases'],'total':c['total_cases'],'families':c['independent_families'],**c['counts_by_status'],**cells})
        for pair in item['paired_catalogue_views']+item['paired_language_views']:
            pairs.append({'phase':phase,**{k:v for k,v in pair.items() if k!='status_pairs'}})
        for family in item['families']:
            families.append({'phase':phase,**{k:(','.join(map(str,v)) if k=='variants_per_family' else v) for k,v in family.items()}})
    public=output/'public-review';public.mkdir()
    (public/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    for name,rows in [('groups.csv',groups),('paired-variants.csv',pairs),('families.csv',families)]:
        (public/name).write_text(csv_text(rows))
    return {'status':'private_aggregate_review_ready','counts':{phase:item['counts']['passed_cases'] for phase,item in phases.items()}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bench-root',type=Path,required=True);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--canary',default='canary-001');p.add_argument('--anchor',default='anchor-002');p.add_argument('--capability',default='capability-001')
    args=p.parse_args()
    try: print(json.dumps(export(args),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError):
        print('Aggregate export refused; preserve original archives and inspect integrity/source compatibility.',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
