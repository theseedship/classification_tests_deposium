#!/usr/bin/env python3
"""PRIVATE descriptive report from sealed harness evidence; no inference.

This derived view deliberately does not relax campaigns.compare qualification.
Synthetic tests exercise accounting only, never a real model campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deposium_bench import campaigns
from deposium_bench.chat_intent_v2_corpus import (INTENTS, LETTERS, CARDS_PATH,
                                               POLICY_ID, validate_oracle)
from deposium_bench.scoring import summarize
from deposium_bench.cases import parse_cases


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def load_archive(path, role):
    """Use the official integrity/profile/request validator, then narrow scope."""
    _, manifest, cases, records, parent, payloads = campaigns._archive(path)
    if not parent['sealed']:
        raise ValueError('Report requires a sealed archive')
    profile = json.loads(payloads['profile.json'])
    if manifest['qualification'] != profile['qualification']:
        raise ValueError('Manifest/profile qualification mismatch')
    if role == 'baseline':
        if (profile['adapter'] != 'recorded' or manifest['qualification'] != 'harness_control'
                or manifest['input_protocol'] != 'recorded_control'):
            raise ValueError('Baseline requires an explicit recorded harness control')
    elif role == 'candidate':
        if (profile['adapter'] in {'recorded', 'fixture_arguments', 'fixture_episode'}
                or manifest['qualification'] != 'model_isolated'
                or manifest['input_protocol'] != 'context_choice'):
            raise ValueError('Candidate requires an actual context-choice model campaign')
    else:
        raise ValueError('Unknown archive role')
    for case in cases:
        validate_oracle(case)
    return {'manifest': manifest, 'cases': cases, 'records': records,
            'hashes': {name: digest(data) for name, data in payloads.items()},
            'profile': profile}


def paired_cases(baseline, candidate):
    """Allow an exact owner subset; reject unknown or changed case/reference/input."""
    source = {case['case_id']: case for case in baseline}
    if not candidate:
        raise ValueError('Empty candidate comparison')
    for case in candidate:
        if case['case_id'] not in source or canonical(case) != canonical(source[case['case_id']]):
            raise ValueError('Candidate cases differ from frozen baseline cases')
    return candidate


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = math.floor(position)
    hi = math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def aggregate_metrics(cases, records):
    """Derive descriptive classification counts from the shared exact scorer."""
    ids = {case['case_id'] for case in cases}
    selected = [record for record in records if record['case_id'] in ids]
    if not cases:
        return {'total_cases': 0, 'accuracy_over_all': None, 'macro_f1_supported': None}
    shared = summarize(cases, selected)
    indexed = {record['case_id']: record for record in selected}
    confusion = [[0] * (len(INTENTS) + 1) for _ in INTENTS]
    invalid = 0
    for case in cases:
        actual = LETTERS.index(case['reference']['assertions'][0]['value'])
        result = indexed.get(case['case_id'], {})
        output = result.get('output')
        choice = output.get('choice_id') if isinstance(output, dict) else None
        valid = result.get('status') == 'ok' and isinstance(choice, str) and choice in LETTERS and len(choice) == 1
        predicted = LETTERS.index(choice) if valid else len(INTENTS)
        invalid += result.get('status') == 'ok' and not valid
        confusion[actual][predicted] += 1
    classes = {}
    for i, label in enumerate(INTENTS):
        support = sum(confusion[i])
        predicted = sum(row[i] for row in confusion)
        tp = confusion[i][i]
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        f1 = 2 * tp / (support + predicted) if support else None
        classes[label] = {'support': support, 'predicted_count': predicted,
                          'precision': precision, 'recall': recall, 'f1': f1}
    supported = [value['f1'] for value in classes.values() if value['support']]
    connector = INTENTS.index('connector_search')
    positives = classes['connector_search']['support']
    durations = [r['duration_ms'] for r in selected if isinstance(r.get('duration_ms'), (int, float))
                 and not isinstance(r['duration_ms'], bool) and math.isfinite(r['duration_ms']) and r['duration_ms'] >= 0]
    return {key: value for key, value in shared.items() if key not in {'rows', 'by_pack', 'by_language'}} | {
        'invalid_outputs': invalid, 'per_label': classes,
        'macro_f1_supported': sum(supported) / len(supported) if supported else None,
        'confusion': {'rows': list(INTENTS), 'columns': [*INTENTS, 'invalid_or_failure'], 'counts': confusion},
        'connector_search': {'positive_support': positives, 'negative_support': len(cases) - positives,
                             'false_positives': sum(row[connector] for i, row in enumerate(confusion) if i != connector),
                             'recall': classes['connector_search']['recall']},
        'latency': {'observed_calls': len(durations), 'missing_calls': len(cases) - len(durations),
                    'p50_ms': percentile(durations, .5), 'p95_ms': percentile(durations, .95),
                    'scope': 'harness duration_ms wall time including adapter/transport; not isolated model timing'}}


def split_metrics(cases, records):
    return {split: aggregate_metrics([c for c in cases if split == 'all' or c['split'] == split], records)
            for split in ('test', 'calibration', 'all')}


def groups_metrics(cases, records):
    report = {}
    for dimension in ('tier_used', 'source_environment', 'source', 'split_group_id', 'day'):
        grouped = {}
        for case in cases:
            value = case['evaluation']['oracle']['params'].get(dimension)
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
            grouped.setdefault(key, []).append(case)
        # JSON is private and may contain private grouping metadata; Markdown omits it.
        report[dimension] = {key: aggregate_metrics(group, records) for key, group in sorted(grouped.items())}
    return report


def paired_metrics(cases, baseline_records, candidate_records):
    ids = {c['case_id'] for c in cases}
    if not cases:
        return {'common_case_denominator': 0, 'corrected': 0, 'introduced': 0,
                'both_correct': 0, 'both_wrong': 0}
    left = summarize(cases, [r for r in baseline_records if r['case_id'] in ids])['rows']
    right = summarize(cases, [r for r in candidate_records if r['case_id'] in ids])['rows']
    result = {'common_case_denominator': len(cases), 'corrected': 0, 'introduced': 0,
              'both_correct': 0, 'both_wrong': 0}
    for a, b in zip(left, right):
        key = ('both_correct' if a['passed'] and b['passed'] else
               'introduced' if a['passed'] else 'corrected' if b['passed'] else 'both_wrong')
        result[key] += 1
    return result


def build_report(baseline, candidates):
    report = {'schema_version': 'deposium.private-chat-intent-v2-report/v1',
              'qualification': 'descriptive_historical_label_comparison',
              'policy_id': POLICY_ID, 'cards_sha256': digest(CARDS_PATH.read_bytes()),
              'baseline': {'kind': 'recorded_historical_labels_harness_control',
                           'hashes': baseline['hashes'],
                           'metrics': split_metrics(baseline['cases'], baseline['records']),
                           'groups': groups_metrics(baseline['cases'], baseline['records']),
                           'latency_qualification': 'recorded replay timing; never production router latency'},
              'candidate_status': 'observed' if candidates else 'not_run', 'candidates': {},
              'go': False,
              'limitations': ['Accuracy improvement does not establish downstream answer quality.',
                              'Language gate unverified: case.language describes prompt language; message language is not annotated.',
                              'Descriptive one-pass harness latency is not a production tail guarantee.',
                              'CUDA gate requires independent observed launcher/device evidence; profile declarations are insufficient.',
                              'Hashes identify bytes, not annotation truth or independent producer authenticity.']}
    for label, candidate in candidates.items():
        cases = paired_cases(baseline['cases'], candidate['cases'])
        metrics = split_metrics(cases, candidate['records'])
        baseline_common = split_metrics(cases, baseline['records'])
        test = [c for c in cases if c['split'] == 'test']
        accuracy = metrics['test']['accuracy_over_all']
        prior = baseline_common['test']['accuracy_over_all']
        p95 = metrics['test'].get('latency', {}).get('p95_ms')
        report['candidates'][label] = {'kind': 'actual_candidate_scores', 'hashes': candidate['hashes'],
            'metrics': metrics, 'baseline_common_metrics': baseline_common,
            'groups': groups_metrics(cases, candidate['records']),
            'paired': {split: paired_metrics([c for c in cases if split == 'all' or c['split'] == split], baseline['records'], candidate['records'])
                       for split in ('test', 'calibration', 'all')},
            'gates': {'same_test_accuracy_at_least_baseline': accuracy >= prior if test else None,
                      'observed_test_p95_below_500_ms': p95 < 500 if p95 is not None else None,
                      'actual_cuda': 'unverified', 'message_language': 'unverified', 'go': False}}
    return report


def markdown(report):
    lines = ['# PRIVATE derived intent v2 report', '',
             'Descriptive historical-label comparison; primary split: test.',
             'Baseline is a recorded harness control. Its replay latency is not production latency.', '',
             '| Observation | Test cases | Correct / all | Accuracy |', '|---|---:|---:|---:|']
    for label, metrics in [('Historical baseline', report['baseline']['metrics']['test'])] + [
            (label, value['metrics']['test']) for label, value in report['candidates'].items()]:
        # Labels are caller-provided private labels, escaped to preserve Markdown structure.
        label = label.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
        lines.append(f"| {label} | {metrics['total_cases']} | {metrics.get('passed_cases', 0)}/{metrics['total_cases']} | {metrics['accuracy_over_all']} |")
    lines += ['', f"Candidate status: {report['candidate_status']}. Go: false.", '', *report['limitations'], '',
              'The private JSON contains per-label confusion, statuses, split/group denominators and evidence hashes.']
    return '\n'.join(lines) + '\n'


def private_destination(path):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise ValueError('Output must be a new private ignored directory')
    repo = Path(__file__).resolve().parents[1]
    try:
        relative = path.relative_to(repo)
    except ValueError:
        raise ValueError('Output must be inside this repository under a privacy ignore rule') from None
    ignored = subprocess.run(['git', 'check-ignore', '-q', '--', str(relative)], cwd=repo)
    if ignored.returncode != 0:
        raise ValueError('Output must be Git ignored')
    if path.resolve() != path:
        raise ValueError('Output ancestors must not be symlinks')
    return path


def verify_pack(pack):
    """Verify private manifest listed bytes without leaking data into the report."""
    manifest_path = pack / 'manifest.json'
    if manifest_path.is_symlink():
        raise ValueError('Pack manifest must not be a symbolic link')
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('schema_version') != 'deposium.intent-private-pack/v2':
        raise ValueError('Unsupported private pack manifest')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Missing pack evidence hashes')
    evidence = {'manifest.json': digest(manifest_bytes)}
    for name, expected in files.items():
        if not isinstance(name, str) or Path(name).name != name or name in {'.', '..'}:
            raise ValueError('Unsafe pack evidence path')
        path = pack / name
        if path.is_symlink():
            raise ValueError('Pack evidence must not be a symbolic link')
        actual = digest(path.read_bytes())
        if actual != expected:
            raise ValueError('Pack evidence hash mismatch')
        evidence[name] = actual
    required = {'protocol.frozen.json', 'intent-choice-cards.frozen.json', 'cases.jsonl'}
    if not required <= set(files):
        raise ValueError('Pack omits frozen evidence')
    if evidence['intent-choice-cards.frozen.json'] != digest(CARDS_PATH.read_bytes()):
        raise ValueError('Pack cards differ from frozen scorer cards')
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', action='append', default=[], metavar='LABEL=ARCHIVE')
    parser.add_argument('--pack-root')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        output = private_destination(args.output)
        baseline = load_archive(args.baseline, 'baseline')
        candidates = {}
        for item in args.candidate:
            label, separator, archive = item.partition('=')
            if not separator or not label.strip() or label in candidates:
                raise ValueError('Expected unique nonempty LABEL=ARCHIVE')
            candidates[label] = load_archive(archive, 'candidate')
        report = build_report(baseline, candidates)
        if args.pack_root:
            pack = Path(args.pack_root)
            report['pack_evidence_sha256'] = verify_pack(pack)
            pack_cases, _ = parse_cases((pack / 'cases.jsonl').read_bytes())
            paired_cases(pack_cases, baseline['cases'])
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name, data in [('report.json', json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)),
                           ('report.md', markdown(report))]:
            with (output / name).open('x', encoding='utf-8') as stream:
                stream.write(data)
        print('Private aggregate report created; no model inference performed.')
        return 0
    except (ValueError, OSError):
        # Do not expose private case IDs, paths, message previews or metadata.
        print('Report refused: invalid evidence, comparison, or private destination.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
