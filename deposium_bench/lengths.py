"""Frozen context variants, measured with a pinned tokenizer and no inference."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

from .adapters import load_profile
from .cases import load_cases, validate_cases
from .choice_protocol import choice_row

ROOT = Path(__file__).resolve().parent.parent
VERSION = "deposium.length-generator/v1"
WORKER = ROOT / "bridges/tokenizer-worker.py"
DEFAULT_TARGETS = (100, 250, 500, 1000, 2000, 4000, 8000)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class ReferenceTokenizer:
    """Uses the explicitly configured local runtime, but only imports tokenizers."""
    def __init__(self, profile_path):
        self.process = None
        self.buffer = bytearray()
        path = Path(profile_path).resolve()
        profile, _ = load_profile(path)
        if profile["adapter"] != "julia" or profile["capabilities"] != ["bench.context-choice"]:
            raise ValueError("Length generation requires the isolated context-choice profile.")
        model = profile["model"]
        self.path = (path.parent / model["local_dir"] / "tokenizer/tokenizer.json").resolve()
        assets_path = path.parent / model["assets_manifest"]
        assets = json.loads(assets_path.read_text())
        if assets["revision"] != profile["revision"] or assets["repo_id"] != model["repo_id"]:
            raise ValueError("Tokenizer manifest identity does not match profile.")
        expected = next(item for item in assets["files"] if item["path"] == "tokenizer/tokenizer.json")
        digest = sha(self.path)
        if expected["sha256"] != digest or expected["size"] != self.path.stat().st_size:
            raise ValueError("Pinned tokenizer bytes changed.")
        self.provenance = {"repo_id": model["repo_id"], "revision": profile["revision"],
                           "sha256": digest, "worker_sha256": sha(WORKER),
                           "format": "Julia strict choice encoding; special tokens included; unpadded"}
        self._file_state = self.path.stat()
        runtime_python = os.path.abspath(path.parent / model["runtime_python"])
        self.process = subprocess.Popen([runtime_python, "-I", "-B", str(WORKER), str(self.path)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        env={"PATH": os.defpath, "TOKENIZERS_PARALLELISM": "false"})
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)
        try:
            if self._read(time.monotonic() + 20) != {"ready": True}:
                raise ValueError("Tokenizer failed to initialize.")
        except BaseException:
            self.close()
            raise

    def _read(self, deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                if selector.select(.05):
                    chunk = os.read(self.process.stdout.fileno(), 65536)
                    if not chunk:
                        raise ValueError("Tokenizer process exited.")
                    self.buffer.extend(chunk)
                    if len(self.buffer) > 1024 * 1024:
                        raise ValueError("Tokenizer response exceeds limit.")
                    if b"\n" in self.buffer:
                        line, _, rest = self.buffer.partition(b"\n")
                        if rest:
                            raise ValueError("Unexpected tokenizer response.")
                        self.buffer.clear()
                        return json.loads(line)
        raise ValueError("Tokenizer timed out.")

    def counts(self, texts):
        state = self.path.stat()
        if (state.st_size, state.st_mtime_ns, state.st_ctime_ns) != (
                self._file_state.st_size, self._file_state.st_mtime_ns, self._file_state.st_ctime_ns):
            raise ValueError("Tokenizer changed during generation.")
        payload = encode(texts)
        if len(payload) > 1024 * 1024:
            raise ValueError("Tokenization request exceeds limit.")
        deadline = time.monotonic() + 20
        sent = 0
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdin, selectors.EVENT_WRITE)
            while sent < len(payload):
                if time.monotonic() > deadline:
                    raise ValueError("Tokenizer input timed out.")
                if selector.select(.05):
                    sent += os.write(self.process.stdin.fileno(), payload[sent:sent + 32768])
        values = self._read(deadline)
        if (not isinstance(values, list) or len(values) != len(texts)
                or any(type(value) is not int or value < 0 for value in values)):
            raise ValueError("Invalid tokenizer counts.")
        return values

    def measure(self, input_value):
        row = choice_row(input_value)
        values = self.counts([row["state"], "choice question: " + row["question"],
                              *(" " + option for option in row["options"])])
        content, question, *options = values
        head = question + sum(options) + len(options) + 4
        total = content + head
        return {"content_tokens": content, "head_tokens": head, "actual_tokens": total,
                "padded_tokens": (total + 7) // 8 * 8, "option_tokens": options,
                "question_tokens": question}

    def close(self):
        if self.process is not None:
            process, self.process = self.process, None
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _sentences(domain, language, count):
    """Scoped synthetic annexes: varied wording, never facts about the active case."""
    pools = json.loads((ROOT / "deposium_bench/data/context-distractors.json").read_text())
    templates = pools[domain][language]
    for index in range(count):
        # Each indexed annex concerns another record/exercise/sample explicitly.
        yield templates[index % len(templates)].format(n=index + 1,
                                                       code=chr(65 + index // len(templates) % 26))


def _context(base, sentences, number, position):
    used = sentences[:number]
    boundary = 0 if position == "start" else number if position == "end" else number // 2
    return "\n\n".join([*used[:boundary], base, *used[boundary:]])


def validate_variant_input(case):
    """Reject changed facts or arbitrary additions disguised as frozen annexes."""
    meta = case["evaluation"]
    length = meta["length"]
    original = meta["oracle"]["base_input"]
    context = case["input"]["context"]
    base = original["context"]
    if context.count(base) != 1:
        raise ValueError("Length variant must contain its base facts exactly once.")
    before, after = context.split(base)
    prefix = [] if not before else before.removesuffix("\n\n").split("\n\n")
    suffix = [] if not after else after.removeprefix("\n\n").split("\n\n")
    count = len(prefix) + len(suffix)
    if count > 20000:
        raise ValueError("Too many context annexes.")
    sentences = list(_sentences(meta["domain"], case["language"], count))
    if context != _context(base, sentences, count, length["position"]):
        raise ValueError("Context differs from the frozen scoped annex protocol.")
    expected = original["options"] if length["order"] == "original" else original["options"][::-1]
    if case["input"]["options"] != expected:
        raise ValueError("Option order differs from its annotation.")
    if length["base_input_sha256"] != hashlib.sha256(encode(original)).hexdigest():
        raise ValueError("Length variant base input hash mismatch.")
    expected_id = f"{meta['base_case_id']}--t{length['target_tokens']:05d}--{length['position']}--{length['order']}"
    if case["case_id"] != expected_id:
        raise ValueError("Length variant identity differs from its annotation.")


def make_variant(case, target, position, order, counter):
    variant = deepcopy(case)
    value = variant["input"]
    if order == "reversed":
        value["options"].reverse()
    base = value["context"]
    sentences = list(_sentences(case["evaluation"]["domain"], case["language"], target // 4 + 32))
    best, measured = base, counter.measure(value)
    # Bracket first; avoid tokenizing huge annexes for a short target.
    low, high = 0, 0
    best_distance = abs(measured["actual_tokens"] - target)
    if measured["actual_tokens"] < target:
        high = 1
        while high < len(sentences):
            trial = counter.measure({**value, "context": _context(base, sentences, high, position)})
            if trial["actual_tokens"] >= target:
                break
            low, high = high, min(high * 2, len(sentences))
    # Search complete sentences; keep the closest whole-context variant.
    while low <= high:
        middle = (low + high) // 2
        context = _context(base, sentences, middle, position)
        trial = counter.measure({**value, "context": context})
        distance = abs(trial["actual_tokens"] - target)
        if distance < best_distance:
            best, measured, best_distance = context, trial, distance
        if trial["actual_tokens"] < target:
            low = middle + 1
        elif trial["actual_tokens"] > target:
            high = middle - 1
        else:
            break
    value["context"] = best
    length = {key: measured[key] for key in ("actual_tokens", "content_tokens", "head_tokens", "padded_tokens")}
    length.update(target_tokens=target, position=position, order=order,
                  tokenizer_sha256=counter.provenance["sha256"], tokenizer_revision=counter.provenance["revision"],
                  base_input_sha256=hashlib.sha256(encode(case["input"])).hexdigest(), generator_version=VERSION,
                  within_target=best_distance <= max(1, target * .05))
    variant["evaluation"]["length"] = length
    variant["case_id"] = f"{case['case_id']}--t{target:05d}--{position}--{order}"
    return variant


def build_lengths(dataset_path, profile_path, output_dir, *, targets=DEFAULT_TARGETS,
                  positions=("middle",), orders=("original",), counter=None):
    """Write a new corpus and its generation manifest, with infeasible targets visible."""
    cases, digest = load_cases(dataset_path)
    if any(case.get("evaluation", {}).get("length", "absent") is not None for case in cases):
        raise ValueError("Length generation requires v2 base cases, not existing variants.")
    for values, allowed, name in ((positions, {"start", "middle", "end"}, "positions"),
                                  (orders, {"original", "reversed"}, "orders")):
        if not values or len(set(values)) != len(values) or set(values) - allowed:
            raise ValueError(f"Invalid or duplicate {name}.")
    if (not targets or any(type(target) is not int or not 32 <= target <= 32768 for target in targets)
            or len(set(targets)) != len(targets) or len(cases) * len(targets) * len(positions) * len(orders) > 20000):
        raise ValueError("Invalid targets or generation exceeds 20000 cases.")
    destination = Path(output_dir).resolve()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Output exists.")
    owned = counter is None
    counter = counter or ReferenceTokenizer(profile_path)
    try:
        variants = [make_variant(case, target, position, order, counter)
                    for target in targets for position in positions for order in orders for case in cases]
        validate_cases(variants)
        payload = b"".join(encode(case) for case in variants)
        manifest = {"schema_version": "deposium.length-dataset/v1", "generator_version": VERSION,
                    "generator_sha256": sha(__file__),
                    "distractors_sha256": sha(ROOT / "deposium_bench/data/context-distractors.json"),
                    "source_dataset_sha256": digest, "dataset_sha256": hashlib.sha256(payload).hexdigest(),
                    "base_cases": len(cases), "families": len({c["translation_family"] for c in cases}),
                    "case_count": len(variants), "targets": list(targets), "positions": list(positions),
                    "orders": list(orders), "reference_tokenizer": counter.provenance,
                    "eligible_cases": sum(c["evaluation"]["length"]["within_target"] for c in variants),
                    "infeasible_case_ids": [c["case_id"] for c in variants if not c["evaluation"]["length"]["within_target"]],
                    "tolerance_fraction": .05, "evaluation_status": "not_run", "human_review": "not_performed",
                    "limitations": ["Annexes are synthetic scoped distractors, not real long documents.",
                                    "Variant positions and translations are correlated within a family.",
                                    "Input annotations stay outside candidate-visible context."]}
        destination.mkdir(parents=True)
        (destination / "cases.jsonl").write_bytes(payload)
        (destination / "manifest.json").write_bytes(encode(manifest))
        return manifest
    finally:
        if owned:
            counter.close()
