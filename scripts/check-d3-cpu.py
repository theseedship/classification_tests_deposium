"""Explicit synthetic CPU contract/overflow control; never a benchmark score."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.adapters import create_adapter, load_profile
from deposium_bench.campaigns import _encode, _write_new, _source_fingerprint
from deposium_bench.native_resources import memory_snapshot


def check(profile_path, output):
    profile, digest = load_profile(profile_path)
    if profile["adapter"] != "d3":
        raise ValueError("D3 profile required")
    output = Path(output)
    if output.exists():
        raise FileExistsError("control archive must be new")
    before = memory_snapshot()
    from deposium_bench.d3_adapter import minimum_available_mib
    if before.get("MemAvailable_mib", 0) < minimum_available_mib(profile["model"]["repo_id"]):
        raise ValueError("insufficient RAM before control archive")
    source = _source_fingerprint()
    output.mkdir(parents=True)
    request = {"context": "Les documents sont stockés dans le dossier Atlas.",
               "question": "Quel dossier contient les documents ?",
               "options": [{"id": "a", "description": "Le dossier Atlas"},
                           {"id": "b", "description": "Le dossier Boréal"}]}
    records = []
    adapter = create_adapter(profile, profile_path)
    try:
        for name, context in (("short", request["context"]), ("overflow", "bonjour " * 10000)):
            value = dict(request, context=context)
            start = time.perf_counter()
            result = adapter.predict({"contract_id": "bench.context-choice", "input": value})
            records.append({"control": name, "request": value, "result": result,
                            "duration_ms": (time.perf_counter() - start) * 1000})
    finally:
        adapter.close()
    short, overflow = [record["result"] for record in records]
    valid = (short["status"] == "ok" and (short.get("raw_output") or {}).get("forward_executed") is True
             and overflow["status"] == "unsupported"
             and (overflow.get("raw_output") or {}).get("forward_executed") is False)
    manifest = {"schema_version": "deposium.d3-control/v1", "scope": "synthetic_contract_only",
                "profile_sha256": digest, "source": source, "memory_before": before,
                "adapter": adapter.provenance,
                "peak_observed_rss_mb": getattr(adapter, "_peak_rss_mb", None),
                "controls_passed": valid, "scored_cases": 0}
    _write_new(output / "manifest.json", _encode(manifest))
    _write_new(output / "raw.jsonl", b"".join(_encode(record) for record in records))
    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir())}
    _write_new(output / "seal.json", _encode({"schema_version": "deposium.archive-seal/v1", "files": files,
                                              "sha256": hashlib.sha256(_encode(files)).hexdigest()}))
    print("synthetic_controls=" + ("pass" if valid else "fail") + "; scored_cases=0")
    return 0 if valid else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(check(args.profile, args.output))
