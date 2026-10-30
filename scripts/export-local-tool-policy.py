#!/usr/bin/env python3
"""Export reviewed aggregates from a sealed local tool-policy archive; no inference.

Accepts the TRAIN canary and the held-out pack, both launcher receipt layouts
and a partial collection stopped by a resource guard. Only allowlisted counts,
public model/runtime identities and aggregate resource evidence leave the
private archive. Raw generations, templates, local paths and HTTP bodies are
never copied. Unobserved cases stay in every denominator.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

DATASETS = {'6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d': 'tool-policy-canary-v1',
            '7f7ed8f08fe15d5b897744fe71f2a5ed76344b5ccd7a0df43492b2dc3371bac7': 'tool-policy-heldout-v1'}
STATUSES = ('ok', 'unsupported', 'missing', 'error', 'timeout', 'abstain')
CONTROLS = {'authenticated_props': 200, 'unauthenticated_chat': 401, 'chat_json_warmup': 200,
            'unknown_request_model_diagnostic': 200, 'oversized_chat_context': 400}
TASKS = {'bench.tool-discovery': 'discovery', 'bench.tool-arguments': 'arguments',
         'bench.tool-episode': 'episodes'}
PROMPTS = ('deposium.local-tool-policy-prompt/v1', 'deposium.local-tool-policy-prompt/v2')
EPISODE_STAGES = ('tool', 'arguments', 'binding', 'execution', 'result', 'stopping', 'budget')
ARGUMENT_STAGES = ('tool', 'arguments', 'binding', 'execution', 'result')
STOP_REASONS = (None, 'rss_guard', 'host_reserve', 'time_limit', 'native_supervision_lost', 'resource_observation_failed')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def verify_seal(root, name, schema):
    require(root.is_dir() and not root.is_symlink(), 'invalid archive root')
    path = root / name
    require(path.is_file() and not path.is_symlink(), 'missing seal')
    seal = load(path)
    require(seal.get('schema_version') == schema and isinstance(seal.get('files'), dict)
            and bool(seal['files']), 'seal schema')
    for relative, expected in seal['files'].items():
        member = Path(relative)
        require(not member.is_absolute() and '..' not in member.parts and relative != name,
                'unsafe seal member')
        target = root / member
        require(target.is_file() and not target.is_symlink()
                and target.resolve().is_relative_to(root.resolve()), 'invalid sealed file')
        require(re.fullmatch(r'[0-9a-f]{64}', expected) is not None
                and sha(target.read_bytes()) == expected, 'sealed file changed')
    return sha(path.read_bytes())


def count(value, total=None):
    require(type(value) is int and value >= 0 and (total is None or value <= total), 'invalid count')
    return value


def cell(passed, eligible):
    return {'correct': count(passed, eligible), 'eligible': count(eligible)}


def milliseconds(values):
    require(values and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values),
            'invalid duration')
    ordered = sorted(values)
    return {'count': len(ordered), 'min': round(ordered[0], 1), 'median': round(statistics.median(ordered), 1),
            'max': round(ordered[-1], 1), 'sum': round(sum(ordered), 1)}


def dataset_identity(dataset, cases):
    """Public dataset identity from either receipt layout, cross-checked against the sealed cases."""
    sha256 = dataset.get('sha256')
    require(sha256 in DATASETS, 'unknown dataset identity')
    total = count(dataset['cases'])
    require(total == len(cases) > 0, 'receipt case count differs from sealed cases')
    if 'train_families' in dataset:
        families, splits = count(dataset['train_families']), {'train': total, 'calibration': 0, 'test': 0}
    else:
        families, splits = count(dataset['families']), dataset['counts_by_split']
    actual = {s: sum(c['split'] == s for c in cases) for s in ('train', 'calibration', 'test')}
    require(actual == splits and sum(splits.values()) == total
            and len({c['translation_family'] for c in cases}) == families, 'receipt inventory differs from sealed cases')
    split = next(s for s, n in splits.items() if n == total)
    return {'id': DATASETS[sha256], 'sha256': sha256, 'cases': total, 'families': families, 'splits': splits}, split


def export(root):
    pilot_seal = verify_seal(root, 'pilot-seal.json', 'deposium.native-pilot-seal/v1')
    campaign_seal = verify_seal(root / 'campaign', 'seal.json', 'deposium.archive-seal/v1')
    pilot = load(root / 'pilot.json')
    summary = load(root / 'campaign' / 'summary.json')
    profile = load(root / 'campaign' / 'profile.json')
    metrics = summary['metrics']
    cases = [json.loads(line) for line in (root / 'campaign' / 'cases.jsonl').read_text().splitlines()]
    records = [json.loads(line) for line in (root / 'campaign' / 'raw.jsonl').read_text().splitlines()]

    require(pilot['schema_version'] == 'deposium.local-tool-policy-pilot/v1'
            and pilot['outer_sealed'] is True and pilot['owned_process_terminated'] is True
            and pilot['resource_writer_closed'] is True and pilot['weight_verification'] == 'verified',
            'pilot receipt is not a closed, verified run')
    require(pilot['technical_controls_in_quality_denominator'] is False
            and pilot['native_request_alias_enforcement'] is False, 'unexpected control semantics')
    dataset, split = dataset_identity(pilot['dataset'], cases)
    require(sha((root / 'campaign' / 'cases.jsonl').read_bytes()) == dataset['sha256'], 'sealed cases differ from receipt')
    prompt = pilot.get('prompt_version') or profile['model']['prompt_version']
    require(prompt in PROMPTS and profile['model']['prompt_version'] == prompt, 'unknown or inconsistent prompt version')

    total = dataset['cases']
    require(metrics['total_cases'] == total and metrics['scored_cases'] > 0, 'unexpected or zero denominator')
    statuses = {k: count(metrics['counts_by_status'][k], total) for k in STATUSES}
    require(sum(statuses.values()) == total, 'status denominator')
    # A case the session never reached has no raw record; it is counted as missing, never dropped.
    require(len(records) + statuses['missing'] == total
            and {r['case_id'] for r in records} <= {c['case_id'] for c in cases}, 'raw records do not match the pack')
    require(count(metrics['passed_cases'], metrics['scored_cases']) + metrics['failed_cases'] == metrics['scored_cases'],
            'inconsistent pass counts')
    stop_reason = pilot['resources']['stop_reason']
    require(stop_reason in STOP_REASONS, 'unknown stop reason')
    collected = pilot['collection_complete'] is True
    if collected:
        require(summary['completion_status'] == 'complete' and stop_reason is None
                and statuses['missing'] == 0 and pilot['status'] == 'collected', 'complete collection with gaps')
    else:
        require(summary['completion_status'] != 'complete' and pilot['status'] == 'partial'
                and (statuses['missing'] + statuses['error'] + statuses['timeout']) > 0, 'partial collection without gaps')
    require(summary['mode'] == 'run' and summary['qualification'] == 'model_isolated', 'not an isolated run')

    controls = {c['name']: c['http_status'] for c in pilot['technical_controls']}
    require(controls == CONTROLS and not any(c['response_redacted'] for c in pilot['technical_controls']),
            'technical controls differ from the fixed protocol')
    backend = pilot['actual_backend']
    require(backend['kind'] == 'metal' and backend['offloaded_layers'] == backend['total_layers'] > 0,
            'Metal did not offload every layer')
    resources = pilot['resources']
    limit = pilot['envelope']['rss_limit_mib']
    require(resources['rss_peak_mib'] <= limit or stop_reason == 'rss_guard', 'RSS ceiling exceeded without a guard stop')
    require(resources['min_available_mib'] >= pilot['envelope']['reserve_mib'] or stop_reason == 'host_reserve',
            'host reserve breached without a guard stop')

    contract_of = {c['case_id']: TASKS[c['contract_id']] for c in cases}
    by_task = {name: [0, 0, 0] for name in TASKS.values()}  # correct, scored, eligible
    unobserved = []
    for row in metrics['rows']:
        task = contract_of[row['case_id']]
        by_task[task][2] += 1
        by_task[task][1] += 1 if row['scored'] else 0
        by_task[task][0] += 1 if row['passed'] else 0
        if row['status'] != 'ok':
            unobserved.append({'case_id': row['case_id'], 'status': row['status']})
    require(sum(v[2] for v in by_task.values()) == total and sum(v[1] for v in by_task.values()) == metrics['scored_cases']
            and sum(v[0] for v in by_task.values()) == metrics['passed_cases'], 'task cells do not partition the pack')
    by_task = {k: v for k, v in by_task.items() if v[2]}

    task_metrics = metrics['task_metrics']
    results = {
        'overall': {**cell(metrics['passed_cases'], metrics['scored_cases']), 'eligible_all': total},
        'by_language': {lang: {**cell(g['passed_cases'], g['scored_cases']), 'eligible_all': g['total_cases']}
                        for lang, g in sorted(metrics['by_language'].items())},
        'by_task': {name: {'correct': v[0], 'scored': v[1], 'eligible': v[2]} for name, v in by_task.items()},
    }
    if 'discovery' in by_task:
        d = task_metrics['bench.tool-discovery']
        results['discovery'] = {'eligible_select_cases': d['eligible_select_cases'],
                                'valid_select_observations': d['observed_select_cases'],
                                'shortlist_recall_sum': d['shortlist_recall_sum'],
                                'final_sufficient': cell(d['final_sufficient_cases'], d['eligible_select_cases']),
                                'final_minimal': cell(d['final_minimal_cases'], d['eligible_select_cases'])}
    if 'arguments' in by_task:
        a = task_metrics['bench.tool-arguments']
        results['arguments'] = {name: cell(a[f'{name}_correct_cases'], a['eligible_cases']) for name in ARGUMENT_STAGES}
    if 'episodes' in by_task:
        e = task_metrics['bench.tool-episode']
        results['episodes'] = {'stages': {name: cell(e[f'{name}_correct_cases'], e[f'{name}_eligible_cases'])
                                          for name in EPISODE_STAGES},
                               'procedure': cell(e['procedure_correct_cases'], e['eligible_cases']),
                               'task_success': {'correct': e['task_success_cases'],
                                                'eligible': e['task_success_eligible_cases'],
                                                'over_all_cases': e['eligible_cases']},
                               'policy_steps_observed': e['policy_steps_observed'],
                               'tool_call_attempts_observed': e['tool_call_attempts_observed'],
                               'tool_calls_observed': e['tool_calls_observed']}

    observed = [r['duration_ms'] for r in records if r.get('status') != 'missing']
    verdict = summary['metrics']['verdict']
    return {
        'schema_version': 'deposium.local-tool-policy-results/v1',
        'report_date': pilot['created_at'][:10],
        'evaluation_status': f"{split}_{'collected' if collected else 'partial'}_quality_{verdict}",
        'qualification': f'model_isolated_generated_json_{split}',
        'review': 'agent_only_pending_human',
        'dataset': dataset,
        'prompt_version': prompt,
        'model': {'repo_id': pilot['model_assets']['repo_id'], 'revision': pilot['model_assets']['revision'],
                  'file': pilot['model_assets']['files'][0]['path'], 'size': pilot['model_assets']['files'][0]['size'],
                  'sha256': pilot['model_assets']['files'][0]['sha256']},
        'runtime': {'repository': pilot['runtime']['repository'], 'revision': pilot['runtime']['revision'],
                    'binary_sha256': pilot['runtime']['binary_sha256'], 'backend': backend,
                    'chat_template_sha256': sha((root / 'chat-template.jinja').read_bytes())},
        'envelope': pilot['envelope'],
        'technical_controls': {'http_statuses': controls, 'native_request_alias_enforcement': False,
                               'counted_as_benchmark_predictions': False},
        'coverage': {'eligible_cases': total, 'scored_cases': metrics['scored_cases'],
                     'passed_cases': metrics['passed_cases'], 'counts_by_status': statuses,
                     'collection_complete': collected, 'stop_reason': stop_reason,
                     'unobserved_cases': unobserved},
        'results': results,
        'resources': {'rss_peak_mib': round(resources['rss_peak_mib'], 1), 'rss_limit_mib': limit,
                      'min_available_mib': round(resources['min_available_mib'], 1),
                      'available_before_mib': round(pilot['memory_before']['MemAvailable_mib'], 1),
                      'available_after_mib': round(pilot['memory_after']['MemAvailable_mib'], 1),
                      'case_duration_ms': milliseconds(observed),
                      'host': {'platform': 'macOS arm64', 'memory_total_mib': pilot['memory_before']['MemTotal_mib']}},
        'seals': {'pilot_seal_sha256': pilot_seal, 'campaign_seal_sha256': campaign_seal,
                  'raw_sha256': summary['raw_sha256']},
        'aggregate_producer_sha256': sha(Path(__file__).read_bytes()),
        'limitations': [
            'Correlated FR/EN pairs from one model, one runtime and one device; no ranking or classifier-cohort comparison.',
            'Agent-authored references await independent human review; a failure here is not a reference change.',
            'Unobserved (missing, error, timeout) cases stay in every eligible denominator and contribute zero.',
            'A resource-guard stop is an envelope outcome of the pinned runtime, not a model quality result.',
            'Native request-alias enforcement is absent in the pinned server; fixed client and file/session identity guard it.',
            'Requested JSON schema is not proof of grammar enforcement; generated JSON is scored without repair.',
            'Sampled RSS is not a unified-memory cap; available memory is a reclaimable-page estimate.',
            'Single pass at temperature 0: descriptive latency only, not a production tail guarantee.',
            'Synthetic lookup/sum tools only; no live MCP, application replay or answer quality.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        document = export(args.archive)
        require(not args.output.exists(), 'refusing to overwrite an existing aggregate')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2,
                                          allow_nan=False) + '\n')
        print(json.dumps({'status': 'aggregate_written', 'evaluation_status': document['evaluation_status'],
                          'passed': document['coverage']['passed_cases'], 'scored': document['coverage']['scored_cases'],
                          'eligible': document['coverage']['eligible_cases']}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        print('Aggregate export refused; preserve the original archive and inspect integrity.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
