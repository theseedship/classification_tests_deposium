"""Offline framework admission, archives and HTTP measurement boundaries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deposium_bench import campaigns
from deposium_bench.adapters import create_adapter, parse_profile
from deposium_bench.context_analysis import _measurements, _provider_usage, analyze_context
from deposium_bench.comparison import _side, _timings
from deposium_bench.timing import benchmark_timing, _distribution
from deposium_bench.cases import candidate_request, load_cases
from tests.test_schemas import Draft202012Validator, load_schema

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'datasets/context-choice-v1/cases.jsonl'


def profile():
    return {'schema_version': 'deposium.candidate/v1', 'profile_id': 'offline-jev',
            'adapter': 'jev_http', 'qualification': 'model_isolated',
            'capabilities': ['bench.context-choice'], 'revision': None, 'recordings': None,
            'timeout_seconds': 10,
            'model': {'endpoint': 'https://api.typesafe.ai/v1/systemone', 'model_id': 'jev-1.0.0',
                      'credential_env': 'TYPESAFE_API_KEY', 'budget_ledger': 'budget/ledger.json',
                      'max_requests': 20, 'max_input_tokens': 2000000,
                      'reserved_input_tokens_per_request': 65536, 'max_request_bytes': 131072,
                      'min_interval_seconds': .1}}


class JevFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'profile.json'
        self.path.write_text(json.dumps(profile()))
        cases, _ = load_cases(DATASET)
        self.cases = cases[:2]
        self.dataset = self.root / 'cases.jsonl'
        self.dataset.write_text(''.join(json.dumps(case) + '\n' for case in self.cases))

    def test_profile_and_factory_are_lazy_and_missing_credentials_do_not_touch_budget(self):
        value = profile()
        self.assertEqual(parse_profile(json.dumps(value).encode())[0], value)
        with patch.dict(os.environ, {}, clear=True), \
             patch('deposium_bench.jev_http_adapter.HTTPSConnection', side_effect=AssertionError('no HTTP')):
            adapter = create_adapter(value, self.path)
            self.assertFalse(adapter.provenance['available'])
            result = adapter.predict(candidate_request(self.cases[0]))
            self.assertEqual(result['status'], 'missing')
            self.assertIsNone(result['raw_output'])
            self.assertFalse((self.root / 'budget').exists())
            self.assertNotIn('model_revision', adapter.provenance)
            adapter.close()
        for key, bad in [('endpoint', 'https://elsewhere.test'), ('model_id', 'latest'),
                         ('credential_env', 'OTHER'), ('max_requests', 801),
                         ('max_input_tokens', 2000001), ('max_request_bytes', 131073),
                         ('min_interval_seconds', .09), ('reserved_input_tokens_per_request', 1)]:
            malformed = deepcopy(value)
            malformed['model'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_profile(json.dumps(malformed).encode())
        for key, bad in [('revision', 'a' * 40), ('timeout_seconds', 31),
                         ('capabilities', ['mcps.document-plan'])]:
            malformed = deepcopy(value)
            malformed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_profile(json.dumps(malformed).encode())

    def test_missing_archive_has_api_identity_and_rebases_only_ledger(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch('deposium_bench.jev_http_adapter.HTTPSConnection', side_effect=AssertionError('no HTTP')):
            first = campaigns.run_campaign(self.dataset, self.path, self.root / 'run', max_new_cases=1)
            second = campaigns.resume_campaign(self.root / 'run', self.root / 'resume')
        prepared = json.loads((self.root / 'run/profile.json').read_text())
        expected = profile()
        expected['model']['budget_ledger'] = str(self.root / 'budget/ledger.json')
        self.assertEqual(prepared, expected)
        manifest = json.loads((self.root / 'run/manifest.json').read_text())
        self.assertEqual(manifest['qualification'], 'model_isolated')
        self.assertEqual(manifest['proof_level'], 'A')
        self.assertEqual(manifest['input_protocol'], 'context_choice')
        self.assertEqual(first['metrics']['scored_cases'], 0)
        self.assertEqual(second['metrics']['counts_by_status']['missing'], 2)
        self.assertFalse((self.root / 'budget').exists())
        self.assertEqual(json.loads((self.root / 'resume/profile.json').read_text()), prepared)
        if Draft202012Validator:
            Draft202012Validator(load_schema('candidate')).validate(prepared)
            Draft202012Validator(load_schema('campaign')).validate(manifest)
        analysis = analyze_context(self.root / 'resume', self.root / 'analysis')
        self.assertEqual(analysis['counts']['latency']['http_ms']['count'], 0)
        self.assertEqual(analysis['counts']['provider_usage']['provider_input_tokens']['unreported_calls'], 2)
        self.assertIn('provider_input_tokens', (self.root / 'analysis/rows.csv').read_text())

    @unittest.skipUnless(Draft202012Validator, 'jsonschema is optional')
    def test_http_schema_accepts_configured_transport_without_claiming_model_revision(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'offline-syntactic-fixture'}, clear=True), \
             patch('deposium_bench.jev_http_adapter.HTTPSConnection', side_effect=AssertionError('no HTTP')):
            adapter = create_adapter(profile(), self.path)
            self.assertTrue(adapter.provenance['available'])
            self.assertFalse((self.root / 'budget').exists())
            schema = load_schema('campaign')
            fragment = {'$defs': schema['$defs'], '$ref': '#/$defs/adapter_provenance'}
            validator = Draft202012Validator(fragment)
            validator.validate(adapter.provenance)
            for field, value in [('model_revision', 'a' * 40), ('load_rss_mb', 12),
                                 ('runtime_lock_verified', True)]:
                invalid = dict(adapter.provenance, **{field: value})
                with self.subTest(field=field):
                    self.assertTrue(list(validator.iter_errors(invalid)))
            malformed = deepcopy(profile())
            malformed['model']['repo_id'] = 'fake/model'
            self.assertTrue(list(Draft202012Validator(load_schema('candidate')).iter_errors(malformed)))
            adapter.close()

    def test_http_and_cache_measurements_never_invent_native_or_engine_data(self):
        attempted = {'duration_ms': 120, 'raw_output': {'http_ms': 90, 'http_attempted': True,
                     'cached_failure': False, 'requested_model': 'jev-1.0.0', 'observed_model': 'jev-1.0.0',
                     'usage': {'input_tokens': 123, 'output_tokens': 0}}}
        cached = {'duration_ms': 1, 'raw_output': {'http_attempted': False, 'cached_failure': True}}
        measurements = [_measurements(attempted), _measurements(cached)]
        self.assertEqual(measurements[0]['http_ms'], 90)
        for field in ('decision_ms', 'inference_ms', 'rss_mib', 'native_tokens', 'state_truncated'):
            self.assertIsNone(measurements[0][field])
        usage = _provider_usage(measurements)
        self.assertEqual(usage['http_attempted_calls'], 1)
        self.assertEqual(usage['cached_failure_calls'], 1)
        self.assertEqual(usage['provider_input_tokens']['total'], 123)
        self.assertEqual(usage['provider_output_tokens']['count'], 1)
        self.assertEqual(usage['provider_input_tokens']['unreported_calls'], 1)
        invalid = _measurements({'duration_ms': 1, 'raw_output': {'http_ms': True,
                                'usage': {'input_tokens': -1, 'output_tokens': 'bad'}}})
        self.assertIsNone(invalid['http_ms'])
        self.assertIsNone(invalid['provider_input_tokens'])
        distribution = _distribution([{'result': dict(attempted, status='ok')},
                                      {'result': dict(cached, status='error')}])
        self.assertEqual(distribution['latency']['http_ms']['count'], 1)
        self.assertEqual(distribution['latency']['decision_ms']['count'], 0)
        self.assertEqual(distribution['provider_usage'], usage)
        side = _side({'status': 'ok', 'scored': True, 'passed': False, 'reason': 'fixture', 'checks': []}, attempted)
        self.assertEqual(side['runtime_observations']['observed_model'], 'jev-1.0.0')
        self.assertEqual(side['runtime_observations']['usage']['input_tokens'], 123)
        self.assertFalse(_timings([attempted, cached])['cross_candidate_comparable'])

    def test_timing_reuses_archived_ledger_across_launches_and_calls_only_public_inputs(self):
        adapters = []
        def factory(value, path, **kwargs):
            self.assertEqual(value['model']['budget_ledger'], str(self.root / 'budget/ledger.json'))
            self.assertEqual(set(value['model']), set(profile()['model']))
            adapter = Mock()
            adapter.capabilities = ['bench.context-choice']
            adapter.provenance = {'identity_sha256': 'a' * 64, 'adapter': 'jev_http'}
            adapter.predict.return_value = {'status': 'error', 'output': None, 'error': 'fixture',
                 'raw_output': {'http_attempted': True, 'cached_failure': False, 'http_ms': 7}}
            adapters.append(adapter)
            return adapter
        with patch.object(campaigns, 'create_adapter', side_effect=factory):
            summary = benchmark_timing(self.dataset, [self.path], self.root / 'timing', launches=2, warmup=0, passes=1)
        self.assertEqual(summary['recorded_calls'], 6)
        self.assertEqual(len(adapters), 2)
        for adapter in adapters:
            self.assertEqual([call.args[0] for call in adapter.predict.call_args_list],
                             [candidate_request(self.cases[0]), *[candidate_request(case) for case in self.cases]])
            adapter.close.assert_called_once_with()
        measured = summary['candidates']['offline-jev']['phases']['measured']
        self.assertEqual(measured['provider_usage']['http_attempted_calls'], 4)
        self.assertEqual(measured['latency']['http_ms']['count'], 4)
        self.assertEqual(measured['latency']['decision_ms']['count'], 0)
        self.assertTrue(any('budgeted API' in line for line in summary['limitations']))
        self.assertFalse(any('No paid API' in line for line in summary['limitations']))
        self.assertFalse((self.root / 'budget').exists())
