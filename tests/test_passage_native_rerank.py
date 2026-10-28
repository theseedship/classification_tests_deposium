"""Offline contract tests for the native, isolated TurboV3 runner."""
from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/passage-native-rerank.py"
SPEC = importlib.util.spec_from_file_location("passage_native_rerank", SCRIPT)
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def case(number):
    return {"case_id": f"case-{number}", "contract_id": "bench.passage-rerank",
            "input": {"query": "Quelle valeur ?", "passages": [
                {"id": f"p-{number}-{i}", "text": f"Le passage {i} répond."} for i in range(4)]}}


class NativeRerankContractTests(unittest.TestCase):
    def test_balanced_export_requires_exact_512_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ranking.jsonl"
            rows = [case(i) for i in range(512)]
            raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
            path.write_bytes(raw)
            loaded, _, _ = native.load_inputs(path, native.sha256_bytes(raw), expected_count=512)
            self.assertEqual(len(loaded), 512)
            with self.assertRaisesRegex(native.QualificationError, "expected 128 cases; got 512"):
                native.load_inputs(path, native.sha256_bytes(raw))
            short_raw = "".join(json.dumps(row) + "\n" for row in rows[:128]).encode()
            path.write_bytes(short_raw)
            with self.assertRaisesRegex(native.QualificationError, "expected 512 cases; got 128"):
                native.load_inputs(path, native.sha256_bytes(short_raw), expected_count=512)

    def test_cli_rejects_513_case_profile_before_file_access(self):
        with contextlib.redirect_stderr(io.StringIO()) as diagnostic:
            with self.assertRaises(SystemExit) as raised:
                native.main(["--inputs", "/nonexistent/ranking.jsonl",
                             "--expected-input-sha256", "0" * 64,
                             "--tokenizer", "/nonexistent/tokenizer.json",
                             "--case-count", "513"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--case-count", diagnostic.getvalue())
        self.assertIn("invalid choice", diagnostic.getvalue())
        self.assertIn("513", diagnostic.getvalue())

    def test_frozen_inputs_require_exact_digest_and_complete_case_ids(self):
        rows = [case(i) for i in range(128)]
        raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ranking.jsonl"
            path.write_bytes(raw)
            loaded, observed, digest = native.load_inputs(path, native.sha256_bytes(raw))
            self.assertEqual(len(loaded), 128)
            self.assertEqual(observed, raw)
            self.assertEqual(digest, native.sha256_bytes(raw))
            with self.assertRaisesRegex(native.QualificationError, "SHA-256 mismatch"):
                native.load_inputs(path, "0" * 64)
            with self.assertRaisesRegex(native.QualificationError, "exactly one LF"):
                without_lf = raw.rstrip(b"\n")
                path.write_bytes(without_lf)
                native.load_inputs(path, native.sha256_bytes(without_lf))
            path.write_bytes(raw)
            rows[0]["input"]["passages"][0]["text"] = "line\u2028separator"
            unicode_raw = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()
            path.write_bytes(unicode_raw)
            loaded, _, _ = native.load_inputs(path, native.sha256_bytes(unicode_raw))
            self.assertEqual(loaded[0]["input"]["passages"][0]["text"], "line\u2028separator")
            rows[1]["case_id"] = rows[0]["case_id"]
            changed = "".join(json.dumps(row) + "\n" for row in rows).encode()
            path.write_bytes(changed)
            with self.assertRaisesRegex(native.QualificationError, "duplicate case_id"):
                native.load_inputs(path, native.sha256_bytes(changed))

    def test_exact_pair_length_gate_rejects_native_truncation(self):
        class FakeEncoding:
            def __init__(self, n):
                self.ids = list(range(n))

        class FakeTokenizer:
            @staticmethod
            def from_file(_):
                return FakeTokenizer()

            def no_truncation(self):
                pass

            def no_padding(self):
                pass

            def encode(self, _query, text, add_special_tokens):
                self.assert_special_tokens = add_special_tokens
                return FakeEncoding(513 if text == "too long" else 32)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tokenizer.json"
            path.write_bytes(b"fake")
            module = types.SimpleNamespace(Tokenizer=FakeTokenizer)
            with patch.object(native, "sha256_bytes", return_value=native.EXPECTED_HASHES[native.TOKENIZER_PATH]), \
                 patch.dict(sys.modules, {"tokenizers": module}):
                rows = [case(0)]
                self.assertEqual(native.token_preflight(rows, path)["max_pair_tokens"], 32)
                rows[0]["input"]["passages"][0]["text"] = "too long"
                with self.assertRaisesRegex(native.QualificationError, "truncation"):
                    native.token_preflight(rows, path)

    def test_native_response_maps_sorted_indices_to_frozen_passage_ids(self):
        row = case(7)
        order = [2, 0, 3, 1]
        payload = {"model": native.MODEL, "results": [
            {"index": i, "document": row["input"]["passages"][i]["text"],
             "relevance_score": float(4 - rank)} for rank, i in enumerate(order)]}
        result = native.parse_response(row, json.dumps(payload), "200")
        self.assertEqual(result["ranking"], [row["input"]["passages"][i]["id"] for i in order])
        self.assertEqual(result["scores"][0]["raw_logit"], 4.0)
        payload["results"][1]["index"] = 2
        with self.assertRaisesRegex(native.QualificationError, "duplicated"):
            native.parse_response(row, json.dumps(payload), "200")

    def test_cpu_provider_proof_rejects_cuda_and_missing_session(self):
        session = f'ORT session created provider="cpu" model_path={native.MODEL_PATH}'
        loaded = f'ONNX reranker: {native.MODEL_PATH} (cross-encoder mode, pool: 1, max_len: 512) provider="cpu"'
        self.assertEqual(native.cpu_proof(session + "\n" + loaded)["provider"], "cpu")
        with self.assertRaisesRegex(native.QualificationError, "not proven CPU"):
            native.cpu_proof((session + "\n" + loaded).replace('provider="cpu"', 'provider="cuda"'))
        with self.assertRaisesRegex(native.QualificationError, "not proven CPU"):
            native.cpu_proof((session + "\n" + loaded).replace('provider="cpu"', 'provider="cpu_fallback"'))
        with self.assertRaisesRegex(native.QualificationError, "exactly one"):
            native.cpu_proof(loaded)

    def test_container_profile_has_only_pinned_binary_bind_mount(self):
        cpu_binary = Path("/ignored/preflight/pinned-cpu-binary")
        command = native.container_command("deposium-passage-cpu-test", cpu_binary)
        self.assertEqual(command[0], "create")
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("/app/cache:rw,nosuid,nodev,size=64m", command)
        self.assertIn("--runtime=runc", command)
        self.assertIn("--memory=4g", command)
        self.assertIn("--cpus=2", command)
        self.assertIn("CUDA_VISIBLE_DEVICES=-1", command)
        self.assertIn("NVIDIA_VISIBLE_DEVICES=void", command)
        self.assertIn("--env=NVIDIA_VISIBLE_DEVICES=void", command)
        self.assertIn("ORT_INTRA_THREADS=2", command)
        self.assertIn("ENABLE_GPU=false", command)
        self.assertIn("OMP_NUM_THREADS=2", command)
        self.assertIn(native.IMAGE, command)
        self.assertEqual([command[i + 1] for i, value in enumerate(command) if value == "--mount"],
                         [f"type=bind,source={cpu_binary},target={native.BINARY_PATH},readonly"])
        self.assertFalse(any(arg == "--volume" or arg.startswith("--gpus") or arg == "--publish" for arg in command))

    def test_cpu_binary_requires_exact_artifact_and_default_only_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "cpu"
            binary.write_bytes(b"CPU-demo")
            fingerprint = binary.with_name(binary.name + ".fingerprint.json")
            fingerprint.write_text(json.dumps({"features": '["default"]'}))
            with patch.object(native, "CPU_BINARY_SIZE", binary.stat().st_size), \
                 patch.object(native, "CPU_BINARY_SHA256", native.sha256_file(binary)), \
                 patch.object(native, "CPU_FINGERPRINT_SHA256", native.sha256_file(fingerprint)):
                proof = native.verify_cpu_binary(binary)
                self.assertEqual(proof["cargo_features"], ["default"])
                self.assertEqual(proof["source_revision"], "unproven_for_host_artifact")
                binary.write_bytes(b"tampered!")
                with self.assertRaisesRegex(native.QualificationError, "SHA-256 or size mismatch"):
                    native.verify_cpu_binary(binary)

    def test_running_binary_hash_gate_rejects_mismatched_mount(self):
        good = subprocess.CompletedProcess([], 0, f"{native.CPU_BINARY_SHA256}  {native.BINARY_PATH}\n", "")
        bad = subprocess.CompletedProcess([], 0, f"{'0' * 64}  {native.BINARY_PATH}\n", "")
        with patch.object(native, "docker_command", return_value=good):
            self.assertEqual(native.verify_running_binary("owned-container"), native.CPU_BINARY_SHA256)
        with patch.object(native, "docker_command", return_value=bad):
            with self.assertRaisesRegex(native.QualificationError, "running CPU binary SHA-256 mismatch"):
                native.verify_running_binary("owned-container")

    def test_stopped_container_copy_reads_mounted_cpu_binary(self):
        cpu_binary = Path("/private/preflight/cpu")
        contents = {native.MODEL_PATH: b"model", native.TOKENIZER_PATH: b"tokenizer",
                    native.ORT_PATH: b"ort", native.BINARY_PATH: b"mounted CPU"}
        hashes = {path: native.sha256_bytes(data) for path, data in contents.items()}
        # The image binary's digest is deliberately different from the mounted CPU executable.
        image_hashes = {**hashes, native.BINARY_PATH: native.sha256_bytes(b"image GPU")}

        def fake_docker(args, **_):
            if args[0] == "cp":
                source = args[1].split(":", 1)[1]
                Path(args[2]).write_bytes(contents[source])
                return subprocess.CompletedProcess(args, 0, "", "")
            template = args[2]
            values = {"{{.Image}}": native.IMAGE,
                      "{{json .HostConfig.Mounts}}": json.dumps([{
                          "Type": "bind", "Source": str(cpu_binary), "Target": native.BINARY_PATH,
                          "ReadOnly": True}]),
                      "{{.HostConfig.ReadonlyRootfs}}": "true",
                      "{{.HostConfig.NetworkMode}}": "none",
                      "{{json .HostConfig.DeviceRequests}}": "null",
                      "{{json .HostConfig.Devices}}": "[]"}
            return subprocess.CompletedProcess(args, 0, values[template] + "\n", "")

        with patch.object(native, "EXPECTED_HASHES", image_hashes), \
             patch.object(native, "CPU_BINARY_SHA256", hashes[native.BINARY_PATH]), \
             patch.object(native, "docker_command", side_effect=fake_docker):
            self.assertEqual(native.verify_prestart("owned-container", cpu_binary), hashes)
            contents[native.BINARY_PATH] = b"image GPU"
            with self.assertRaisesRegex(native.QualificationError, "binary SHA-256 mismatch"):
                native.verify_prestart("owned-container", cpu_binary)

    def test_seal_matches_archive_fingerprint_and_failed_preflight_has_no_docker(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "run"
            with patch.object(native, "require_clean_bench_source", return_value="a" * 40), \
                 patch.object(native, "verify_cpu_binary", return_value={"sha256": native.CPU_BINARY_SHA256}), \
                 patch.object(native, "require_host_memory", side_effect=native.QualificationError("low RAM")), \
                 patch.object(native, "docker_command") as docker:
                with self.assertRaisesRegex(native.QualificationError, "low RAM"):
                    native.execute([case(i) for i in range(128)], b"frozen\n", "a" * 64,
                                   {"max_pair_tokens": 32}, out, 30, Path("/ignored/cpu"))
                docker.assert_not_called()
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["scores_observed"], 0)
            seal = json.loads((out / "seal.json").read_text())
            self.assertEqual(seal["schema_version"], "deposium.archive-seal/v1")
            files = {p.name: native.sha256_file(p) for p in out.iterdir() if p.name != "seal.json"}
            self.assertEqual(seal["files"], files)
            self.assertEqual(seal["sha256"], native.sha256_bytes(
                (json.dumps(files, ensure_ascii=False, sort_keys=True) + "\n").encode()))

    def test_failed_created_container_logs_before_owned_cleanup(self):
        calls = []

        def fake_docker(args, **_):
            calls.append(args[0])
            if args[0] == "create":
                return subprocess.CompletedProcess(args, 0, "own-container-id\n", "")
            if args[0] == "inspect":
                return subprocess.CompletedProcess(args, 0, "1\n", "")
            if args[0] == "logs":
                return subprocess.CompletedProcess(args, 0, "startup diagnostic\n", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "run"
            with patch.object(native, "require_clean_bench_source", return_value="a" * 40), \
                 patch.object(native, "verify_cpu_binary", return_value={"sha256": native.CPU_BINARY_SHA256}), \
                 patch.object(native, "require_host_memory", return_value=16 * 1024 ** 3), \
                 patch.object(native, "docker_command", side_effect=fake_docker), \
                 patch.object(native, "verify_prestart", side_effect=native.QualificationError("bad hash")), \
                 patch.object(native, "read_resource_peaks", side_effect=native.QualificationError("stopped")):
                with self.assertRaisesRegex(native.QualificationError, "bad hash"):
                    native.execute([case(i) for i in range(128)], b"frozen\n", "a" * 64,
                                   {"max_pair_tokens": 32}, out, 30, Path("/ignored/cpu"))
            self.assertLess(calls.index("logs"), calls.index("rm"))
            self.assertIn("startup diagnostic", (out / "container.log").read_text())
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["container_cleanup"], "removed_with_anonymous_volumes")
            self.assertEqual(manifest["status"], "failed")
            self.assertIn("container.log", json.loads((out / "seal.json").read_text())["files"])


if __name__ == "__main__":
    unittest.main()
