#!/usr/bin/env python3
"""Export reviewed aggregates from a sealed local tool-policy canary; no inference.

Only allowlisted counts, public model/runtime identities and aggregate resource
evidence leave the private archive. Raw generations, templates, local paths and
HTTP bodies are never copied.
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

DATASET_SHA = '6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d'
STATUSES = ('ok', 'unsupported', 'missing', 'error', 'timeout', 'abstain')
CONTROLS = {'authenticated_props': 200, 'unauthenticated_chat': 401, 'chat_json_warmup': 200,
            'unknown_request_model_diagnostic': 200, 'oversized_chat_context': 400}
TASKS = {'bench.tool-discovery': 'discovery', 'bench.tool-arguments': 'arguments',
         'bench.tool-episode': 'episodes'}
PACK_CASES = {'discovery': 2, 'arguments': 2, 'episodes': 6}
EPISODE_STAGES = ('tool', 'arguments', 'binding', 'execution', 'result', 'stopping', 'budget')


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


def export(root):
    pilot_seal = verify_seal(root, 'pilot-seal.json', 'deposium.native-pilot-seal/v1')
    campaign_seal = verify_seal(root / 'campaign', 'seal.json', 'deposium.archive-seal/v1')
    pilot = load(root / 'pilot.json')
    summary = load(root / 'campaign' / 'summary.json')
    metrics = summary['metrics']
    records = [json.loads(line) for line in (root / 'campaign' / 'raw.jsonl').read_text().splitlines()]

    require(pilot['schema_version'] == 'deposium.local-tool-policy-pilot/v1'
            and pilot['outer_sealed'] is True and pilot['owned_process_terminated'] is True
            and pilot['resource_writer_closed'] is True and pilot['weight_verification'] == 'verified'
            and pilot['dataset']['sha256'] == DATASET_SHA, 'pilot receipt is not a closed, verified run')
    require(pilot['technical_controls_in_quality_denominator'] is False
            and pilot['native_request_alias_enforcement'] is False, 'unexpected control semantics')
    require(summary['completion_status'] == 'complete' and summary['mode'] == 'run'
            and summary['qualification'] == 'model_isolated', 'campaign is not a complete isolated run')
    total = count(metrics['total_cases'])
    require(total == 10 == len(records) and metrics['scored_cases'] > 0, 'unexpected or zero denominator')
    statuses = {k: count(metrics['counts_by_status'][k], total) for k in STATUSES}
    require(sum(statuses.values()) == total, 'status denominator')
    require(count(metrics['passed_cases'], metrics['scored_cases']) + metrics['failed_cases'] == metrics['scored_cases'],
            'inconsistent pass counts')

    controls = {c['name']: c['http_status'] for c in pilot['technical_controls']}
    require(controls == CONTROLS and not any(c['response_redacted'] for c in pilot['technical_controls']),
            'technical controls differ from the fixed protocol')
    backend = pilot['actual_backend']
    require(backend['kind'] == 'metal' and backend['offloaded_layers'] == backend['total_layers'] > 0,
            'Metal did not offload every layer')
    resources = pilot['resources']
    require(resources['stop_reason'] is None and resources['rss_peak_mib'] <= pilot['envelope']['rss_limit_mib'],
            'resource stop or ceiling exceeded')

    by_task = {}
    for row in metrics['rows']:
        task = next(name for prefix, name in (('tp001', 'discovery'), ('tp002', 'arguments'),
                                              ('tp003', 'episodes'), ('tp004', 'episodes'),
                                              ('tp005', 'episodes')) if row['case_id'].startswith(prefix))
        group = by_task.setdefault(task, [0, 0])
        group[0] += 1 if row['passed'] else 0
        group[1] += 1
    require({k: v[1] for k, v in by_task.items()} == PACK_CASES, 'unexpected family composition')

    episode = metrics['task_metrics']['bench.tool-episode']
    discovery = metrics['task_metrics']['bench.tool-discovery']
    arguments = metrics['task_metrics']['bench.tool-arguments']
    stages = {name: cell(episode[f'{name}_correct_cases'], episode[f'{name}_eligible_cases'])
              for name in EPISODE_STAGES}
    result = {
        'schema_version': 'deposium.local-tool-policy-results/v1',
        'report_date': '2026-10-30',
        'evaluation_status': 'train_canary_collected_quality_fail',
        'qualification': 'model_isolated_generated_json_train_canary',
        'review': 'agent_only_pending_human',
        'dataset': {'id': 'tool-policy-canary-v1', 'sha256': DATASET_SHA, 'cases': total,
                    'families': pilot['dataset']['train_families'], 'splits': {'train': total}},
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
                     'collection_complete': pilot['collection_complete']},
        'results': {
            'overall': cell(metrics['passed_cases'], metrics['scored_cases']),
            'by_language': {lang: cell(g['passed_cases'], g['scored_cases'])
                            for lang, g in sorted(metrics['by_language'].items())},
            'by_task': {name: cell(*by_task[name]) for name in PACK_CASES},
            'discovery': {'eligible_select_cases': discovery['eligible_select_cases'],
                          'valid_select_observations': discovery['observed_select_cases'],
                          'shortlist_recall_sum': discovery['shortlist_recall_sum'],
                          'final_sufficient': cell(discovery['final_sufficient_cases'], discovery['eligible_select_cases']),
                          'final_minimal': cell(discovery['final_minimal_cases'], discovery['eligible_select_cases'])},
            'arguments': {name: cell(arguments[f'{name}_correct_cases'], arguments['eligible_cases'])
                          for name in ('tool', 'arguments', 'binding', 'execution', 'result')},
            'episodes': {'stages': stages, 'procedure': cell(episode['procedure_correct_cases'], episode['eligible_cases']),
                         'task_success': {'correct': episode['task_success_cases'],
                                          'eligible': episode['task_success_eligible_cases'],
                                          'over_all_cases': episode['eligible_cases']},
                         'policy_steps_observed': episode['policy_steps_observed'],
                         'tool_call_attempts_observed': episode['tool_call_attempts_observed'],
                         'tool_calls_observed': episode['tool_calls_observed']},
        },
        'resources': {'rss_peak_mib': round(resources['rss_peak_mib'], 1),
                      'min_available_mib': round(resources['min_available_mib'], 1),
                      'available_before_mib': round(pilot['memory_before']['MemAvailable_mib'], 1),
                      'available_after_mib': round(pilot['memory_after']['MemAvailable_mib'], 1),
                      'case_duration_ms': milliseconds([r['duration_ms'] for r in records]),
                      'host': {'platform': 'macOS arm64', 'memory_total_mib': pilot['memory_before']['MemTotal_mib']}},
        'seals': {'pilot_seal_sha256': pilot_seal, 'campaign_seal_sha256': campaign_seal,
                  'raw_sha256': summary['raw_sha256']},
        'aggregate_producer_sha256': sha(Path(__file__).read_bytes()),
        'limitations': [
            'Ten TRAIN cases in five families; five FR/EN pairs are correlated and no held-out claim is made.',
            'Agent-authored references await independent human review; a failure here is not a reference change.',
            'One model, one runtime and one device; no ranking, classifier-cohort comparison or product claim.',
            'Native request-alias enforcement is absent in the pinned server; fixed client and file/session identity guard it.',
            'Requested JSON schema is not proof of grammar enforcement; generated JSON is scored without repair.',
            'Sampled RSS is not a unified-memory cap; available memory is a reclaimable-page estimate.',
            'Single pass at temperature 0: descriptive latency only, not a production tail guarantee.',
            'Synthetic lookup/sum tools only; no live MCP, application replay or answer quality.'],
    }
    return result


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
        print(json.dumps({'status': 'aggregate_written', 'passed': document['coverage']['passed_cases'],
                          'scored': document['coverage']['scored_cases']}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        print('Aggregate export refused; preserve the original archive and inspect integrity.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
