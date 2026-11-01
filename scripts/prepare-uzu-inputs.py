#!/usr/bin/env python3
"""Write a `deposium.uzu-input-preparation/v1` receipt for one frozen pack; no weights, no inference.

The exact System One request bodies are built with the shared projection used by
the Uzu adapter, rendered and tokenized by the pinned helper built with
`scripts/build-uzu-preparation.py` (hanashi::decision::DecisionEncoding), and a
synthetic oversized request is prepared as the overflow control. The receipt
maps each request-body SHA-256 to its token count and token-ID digest. It is
written to a new ignored `results/` directory; token IDs and paths stay local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deposium_bench.cases import parse_cases  # noqa: E402
from deposium_bench.systemone_local import native_request  # noqa: E402
from deposium_bench.uzu_local import UZU_REVISION, preparation_map, verify_pack  # noqa: E402

RENDERER = "hanashi::decision::DecisionEncoding"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def overflow_input(limit):
    return {"context": "sentinel " * (limit + 512), "question": "Choose one option.",
            "options": [{"id": str(i), "description": f"Option {i}"} for i in range(4)]}


def prepare(args):
    output = args.output.absolute()
    require(output.resolve().is_relative_to((ROOT / "results").resolve()) and not output.exists(),
            "output must be a new directory under results/")
    pack, assets_path = args.pack.resolve(strict=True), args.assets_manifest.resolve(strict=True)

    def remember(path, expected):
        require(sha(Path(path).read_bytes()) == expected, f"pack file changed: {Path(path).name}")

    verify_pack(pack, assets_path, remember)
    cases, dataset_sha = parse_cases(args.dataset.read_bytes())
    require(cases and all(c["contract_id"] == "bench.context-choice" for c in cases), "choice dataset required")
    bodies = {}
    for case in cases:
        bodies.setdefault(native_request(case["input"], args.model_id)[2], case["case_id"])
    negative = native_request(overflow_input(args.max_tokens), args.model_id)[2]
    lines = [json.dumps({"case_id": f"body-{i}", "native_request_json": body.decode()}, ensure_ascii=False)
             for i, body in enumerate([*bodies, negative])]
    output.mkdir(parents=True)
    (output / "inputs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output / "inputs.jsonl").open("rb") as stdin, (output / "prepared.jsonl").open("xb") as stdout, \
            (output / "stderr.log").open("xb") as stderr:
        code = subprocess.run([str(args.helper), "--pack", str(pack)], stdin=stdin, stdout=stdout, stderr=stderr,
                              timeout=600).returncode
    rows = [json.loads(line) for line in (output / "prepared.jsonl").read_text().splitlines()]
    require(code == 0 and len(rows) == len(lines) and all(r["status"] == "prepared" for r in rows), "uzu preparation failed")
    request_tokens = {}
    for body, row in zip([*bodies, negative], rows):
        ids = json.dumps(row["token_ids"], separators=(",", ":")).encode()
        entry = {"input_tokens": len(row["token_ids"]), "token_ids_sha256": sha(ids)}
        if body is negative:
            overflow = {"request_body_sha256": sha(body), **entry}
        else:
            require(0 < entry["input_tokens"] <= args.max_tokens, "prepared request exceeds the client limit")
            request_tokens[sha(body)] = entry
    receipt = {"schema_version": "deposium.uzu-input-preparation/v1", "uzu_revision": UZU_REVISION,
               "model_id": args.model_id, "assets_sha256": sha(assets_path.read_bytes()), "max_tokens": args.max_tokens,
               "renderer": RENDERER, "weights_loaded": False, "forward_executed": False,
               "request_tokens": request_tokens, "overflow_control": overflow}
    preparation_map(receipt, model_id=args.model_id, assets_sha256=receipt["assets_sha256"], max_tokens=args.max_tokens)
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    counts = sorted(v["input_tokens"] for v in request_tokens.values())
    return {"dataset_sha256": dataset_sha, "requests": len(request_tokens), "min_tokens": counts[0],
            "max_tokens": counts[-1], "overflow_tokens": overflow["input_tokens"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("helper", "pack", "assets-manifest", "dataset", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prepare(args)))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Uzu preparation stopped: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
