"""Offline Julia transport tests using tiny independent Python modules, no weights."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from deposium_bench.julia_adapter import JuliaAdapter, JuliaProfileError, TASKS, validate_model_profile
from deposium_bench.choice_protocol import CONTEXT_CHOICE_CONTRACT, CONTEXT_CHOICE_PROMPT, choice_row, ordered_choice_ids, validate_choice_input

REVISION = "a85b127321d580d65176c89ced8273f305745d85"
ROOT = Path(__file__).resolve().parents[1]


class JuliaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.model = self.root / "model"
        self.model.mkdir()
        self.capture = self.root / "capture.json"
        (self.model / "torch.py").write_text("def set_num_threads(value): pass\n")
        package = self.model / "julia"
        package.mkdir()
        package.joinpath("__init__.py").write_text('''import json
import time
from pathlib import Path
CAPTURE = Path(%r)
class Engine:
    def __init__(self, max_length, head_length):
        self.max_length, self.head_length = max_length, head_length
    def _tokens(self, text, add_special_tokens=False):
        return {'input_ids': list(range(len(text.split())))}
    def encoding_info(self, rows):
        row = rows[0]
        if any('<mask>' in text for text in [row['state'], row['question'], *row['options']]):
            raise ValueError('Reserved model marker in request')
        options = [len(self._tokens(option)['input_ids']) for option in row['options']]
        if any(length > 48 for length in options):
            raise ValueError('Option exceeds 48-token model contract')
        question = len(self._tokens('choice question: ' + row['question'])['input_ids'])
        if question + sum(options) + len(options) > self.head_length:
            raise ValueError('Question/options exceed lossless head budget')
        tokens = len(self._tokens(row['state'])['input_ids']) + question + sum(options) + len(options) + 4
        if tokens > self.max_length:
            raise ValueError('Game state exceeds lossless context budget')
        return [{'tokens':tokens, 'optionTokens':options, 'headLength':self.head_length, 'stateTruncated':False, 'optionsTruncated':False}]
    def logits(self, rows):
        previous = json.loads(CAPTURE.read_text())
        previous['rows'].extend(rows)
        CAPTURE.write_text(json.dumps(previous))
        try:
            state = json.loads(rows[0]['state'])
        except ValueError:
            state = {'context': rows[0]['state']}
        if not isinstance(state, dict):
            state = {'context': rows[0]['state']}
        time.sleep(state.get('delay', 0))
        if state.get('allocate'):
            self.memory = bytearray(180 * 1024 * 1024)
        if state.get('raise'):
            raise RuntimeError('secret-test-value')
        chosen = 'abstain' if state.get('abstain') else 'catalog'
        if 'catalog' not in rows[0]['options']:
            chosen = 'unknown' if state.get('context') == 'ambiguous' else rows[0]['options'][0]
        return [[3.0 if option == chosen else 0.0 for option in rows[0]['options']]]
def load_model(path, **kwargs):
    CAPTURE.write_text(json.dumps({'path':path, 'kwargs':kwargs, 'rows':[]}))
    return Engine(kwargs['max_length'], kwargs['head_length'])
''' % str(self.capture))
        for name in ("torch", "transformers", "tokenizers", "numpy"):
            metadata = self.model / f"{name}-0.0.test.dist-info"
            metadata.mkdir()
            (metadata / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.0.test\n")
        self.manifest_path = self.root / "assets.json"
        files = [{"path": path.relative_to(self.model).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "size": path.stat().st_size} for path in sorted(self.model.rglob("*")) if path.is_file()]
        self.manifest_path.write_text(json.dumps({"schema_version": "deposium.model-assets/v1",
                                                "repo_id": "SupersonicLabs/Julia-1", "revision": REVISION, "files": files}))
        self.prompt_path = self.root / "prompt.json"
        self.prompt_path.write_text(json.dumps({"schema_version": "deposium.document-task-prompt/v1",
                                               "input_protocol": "current_equivalent", "question": "Choose the document task",
                                               "options": [{"id": task, "description": task} for task in TASKS], "order": "canonical"}))
        (self.root / "runtime.lock").write_text("torch==0.0.test\n")
        self.profile_path = self.root / "profile.json"
        self.profile = {"schema_version": "deposium.candidate/v1", "profile_id": "offline-julia-test", "adapter": "julia",
                        "qualification": "model_isolated", "capabilities": ["mcps.document-plan"], "revision": REVISION,
                        "timeout_seconds": 2, "recordings": None,
                        "model": {"repo_id": "SupersonicLabs/Julia-1", "local_dir": "model", "runtime_python": sys.executable,
                                  "assets_manifest": "assets.json", "prompt_path": "prompt.json", "runtime_lock": "runtime.lock",
                                  "max_length": 1024, "head_length": 512, "threads": 1, "max_rss_mb": 3072}}
        self.profile_path.write_text(json.dumps(self.profile))

    def adapter(self):
        adapter = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        self.assertTrue(adapter.provenance["available"], adapter.provenance)
        return adapter

    @staticmethod
    def request(**input_fields):
        return {"case_id": "semantic-reference-not-for-model", "contract_id": "mcps.document-plan",
                "input": {"message": "How many documents?", **input_fields}, "reference": {"task": "catalog"}}

    def test_real_worker_api_arguments_input_isolation_and_reuse(self):
        adapter = self.adapter()
        pid = adapter._process.pid
        first = adapter.predict(self.request())
        second = adapter.predict(self.request(message="List the documents"))
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["output"], {"task": "catalog"})
        self.assertEqual(second["output"], first["output"])
        self.assertEqual(adapter._process.pid, pid)
        capture = json.loads(self.capture.read_text())
        self.assertEqual(len(capture["rows"]), 2)
        self.assertEqual(json.loads(capture["rows"][0]["state"]), self.request()["input"])
        self.assertNotIn("semantic-reference", capture["rows"][0]["state"])
        self.assertNotIn("reference", capture["rows"][0]["state"])
        kwargs = capture["kwargs"]
        self.assertEqual(kwargs["device"], "cpu")
        self.assertEqual(kwargs["backend"], "torch")
        self.assertTrue(kwargs["strict_encoding"])
        self.assertFalse(kwargs["marker_only_head"])
        self.assertFalse(kwargs["compile_model"])
        self.assertFalse(kwargs["bend_postprocess"])
        self.assertEqual(adapter.provenance["prompt"], json.loads(self.prompt_path.read_text()))
        self.assertEqual(adapter.provenance["assets_manifest"], json.loads(self.manifest_path.read_text()))
        self.assertEqual(adapter.provenance["runtime_lock"], "torch==0.0.test\n")

    def test_abstention_and_reversed_order_keep_semantic_ids(self):
        prompt = json.loads(self.prompt_path.read_text())
        prompt["options"].reverse()
        prompt["order"] = "reversed"
        self.prompt_path.write_text(json.dumps(prompt))
        adapter = self.adapter()
        result = adapter.predict(self.request(abstain=True))
        self.assertEqual(result["status"], "abstain")
        self.assertIsNone(result["output"])
        self.assertEqual(result["raw_output"]["ordered_ids"], list(reversed(TASKS)))
        self.assertAlmostEqual(sum(result["raw_output"]["probabilities"]), 1)

    def test_nested_annotations_cannot_cross_transport(self):
        adapter = self.adapter()
        for key in ("reference", "Gold", "EXPECTED_OUTPUT", "rationale", "assertions"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                adapter.predict(self.request(context=[{key: "secret annotation"}]))
        self.assertEqual(json.loads(self.capture.read_text())["rows"], [])

    def test_inference_timeout_closes_process_and_stays_distinct(self):
        self.profile["timeout_seconds"] = 0.05
        adapter = self.adapter()
        process = adapter._process
        start = time.monotonic()
        result = adapter.predict(self.request(delay=1))
        self.assertEqual(result["status"], "timeout")
        self.assertLess(time.monotonic() - start, 2)
        self.assertIsNotNone(process.poll())
        self.assertEqual(adapter.predict(self.request())["status"], "timeout")

    def test_initialization_deadline_closes_worker(self):
        sleeper = self.root / "sleeper.py"
        sleeper.write_text("import time\ntime.sleep(2)\n")
        with patch("deposium_bench.julia_adapter.WORKER", sleeper), \
                patch("deposium_bench.julia_adapter.INITIALIZATION_SECONDS", 0.08):
            adapter = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        self.assertFalse(adapter.provenance["available"])
        self.assertEqual(adapter.predict(self.request())["status"], "timeout")
        self.assertIsNone(adapter._process)

    def test_rss_limit_is_observed_and_process_is_closed(self):
        self.profile["model"]["max_rss_mb"] = 128
        adapter = self.adapter()
        process = adapter._process
        result = adapter.predict(self.request(allocate=True))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "julia_rss_limit")
        self.assertIsNotNone(process.poll())

    def test_asset_prompt_and_executable_drift_fail_before_inference(self):
        adapter = self.adapter()
        self.prompt_path.write_text(self.prompt_path.read_text() + " ")
        result = adapter.predict(self.request())
        self.assertEqual(result["status"], "error")
        self.assertEqual(json.loads(self.capture.read_text())["rows"], [])
        self.assertIsNone(adapter._process)

    def test_interruption_closes_worker_and_propagates(self):
        adapter = self.adapter()
        process = adapter._process
        with patch.object(adapter, "_exchange", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            adapter.predict(self.request())
        self.assertIsNotNone(process.poll())
        self.assertIsNone(adapter._process)

    def test_oversized_worker_protocol_output_is_rejected(self):
        writer = self.root / "oversized.py"
        writer.write_text("import sys\nsys.stdin.buffer.readline()\nsys.stdout.buffer.write(b'x' * (1024 * 1024 + 1))\nsys.stdout.flush()\n")
        with patch("deposium_bench.julia_adapter.WORKER", writer):
            adapter = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        self.assertEqual(adapter.predict(self.request())["status"], "error")
        self.assertIsNone(adapter._process)

    def test_missing_assets_and_corrupt_hash_are_distinct(self):
        self.model.joinpath("torch.py").unlink()
        missing = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(missing.close)
        self.assertEqual(missing.predict(self.request())["status"], "missing")
        self.model.joinpath("torch.py").write_text("changed bytes\n")
        corrupt = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(corrupt.close)
        self.assertEqual(corrupt.predict(self.request())["status"], "error")

    def test_unlisted_assets_and_escaping_symlinks_are_rejected(self):
        self.model.joinpath("extra.py").write_text("unused = True\n")
        adapter = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        self.assertEqual(adapter.predict(self.request())["status"], "error")
        self.model.joinpath("extra.py").unlink()
        self.model.joinpath("torch.py").unlink()
        self.model.joinpath("torch.py").symlink_to(self.root / "runtime.lock")
        adapter = JuliaAdapter(self.profile, self.profile_path)
        self.addCleanup(adapter.close)
        self.assertEqual(adapter.predict(self.request())["status"], "error")

    def test_failure_text_is_redacted_and_close_is_idempotent(self):
        adapter = self.adapter()
        # Use the actual flag without Python keyword syntax.
        request = self.request()
        request["input"]["raise"] = True
        result = adapter.predict(request)
        self.assertEqual(result["error"], "julia_inference_failed")
        self.assertNotIn("secret-test-value", json.dumps(result))
        process = adapter._process
        adapter.close()
        adapter.close()
        self.assertIsNotNone(process.poll())

    def test_unsupported_contract_does_not_enter_model(self):
        adapter = self.adapter()
        result = adapter.predict({"case_id": "outside", "contract_id": "mcps.search", "input": {}})
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(json.loads(self.capture.read_text())["rows"], [])

    def test_model_settings_are_bounded_before_any_io(self):
        mutations = [("threads", 0), ("threads", 5), ("max_rss_mb", 3073), ("head_length", 1025),
                     ("max_length", True), ("repo_id", "unreviewed/model")]
        for key, value in mutations:
            profile = deepcopy(self.profile)
            profile["model"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(JuliaProfileError):
                validate_model_profile(profile)

    def test_revision_is_checked_before_asset_access(self):
        for revision in (None, "main", "Z" * 40, [], "1" * 39):
            profile = deepcopy(self.profile)
            profile["revision"] = revision
            with self.subTest(revision=revision), self.assertRaises(JuliaProfileError):
                validate_model_profile(profile)

    def choice_profile(self):
        self.profile["capabilities"] = [CONTEXT_CHOICE_CONTRACT]
        self.prompt_path.write_text(json.dumps(CONTEXT_CHOICE_PROMPT))

    @staticmethod
    def choice_request(count=3, context="supplied context"):
        return {"case_id": "hidden-semantic-case-id", "contract_id": CONTEXT_CHOICE_CONTRACT,
                "input": {"context": context, "question": "Which statement fits the supplied context?",
                          "options": [{"id": f"id-{index}", "description": f"option-{index}"} for index in range(count)]}}

    def test_general_choice_dynamic_counts_plain_context_and_input_hash(self):
        self.choice_profile()
        adapter = self.adapter()
        pid = adapter._process.pid
        for count in (2, 3, 20):
            request = self.choice_request(count)
            result = adapter.predict(request)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["output"], {"choice_id": "id-0"})
            self.assertEqual(len(result["raw_output"]["logits"]), count)
            canonical = json.dumps(request["input"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            self.assertEqual(result["raw_output"]["input_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
            row = json.loads(self.capture.read_text())["rows"][-1]
            self.assertEqual(row, choice_row(request["input"]))
            self.assertEqual(row["state"], "supplied context")
            self.assertNotIn("id-0", json.dumps(row))
            self.assertNotIn("hidden-semantic-case-id", json.dumps(row))
        self.assertEqual(adapter._process.pid, pid)

    def test_unknown_id_is_an_ordinary_general_choice(self):
        self.choice_profile()
        adapter = self.adapter()
        request = self.choice_request(context="ambiguous")
        request["input"]["options"] = [{"id": "known", "description": "known"},
                                         {"id": "abstain", "description": "unknown"}]
        result = adapter.predict(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], {"choice_id": "abstain"})

    def test_choice_input_shape_uniqueness_and_annotation_guards(self):
        value = self.choice_request()["input"]
        invalid = []
        for key, item in (("reference", {}), ("context", {}), ("question", "  "),
                          ("options", []), ("options", [{"id": "only", "description": "only"}])):
            changed = deepcopy(value); changed[key] = item; invalid.append(changed)
        for member in ("id", "description"):
            changed = deepcopy(value); changed["options"][1][member] = changed["options"][0][member]; invalid.append(changed)
        changed = deepcopy(value); changed["options"][0]["expected"] = True; invalid.append(changed)
        changed = deepcopy(value); changed["options"] *= 8; invalid.append(changed)
        for changed in invalid:
            with self.subTest(value=changed), self.assertRaises(ValueError):
                validate_choice_input(changed)
        empty = deepcopy(value); empty["context"] = ""
        validate_choice_input(empty)
        self.assertEqual(ordered_choice_ids(value), ["id-0", "id-1", "id-2"])

    def test_encoding_overflows_are_typed_before_forward_and_keep_worker(self):
        self.choice_profile()
        adapter = self.adapter()
        pid = adapter._process.pid
        requests = []
        request = self.choice_request(context="word " * 1100)
        requests.append((request, "julia_context_overflow"))
        request = self.choice_request(); request["input"]["question"] = "question " * 600
        requests.append((request, "julia_head_overflow"))
        request = self.choice_request(); request["input"]["options"][0]["description"] = "option " * 49
        requests.append((request, "julia_option_overflow"))
        requests.append((self.choice_request(context="<mask>"), "julia_reserved_marker"))
        for request, reason in requests:
            result = adapter.predict(request)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"], reason)
            self.assertFalse(result["raw_output"]["forward_executed"])
            self.assertIsNone(result["raw_output"]["inference_ms"])
            self.assertGreaterEqual(result["raw_output"]["decision_ms"], 0)
            self.assertEqual(json.loads(self.capture.read_text())["rows"], [])
            self.assertEqual(adapter._process.pid, pid)
        self.assertEqual(adapter.predict(self.choice_request())["status"], "ok")

    def test_general_choice_timing_token_components_and_init_identity(self):
        self.choice_profile()
        adapter = self.adapter()
        result = adapter.predict(self.choice_request())
        raw = result["raw_output"]
        self.assertGreaterEqual(raw["decision_ms"], raw["inference_ms"])
        self.assertGreaterEqual(adapter.provenance["init_wall_ms"], adapter.provenance["load_ms"])
        self.assertEqual(len(adapter.provenance["choice_protocol_sha256"]), 64)
        components = raw["token_components"]
        self.assertEqual(components["special"], 7)
        self.assertEqual(components["total"], components["state"] + components["question"] + sum(components["options"]) + 7)
        self.assertEqual(components["padded"] % 8, 0)
        self.assertEqual(components["total"], raw["encoding_info"]["tokens"])
        second = self.adapter()
        self.assertEqual(second.provenance["identity_sha256"], adapter.provenance["identity_sha256"])

    def test_context_profile_limit_and_invalid_head_fail_before_boot(self):
        self.choice_profile()
        self.profile["model"]["max_length"] = 8192
        validate_model_profile(self.profile)
        for length, head in ((8193, 512), (516, 512), (100, 96), (100, 512)):
            profile = deepcopy(self.profile)
            profile["model"].update(max_length=length, head_length=head)
            with self.subTest(length=length, head=head), self.assertRaises(JuliaProfileError):
                validate_model_profile(profile)

    def test_worker_import_does_not_load_candidate(self):
        specification = importlib.util.spec_from_file_location("offline_worker", ROOT / "bridges/julia-worker.py")
        module = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, {"torch": None, "julia": None}):
            specification.loader.exec_module(module)
        self.assertEqual(json.loads(module._input_json({"message": "hello"})), {"message": "hello"})


if __name__ == "__main__":
    unittest.main()
