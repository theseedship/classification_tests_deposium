"""Synthetic source-only controls; no GPU, network, build, or model calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("uzu_pc_preflight", Path(__file__).resolve().parents[1] / "scripts/preflight-uzu-pc.py")
pc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pc)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.run_git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text("results/\nsource/\n")
        self.run_git(self.source, "init", "-q")
        self.run_git(self.source, "remote", "add", "origin", pc.REPOSITORY)
        content = {
            "Cargo.toml": '[workspace.package]\nversion = "synthetic"\n',
            pc.ENGINE + "Cargo.toml": '[features]\ndefault = ["metal", "cpu"]\nmetal=[]\ncpu=[]\nwebgpu=[]\n',
            pc.KERNEL: "\n".join(
                f'type {name} = Unsupported<WebGPU>;\nimpl {name} for Unsupported<WebGPU> {{ fn new() -> Result<Self, WebGPUError> {{ Err(WebGPUError::NotSupported) }} }}'
                for name in ("AttentionKernel", "MatmulKernel")),
            pc.MATMUL: '<B::Kernels as Kernels>::MatmulKernel::new(context)',
            pc.ATTENTION: '<B::Kernels as Kernels>::AttentionKernel::new(context)',
        }
        for name, text in content.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.commit()
        self.revision = self.run_git(self.source, "rev-parse", "HEAD")
        self.hashes = {name: hashlib.sha256((self.source / name).read_bytes()).hexdigest() for name in content}
        for name, value in (("ROOT", self.root), ("UZU_REVISION", self.revision), ("EXPECTED_HASHES", self.hashes)):
            patcher = patch.object(pc, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = self.root / "results" / "preflight"

    def run_git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.run_git(self.source, "add", ".")
        self.run_git(self.source, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic source")

    def run_preflight(self):
        return pc.preflight(self.source, self.output)

    def test_reviewed_source_is_unsupported_never_pass(self):
        result = self.run_preflight()
        self.assertEqual(result["execution_gate"], "unsupported")
        self.assertEqual(result["cases_scored"], 0)
        self.assertEqual(result["campaign"], "not_run")
        self.assertEqual(result["models"], "not_loaded")
        self.assertEqual(result["actual_backend"], "not_observed")
        self.assertNotIn(str(self.root), json.dumps(result))
        report = json.loads((self.output / "preflight.json").read_text())
        self.assertEqual(report["source_sha256"], self.hashes)
        self.assertEqual(report["engine_features"]["default"], ["metal", "cpu"])

    def test_wrong_origin(self):
        self.run_git(self.source, "remote", "set-url", "origin", "https://example.invalid/synthetic.git")
        self.assertEqual(self.run_preflight()["reason"], "source_origin_mismatch")

    def test_wrong_revision(self):
        with patch.object(pc, "UZU_REVISION", "0" * 40):
            self.assertEqual(self.run_preflight()["reason"], "source_revision_mismatch")

    def test_tracked_dirty(self):
        (self.source / pc.KERNEL).write_text("changed")
        self.assertEqual(self.run_preflight()["reason"], "source_dirty")

    def test_untracked_dirty(self):
        (self.source / "untracked").write_text("synthetic")
        self.assertEqual(self.run_preflight()["reason"], "source_dirty")

    def test_ignored_dirty(self):
        self.run_git(self.source, "config", "core.excludesfile", str(self.root / "excludes"))
        (self.root / "excludes").write_text("ignored\n")
        (self.source / "ignored").write_text("synthetic")
        self.assertEqual(self.run_preflight()["reason"], "source_dirty")

    def test_missing_source(self):
        result = pc.preflight(self.root / "missing", self.output)
        self.assertEqual(result["reason"], "source_missing")

    def test_missing_evidence_is_error(self):
        (self.source / pc.KERNEL).unlink()
        self.commit()
        with patch.object(pc, "UZU_REVISION", self.run_git(self.source, "rev-parse", "HEAD")):
            self.assertEqual(self.run_preflight()["reason"], "source_evidence_missing")

    def test_changed_hash_is_unknown(self):
        with patch.object(pc, "EXPECTED_HASHES", {**self.hashes, pc.KERNEL: "0" * 64}):
            self.assertEqual(self.run_preflight()["execution_gate"], "unknown")

    def test_unknown_implementation_is_not_supported(self):
        (self.source / pc.KERNEL).write_text("type MatmulKernel = NewImplementation;")
        self.commit()
        hashes = {**self.hashes, pc.KERNEL: hashlib.sha256((self.source / pc.KERNEL).read_bytes()).hexdigest()}
        with patch.object(pc, "UZU_REVISION", self.run_git(self.source, "rev-parse", "HEAD")), patch.object(pc, "EXPECTED_HASHES", hashes):
            self.assertEqual(self.run_preflight()["execution_gate"], "unknown")

    def test_output_overwrite_refused(self):
        self.run_preflight()
        original = (self.output / "preflight.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "output_already_exists"):
            self.run_preflight()
        self.assertEqual((self.output / "preflight.json").read_bytes(), original)

    def test_output_outside_results_refused(self):
        with self.assertRaisesRegex(ValueError, "output_must_be_new_directory_under_results"):
            pc.preflight(self.source, self.root / "published")

    def test_symlink_output_escape_refused(self):
        (self.root / "results").mkdir()
        (self.root / "results" / "escape").symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "output_must_be_new_directory_under_results"):
            pc.preflight(self.source, self.root / "results" / "escape" / "report")


if __name__ == "__main__":
    unittest.main()
