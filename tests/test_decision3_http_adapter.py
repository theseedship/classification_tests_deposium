from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import jev_http_adapter as transport
from deposium_bench.adapters import load_profile, create_adapter
from deposium_bench.campaigns import run_campaign, rescore_campaign
from deposium_bench.decision3_http_adapter import Decision3HTTPAdapter, validate_model_profile
from deposium_bench.mastra_observation import observe_local
from test_jev_http_adapter import FakeConnection, FakeResponse, KEY

ROOT = Path(__file__).resolve().parents[1]


def native():
    return {'model': 'vllm-sr/d3-turbo', 'answers': {'answer': {
        'type': 'choice', 'choice': 'Unknown', 'probabilities': {'Known': 0.2, 'Unknown': 0.8},
        'confidence': 0.8}}, 'usage': {'input_tokens': 17, 'output_tokens': 0},
        'meta': {'model_id': 'vllm-sr/d3-turbo', 'revision': 'a'*40,
                 'model_sha256': 'b'*64, 'dtype': 'bfloat16', 'numerics': 'approximate',
                 'engine': 'transformers', 'accelerator': 'gpu', 'device': '0',
                 'queue_ms': 1.0, 'compute_ms': 3.0}}


class Decision3HTTPTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.profile, _ = load_profile(ROOT/'profiles/decision3-turbo-api-context.json')
        self.profile['model']['budget_ledger'] = str(self.root/'budget.jsonl')
        self.path = self.root/'profile.json'
        self.path.write_text(json.dumps(self.profile))
        FakeConnection.calls = []
        FakeConnection.request_error = None
        FakeConnection.response = FakeResponse(native(), headers={'x-request-id': 'd3-request-id'})
        for p in (patch.object(transport, 'HTTPSConnection', FakeConnection),
                  patch.dict(os.environ, {'DECISION_API_KEY': KEY})):
            p.start(); self.addCleanup(p.stop)

    def adapter(self):
        result = create_adapter(self.profile, self.path)
        self.addCleanup(result.close)
        self.assertIsInstance(result, Decision3HTTPAdapter)
        return result

    def request(self):
        return {'case_id': 'PRIVATE_GOLD_ID', 'contract_id': 'bench.context-choice',
                'input': {'context': 'Synthetic context', 'question': 'Choose an answer',
                          'options': [{'id': 'opaque-a', 'description': 'Known'},
                                      {'id': 'opaque-b', 'description': 'Unknown'}]}}

    def test_success_retains_identity_and_sends_only_visible_input(self):
        adapter = self.adapter()
        self.assertFalse(FakeConnection.calls)
        result = adapter.predict(self.request())
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['output'], {'choice_id': 'opaque-b'})
        self.assertEqual(result['raw_output']['native_result'], native())
        self.assertEqual(result['raw_output']['runtime_meta'], native()['meta'])
        self.assertEqual(result['raw_output']['request_id'], 'd3-request-id')
        connection = FakeConnection.calls[0]
        body = json.loads(connection.body)
        self.assertEqual(connection.host, 'decision.vllm-sr.ai')
        self.assertEqual(body['options'], {'return_meta': True})
        self.assertNotIn('PRIVATE_GOLD_ID', connection.body.decode())
        self.assertNotIn('opaque-b', connection.body.decode())
        self.assertEqual(adapter.provenance['adapter'], 'decision3_http')
        self.assertIn('decision3_adapter_sha256', adapter.provenance)

    def test_missing_key_never_calls_api(self):
        with patch.dict(os.environ, {'DECISION_API_KEY': ''}):
            self.assertEqual(self.adapter().predict(self.request())['status'], 'missing')
        self.assertFalse(FakeConnection.calls)

    def test_untrusted_endpoint_alias_and_budget_rejected(self):
        for key, value in [('endpoint', 'https://other.example/v1/systemone'),
                           ('model_id', 'vllm-sr/d3'), ('credential_env', 'OTHER'),
                           ('max_requests', 801), ('reserved_input_tokens_per_request', 1)]:
            changed = deepcopy(self.profile); changed['model'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_model_profile(changed)

    def test_runtime_identity_is_required(self):
        for field in ('model_id', 'revision', 'model_sha256'):
            data = native(); data['meta'].pop(field)
            FakeConnection.response = FakeResponse(data)
            result = self.adapter().predict(self.request())
            self.assertEqual(result['error'], 'decision3_runtime_identity_missing')
        data = native(); data.pop('meta'); FakeConnection.response = FakeResponse(data)
        self.assertEqual(self.adapter().predict(self.request())['status'], 'error')

    def test_wrong_model_probabilities_and_generated_text_rejected(self):
        variants = []
        data = native(); data['model'] = 'vllm-sr/d3-mini'; variants.append(data)
        data = native(); data['answers']['answer']['probabilities']['Known'] = .5; variants.append(data)
        data = native(); data['answers']['answer']['choice'] = 'Known'; variants.append(data)
        data = native(); data['usage']['output_tokens'] = 1; variants.append(data)
        data = native(); data['answers'] = {}; variants.append(data)
        for data in variants:
            FakeConnection.response = FakeResponse(data)
            self.assertEqual(self.adapter().predict(self.request())['status'], 'error')

    def test_secret_in_native_response_is_not_retained(self):
        data = native(); data['meta']['extra'] = KEY
        FakeConnection.response = FakeResponse(data)
        result = self.adapter().predict(self.request())
        self.assertEqual(result['status'], 'error')
        self.assertNotIn(KEY, json.dumps(result))

    def test_rate_limit_stops_without_retry(self):
        FakeConnection.response = FakeResponse({}, status=429)
        adapter = self.adapter()
        self.assertEqual(adapter.predict(self.request())['status'], 'error')
        self.assertEqual(adapter.predict(self.request())['status'], 'error')
        self.assertEqual(len(FakeConnection.calls), 1)

    def test_campaign_archives_real_trace_and_rescores_offline(self):
        summary = run_campaign(ROOT/'datasets/context-choice-v1/cases.jsonl', self.path,
                               self.root/'run', max_new_cases=1)
        self.assertEqual(len(FakeConnection.calls), 1)
        self.assertEqual(json.loads((self.root/'run/profile.json').read_text())['model']['budget_ledger'],
                         str(self.root/'budget.jsonl'))
        # The two-option mock cannot pass a real four-option case.
        self.assertEqual(summary['metrics']['scored_cases'], 0)
        rescored = rescore_campaign(self.root/'run', self.root/'rescore')
        self.assertEqual(rescored['metrics']['scored_cases'], 0)
        self.assertEqual(len(FakeConnection.calls), 1)

    def test_mastra_requires_remote_opt_in_before_any_request(self):
        with self.assertRaisesRegex(ValueError, 'only explicit local'):
            observe_local(ROOT/'datasets/mastra-read-pilot-v0/cases.jsonl', self.path, self.root/'mastra')
        self.assertFalse(FakeConnection.calls)


    def test_provider_error_is_archived_and_secret_error_is_rejected(self):
        data = {'error': {'code': 'question_failed', 'question_error': 'max_length_exceeded'}}
        FakeConnection.response = FakeResponse(data, status=400)
        result = self.adapter().predict(self.request())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['raw_output']['provider_error'], data)
        data['error']['message'] = KEY
        FakeConnection.response = FakeResponse(data, status=400)
        secret_result = self.adapter().predict(self.request())
        self.assertEqual(secret_result['error'], 'decision3_response_secret_rejected')
        self.assertNotIn(KEY, json.dumps(secret_result))


if __name__ == '__main__':
    unittest.main()
