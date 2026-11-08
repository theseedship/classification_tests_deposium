"""Synthetic report controls only; no real annotation or model inference."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench import campaigns
from deposium_bench.chat_intent_v2_corpus import make_case

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('intent_report', ROOT / 'scripts/report-chat-intent-v2.py')
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def case(index, label='search_query', split='test'):
    return make_case({'message_preview': 'Synthetic document question.', 'label': label,
                      'decision': 'labeled', 'reviewed_at': '2026-11-08',
                      'split_group_id': f'synthetic-{index}', 'source_environment': 'synthetic'},
                     index, 'fr', 'synthetic-report-control', split)


def result(value, choice='c', status='ok', duration=10):
    return {'case_id': value['case_id'], 'status': status,
            'output': {'choice_id': choice}, 'duration_ms': duration}


class ReportTests(unittest.TestCase):
    def test_failures_missing_invalid_and_zero_support_keep_denominators(self):
        cases = [case(i) for i in range(8)]
        records = [result(cases[0]), result(cases[1], 'i'), result(cases[2], 'bad')]
        records += [result(cases[i + 3], status=status)
                    for i, status in enumerate(('unsupported', 'error', 'timeout', 'abstain'))]
        metrics = report.aggregate_metrics(cases, records)
        self.assertEqual(metrics['accuracy_over_all'], 1 / 8)
        self.assertEqual(metrics['counts_by_status'], dict(ok=3, unsupported=1, missing=1,
                                                         error=1, timeout=1, abstain=1))
        self.assertEqual(metrics['invalid_outputs'], 1)
        self.assertEqual(metrics['confusion']['counts'][2], [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 6])
        self.assertEqual(metrics['per_label']['search_query']['support'], 8)
        self.assertEqual(metrics['per_label']['connector_search']['predicted_count'], 1)
        self.assertIsNone(metrics['per_label']['connector_search']['recall'])
        self.assertIsNone(metrics['per_label']['connector_search']['f1'])
        self.assertEqual(metrics['connector_search']['false_positives'], 1)
        self.assertEqual(metrics['connector_search']['negative_support'], 8)
        self.assertIsNone(metrics['connector_search']['recall'])
        self.assertEqual(metrics['macro_f1_supported'], 2 / 9)

    def test_paired_exact_subset_and_mismatch_rejection(self):
        baseline = [case(0), case(1)]
        self.assertEqual(report.paired_cases(baseline, [deepcopy(baseline[1])]), [baseline[1]])
        changed = deepcopy(baseline[1])
        changed['input']['context'] += ' altered'
        with self.assertRaises(ValueError):
            report.paired_cases(baseline, [changed])
        with self.assertRaises(ValueError):
            report.paired_cases(baseline, [case(9)])
        with self.assertRaises(ValueError):
            report.paired_cases(baseline, [])

    def test_paired_corrected_introduced_and_missing(self):
        cases = [case(i) for i in range(4)]
        baseline = [result(cases[0]), result(cases[1], 'a'), result(cases[2]), result(cases[3], 'a')]
        candidate = [result(cases[0], 'a'), result(cases[1]), result(cases[2])]
        self.assertEqual(report.paired_metrics(cases, baseline, candidate),
                         dict(common_case_denominator=4, corrected=1, introduced=1,
                              both_correct=1, both_wrong=1))
        self.assertEqual(report.paired_metrics([], [], [])['common_case_denominator'], 0)

    def test_sealed_synthetic_recorded_baseline_is_not_model_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = [case(0), case(1, split='calibration')]
            dataset = root / 'cases.jsonl'
            dataset.write_bytes(b''.join(campaigns._encode(c) for c in cases))
            recordings = root / 'source.jsonl'
            recordings.write_bytes(b''.join(campaigns._encode({
                'case_id': c['case_id'], 'status': 'ok', 'output': {'choice_id': 'c'},
                'raw_output': None, 'error': None}) for c in cases))
            profile = {'schema_version': 'deposium.candidate/v1', 'profile_id': 'synthetic-report',
                       'adapter': 'recorded', 'qualification': 'harness_control',
                       'capabilities': ['bench.context-choice'], 'model': None,
                       'timeout_seconds': 15, 'revision': None, 'recordings': 'source.jsonl'}
            profile_path = root / 'profile.json'
            profile_path.write_text(json.dumps(profile))
            campaigns.run_campaign(dataset, profile_path, root / 'archive')
            baseline = report.load_archive(root / 'archive', 'baseline')
            with self.assertRaises(ValueError):
                report.load_archive(root / 'archive', 'candidate')
            derived = report.build_report(baseline, {})
            self.assertEqual(derived['candidate_status'], 'not_run')
            self.assertFalse(derived['go'])
            self.assertEqual(derived['baseline']['metrics']['test']['total_cases'], 1)
            self.assertNotIn(cases[0]['case_id'], report.markdown(derived))
            (root / 'archive/seal.json').unlink()
            with self.assertRaises(ValueError):
                report.load_archive(root / 'archive', 'baseline')

    def test_candidate_aggregate_fixture_does_not_qualify_cuda_or_language(self):
        # Pure in-memory accounting fixture, not a fabricated sealed model campaign.
        cases = [case(0), case(1, split='calibration')]
        base = {'cases': cases, 'records': [], 'hashes': {}}
        candidate = {'cases': [cases[0]], 'records': [result(cases[0])], 'hashes': {}}
        derived = report.build_report(base, {'synthetic-unit-only': candidate})
        gates = derived['candidates']['synthetic-unit-only']['gates']
        self.assertTrue(gates['same_test_accuracy_at_least_baseline'])
        self.assertTrue(gates['observed_test_p95_below_500_ms'])
        self.assertEqual(gates['actual_cuda'], 'unverified')
        self.assertEqual(gates['message_language'], 'unverified')
        self.assertFalse(gates['go'])
        self.assertFalse(derived['go'])

    def test_pack_hashes_frozen_cards_and_path_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp)
            contents = {'protocol.frozen.json': b'{"synthetic":true}',
                        'intent-choice-cards.frozen.json': report.CARDS_PATH.read_bytes(),
                        'cases.jsonl': campaigns._encode(case(0))}
            for name, data in contents.items():
                (pack / name).write_bytes(data)
            manifest = {'schema_version': 'deposium.intent-private-pack/v2',
                        'files': {name: report.digest(data) for name, data in contents.items()}}
            (pack / 'manifest.json').write_text(json.dumps(manifest))
            self.assertIn('manifest.json', report.verify_pack(pack))
            (pack / 'protocol.frozen.json').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                report.verify_pack(pack)
            manifest['files'] = {'../outside': '0' * 64}
            (pack / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                report.verify_pack(pack)

    def test_existing_or_public_destination_refused(self):
        with self.assertRaises(ValueError):
            report.private_destination(ROOT / 'README.md')
        with self.assertRaises(ValueError):
            report.private_destination(ROOT / 'unignored-synthetic-report')


if __name__ == '__main__':
    unittest.main()
