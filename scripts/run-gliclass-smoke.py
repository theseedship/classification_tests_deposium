"""Explicit model-only GLiClass smoke through the common adapter; no download."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.adapters import create_adapter, load_profile
from deposium_bench.campaigns import _destination, _encode
from deposium_bench.native_resources import memory_snapshot


def save(path, value):
    with path.open("xb") as stream:
        stream.write(_encode(value))


def smoke(profile_path, output, stack_root):
    profile_path = Path(profile_path).resolve(strict=True)
    profile, profile_sha = load_profile(profile_path)
    if profile["adapter"] != "gliclass":
        raise ValueError("GLiClass profile required")
    output = _destination(output, stack_root)
    save(output / "profile.json", profile)
    with tarfile.open(output / "bench-source.tar", "x") as archive:
        for folder, pattern in (("deposium_bench", "*.py"), ("bridges", "*.py"), ("schemas", "*.json")):
            for path in sorted((ROOT / folder).rglob(pattern)):
                archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
        archive.add(__file__, arcname="scripts/run-gliclass-smoke.py", recursive=False)
    result = {"schema_version": "deposium.gliclass-smoke/v1",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "profile_sha256": profile_sha, "cases_scored": 0,
              "completed": False, "memory_before": memory_snapshot()}
    adapter = None
    try:
        adapter = create_adapter(profile, profile_path)
        result["adapter_initial"] = deepcopy(adapter.provenance)
        if not adapter.provenance.get("available"):
            raise RuntimeError("gliclass_smoke_initialization_failed")
        request = {"contract_id": "bench.context-choice", "input": {
            "context": "A customer says that the same order was charged twice.",
            "question": "Which team should review the request?", "options": [
                {"id": "synthetic-billing", "description": "Payments, charges and refunds"},
                {"id": "synthetic-shipping", "description": "Shipment location and delivery dates"}]}}
        prediction = adapter.predict(request)
        save(output / "choice.json", {"request": request, "response": prediction})
        if prediction["status"] != "ok":
            raise RuntimeError("gliclass_smoke_choice_failed")
        oversized = deepcopy(request)
        oversized["input"]["context"] = "sentinel " * 6000
        refusal = adapter.predict(oversized)
        save(output / "overflow.json", {"state_words": 6000, "response": refusal})
        if (refusal["status"] != "unsupported" or refusal["output"] is not None
                or refusal["raw_output"].get("forward_executed") is not False):
            raise RuntimeError("gliclass_smoke_overflow_not_rejected")
        result["completed"] = True
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if adapter is not None:
            adapter.close()
            result["adapter_final"] = deepcopy(adapter.provenance)
            log = adapter.provenance.get("runtime_log_path")
            if log and Path(log).is_file():
                shutil.copyfile(log, output / "worker.log")
        result["memory_after"] = memory_snapshot()
        save(output / "smoke.json", result)
        hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(output.rglob("*")) if p.is_file()}
        save(output / "seal.json", {"schema_version": "deposium.gliclass-smoke-seal/v1", "files": hashes})
    print(json.dumps({"output": str(output), "completed": result["completed"], "cases_scored": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stack-root", type=Path, required=True)
    args = parser.parse_args()
    smoke(args.profile, args.output, args.stack_root)


if __name__ == "__main__":
    main()
