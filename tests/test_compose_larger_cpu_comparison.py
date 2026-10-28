"""The new overview must preserve frozen rows and reject unsealed pilots."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/compose-larger-cpu-comparison.py"
spec = importlib.util.spec_from_file_location("larger_cpu_composer", SCRIPT)
composer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composer)

HIST = ROOT / "docs/evidence/model-comparison-d3-larger-overview-20261011/manifest.json"
ANALYSIS = ROOT / "docs/evidence/model-comparison-d3-larger-20261011/analysis.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture():
    frozen, pins = composer.historical(HIST)
    old = json.loads(ANALYSIS.read_text())
    current = {key: deepcopy(value) for key, value in old.items()}
    current["base"] = {}
    current["mastra"] = {}
    for index, (repo, (revision, adapter)) in enumerate(composer.NEW_MODELS.items()):
        label = ("Nox", "Vela4", "Liquid3")[index]
        for kind in ("base", "mastra"):
            row = deepcopy(frozen[kind]["D3edge"])
            identity = row["identity"]
            identity.update(adapter=adapter, model_repo_id=repo, model_revision=revision,
                            profile_id=label.lower() + "-cpu-context-v1",
                            identity_sha256=digest(f"{label}:identity".encode()),
                            model_assets_sha256=digest(f"{label}:assets".encode()))
            identity["settings"] = {"device": "cpu", "dtype": "float32"}
            if repo == "LiquidAI/d1-3B":
                identity["settings"]["mode"] = "liquid3"
            for field in ("manifest_sha256", "raw_sha256", "seal_sha256", "seal_fingerprint"):
                row["source"][field] = digest(f"{label}:{kind}:{field}".encode())
            current[kind][label] = row
    current["base_ranking"] = sorted(current["base"],
                                     key=lambda label: (-current["base"][label]["counts"]["correct"], label))
    return current, frozen, pins


def sealed_archive(root: Path, name: str, *, kind: str, identity: dict, corrupt=False):
    directory = root / name
    directory.mkdir()
    repo = identity["model_repo_id"]
    revision = identity["model_revision"]
    source = {"dataset_sha256": digest(b"cases\n"), "raw_sha256": digest(b"raw\n")}
    if kind == "base":
        manifest = {"dataset_sha256": source["dataset_sha256"], "case_count": 132,
                    "qualification": "model_isolated", "run_id": "synthetic",
                    "scorer": {"sha256": digest(b"scorer")},
                    "adapter_provenance": {"identity_sha256": identity["identity_sha256"],
                                           "model_repo_id": repo, "model_revision": revision,
                                           "model": {"mode": "liquid3" if repo == "LiquidAI/d1-3B" else "other"}}}
        payload = {"cases.jsonl": b"cases\n", "raw.jsonl": b"raw\n",
                   "profile.json": b"{}\n", "report.md": b"synthetic report\n",
                   "summary.json": (json.dumps({"completion_status": "complete",
                                                "raw_sha256": source["raw_sha256"]}) + "\n").encode()}
        source.update(scorer_sha256=digest(b"scorer"), run_id="synthetic")
    else:
        manifest = {"dataset_sha256": source["dataset_sha256"],
                    "requests_sha256": digest(b"requests\n"),
                    "projection_version": "mastra-read-choice/v1",
                    "qualification": "isolated_model_observation", "case_ids": list(range(24))}
        payload = {"cases.jsonl": b"cases\n", "requests.jsonl": b"requests\n", "raw.jsonl": b"raw\n",
                   "summary.json": b'{"completion_status":"complete"}\n',
                   "adapter-initial.json": (json.dumps({"identity_sha256": identity["identity_sha256"],
                                                     "model_repo_id": repo,
                                                     "model_revision": revision}) + "\n").encode(),
                   "profile.json": (json.dumps({"model": {"mode": "liquid3" if repo == "LiquidAI/d1-3B" else "other"}}) + "\n").encode()}
        source.update(requests_sha256=digest(b"requests\n"),
                      projection_version="mastra-read-choice/v1")
    payload["manifest.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    source["manifest_sha256"] = digest(payload["manifest.json"])
    files = {key: digest(data) for key, data in payload.items()}
    seal = {"schema_version": "deposium.archive-seal/v1", "files": files,
            "sha256": digest((json.dumps(files, ensure_ascii=False, sort_keys=True) + "\n").encode())}
    seal_bytes = (json.dumps(seal, sort_keys=True) + "\n").encode()
    source.update(seal_fingerprint=seal["sha256"], seal_sha256=digest(seal_bytes))
    for filename, data in payload.items():
        (directory / filename).write_bytes(data)
    (directory / "seal.json").write_bytes(seal_bytes)
    if corrupt:
        (directory / "raw.jsonl").write_bytes(b"altered\n")
    return source


class LargerCompositionTests(unittest.TestCase):
    def test_three_only_and_historical_repeated_produce_22_distinct_models(self):
        current, frozen, pins = fixture()
        base, mastra, new = composer.compose(current, frozen)
        self.assertEqual((len(base), len(mastra), len(new)), (22, 22, 3))
        report = composer.render(base, mastra, current_hash="a" * 64,
                                 historical_hash=pins["manifest_sha256"],
                                 producer_hash="b" * 64, archives=[])
        for section in ("Classement général", "Routage Mastra", "domain : documentary",
                        "language : fr", "Ressources, latences"):
            self.assertIn(section, report)
        self.assertIn("22 modèles", report)
        self.assertIn("pending_human", report)
        for label in composer.HISTORICAL_LABELS:
            current["base"][label] = deepcopy(frozen["base"][label])
            current["mastra"][label] = deepcopy(frozen["mastra"][label])
        current["base_ranking"] = sorted(current["base"],
                                         key=lambda n: (-current["base"][n]["counts"]["correct"], n))
        self.assertEqual(composer.compose(current, frozen)[0], base)

    def test_rejects_changed_historical_row_and_bad_pending_reference(self):
        current, frozen, _ = fixture()
        current["base"]["Jev"] = deepcopy(frozen["base"]["Jev"])
        current["mastra"]["Jev"] = deepcopy(frozen["mastra"]["Jev"])
        current["base"]["Jev"]["counts"]["correct"] -= 1
        current["base_ranking"] = sorted(current["base"],
                                         key=lambda n: (-current["base"][n]["counts"]["correct"], n))
        with self.assertRaisesRegex(composer.CompositionError, "frozen historical"):
            composer.compose(current, frozen)
        current, frozen, _ = fixture()
        current["mastra"]["Nox"]["reference_review"] = "approved"
        with self.assertRaisesRegex(composer.CompositionError, "Mastra reference"):
            composer.compose(current, frozen)

    def test_rejects_unreviewed_identity_and_wrong_denominator(self):
        current, frozen, _ = fixture()
        current["base"]["Nox"]["identity"]["model_revision"] = "0" * 40
        with self.assertRaisesRegex(composer.CompositionError, "pinned CPU identity"):
            composer.compose(current, frozen)
        current, frozen, _ = fixture()
        current["base"]["Nox"]["groups"]["language"]["fr"]["total"] = 65
        with self.assertRaisesRegex(composer.CompositionError, "denominator"):
            composer.compose(current, frozen)

    def test_verifies_six_new_archive_seals_and_detects_tampering(self):
        current, frozen, _ = fixture()
        _, _, new = composer.compose(current, frozen)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for label, (base, route) in new.items():
                base["source"] = sealed_archive(root, f"{label}-base", kind="base",
                                                identity=base["identity"])
                route["source"] = sealed_archive(root, f"{label}-mastra", kind="mastra",
                                                 identity=route["identity"])
            proof = composer.verify_archives(new, root)
            self.assertEqual(len(proof), 6)
            self.assertTrue(all(row["files_verified"] >= 3 for row in proof))
            (root / "Nox-base/raw.jsonl").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(composer.CompositionError, "sealed file changed"):
                composer.verify_archives(new, root)

    def test_historical_manifest_bytes_are_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "manifest.json"
            changed.write_bytes(HIST.read_bytes() + b" ")
            with self.assertRaisesRegex(composer.CompositionError, "manifest bytes changed"):
                composer.historical(changed)


if __name__ == "__main__":
    unittest.main()
