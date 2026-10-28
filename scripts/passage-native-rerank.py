#!/usr/bin/env python3
"""Run a frozen passage ranking export through the native TurboV3 CPU path.

Default mode is offline preflight. ``--execute`` creates a short lived,
network isolated container from the pinned image with a separately pinned
CPU-only TurboV3 executable bind mounted over the image's GPU-built binary.
It never changes the active TurboV3 service. Python's tokenizers package is
used only to reject inputs that the native Rust tokenizer would silently
truncate at 512 tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

IMAGE = "sha256:4c5c2098b21735baf7d3b05206c59c5da69fd4a604194ed258802200f4bcb7d2"
MODEL = "bge-reranker-v2-m3"
MODEL_PATH = "/app/local_models/bge-reranker-v2-m3/model_int8.onnx"
TOKENIZER_PATH = "/app/local_models/bge-reranker-v2-m3/tokenizer.json"
ORT_PATH = "/opt/onnxruntime/lib/libonnxruntime.so.1.24.4"
BINARY_PATH = "/usr/local/bin/deposium-turbov3"
CPU_BINARY_SHA256 = "0cca8fc00aeb5dfb15fe2c737ecd23433daed99437b7ebe037a34793176d1759"
CPU_FINGERPRINT_SHA256 = "fe8554f54474197cbe3039759d550ef83ac449699add3733a921ce231d1d68bf"
CPU_BINARY_SIZE = 152601760
EXPECTED_HASHES = {
    MODEL_PATH: "dd1b7800bdfde4afd4aab79ea75752250e11fa043ddc397cbf8e8a1c9a809b44",
    TOKENIZER_PATH: "8bf8afbfd11306bd872018c53bfdf2e160a56f8edbcf49933324404791c148d3",
    ORT_PATH: "1aacefdf0b4afa145d410b2381bbc3db3d978c485fb182c42a2b0b09f91f5310",
    BINARY_PATH: "53aa7c30fd67e92b45eccad89a957b98c302542b8e4421fc71af305808f02acf",
}
DEFAULT_CASE_COUNT = 128
ALLOWED_CASE_COUNTS = (128, 512)
TOP_K = 4
MAX_TOKENS = 512
MAX_SECONDS = 1200
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class QualificationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_cpu_binary(path: Path):
    """Require the separately pinned, no-CUDA Rust artifact before Docker exists."""
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise QualificationError("--cpu-binary must be an absolute regular file, not a symlink")
    if path.stat().st_size != CPU_BINARY_SIZE or sha256_file(path) != CPU_BINARY_SHA256:
        raise QualificationError("CPU binary SHA-256 or size mismatch")
    fingerprint = path.with_name(path.name + ".fingerprint.json")
    if fingerprint.is_symlink() or not fingerprint.is_file() or sha256_file(fingerprint) != CPU_FINGERPRINT_SHA256:
        raise QualificationError("CPU build fingerprint SHA-256 mismatch")
    try:
        metadata = json.loads(fingerprint.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise QualificationError("invalid CPU build fingerprint") from exc
    if json.loads(metadata.get("features", "null")) != ["default"]:
        raise QualificationError("CPU build fingerprint does not prove default-only features")
    return {"file_name": path.name, "sha256": CPU_BINARY_SHA256, "size_bytes": CPU_BINARY_SIZE,
            "fingerprint_file_name": fingerprint.name, "fingerprint_sha256": CPU_FINGERPRINT_SHA256,
            "cargo_features": ["default"], "source_revision": "unproven_for_host_artifact"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_inputs(path: Path, expected_hash: str, expected_count: int = DEFAULT_CASE_COUNT):
    if expected_count not in ALLOWED_CASE_COUNTS:
        raise QualificationError(f"case count must be one of {ALLOWED_CASE_COUNTS}")
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if digest != expected_hash:
        raise QualificationError(f"input SHA-256 mismatch: {digest}")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise QualificationError("ranking JSONL must end with exactly one LF")
    try:
        # splitlines() would split a literal U+2028 inside JSON text.
        rows = [json.loads(line.decode("utf-8"), object_pairs_hook=unique_object)
                for line in raw.split(b"\n")[:-1]]
    except (UnicodeError, ValueError) as exc:
        raise QualificationError("invalid ranking JSONL") from exc
    if len(rows) != expected_count:
        raise QualificationError(f"expected {expected_count} cases; got {len(rows)}")
    seen = set()
    for row in rows:
        if set(row) != {"case_id", "contract_id", "input"} or row["contract_id"] != "bench.passage-rerank":
            raise QualificationError("unexpected ranking request contract")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise QualificationError("blank or duplicate case_id")
        seen.add(case_id)
        value = row["input"]
        if not isinstance(value, dict) or set(value) != {"query", "passages"}:
            raise QualificationError("unexpected ranking input fields")
        if not isinstance(value["query"], str) or not value["query"].strip():
            raise QualificationError("blank query")
        passages = value["passages"]
        if not isinstance(passages, list) or len(passages) != TOP_K:
            raise QualificationError("each case needs four passages")
        passage_ids = set()
        for passage in passages:
            if not isinstance(passage, dict) or set(passage) != {"id", "text"}:
                raise QualificationError("unexpected passage fields")
            if any(not isinstance(passage[k], str) or not passage[k].strip() for k in ("id", "text")):
                raise QualificationError("blank passage field")
            if passage["id"] in passage_ids:
                raise QualificationError("duplicate passage ID")
            passage_ids.add(passage["id"])
    return rows, raw, digest


def token_preflight(rows, tokenizer_path: Path):
    if sha256_bytes(tokenizer_path.read_bytes()) != EXPECTED_HASHES[TOKENIZER_PATH]:
        raise QualificationError("tokenizer SHA-256 mismatch")
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise QualificationError("local tokenizers package required for exact pair-length preflight") from exc
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    lengths = []
    for row in rows:
        query = row["input"]["query"]
        for passage in row["input"]["passages"]:
            length = len(tokenizer.encode(query, passage["text"], add_special_tokens=True).ids)
            if length > MAX_TOKENS:
                raise QualificationError(
                    f"native 512-token truncation would affect {row['case_id']}/{passage['id']}: {length} tokens"
                )
            lengths.append(length)
    return {"pair_count": len(lengths), "max_pair_tokens": max(lengths), "tokenizer_sha256": EXPECTED_HASHES[TOKENIZER_PATH]}


def docker_command(args, *, input_text=None, timeout=30, check=True):
    process = subprocess.run(["docker", *args], input=input_text, text=True, encoding="utf-8",
                             capture_output=True, timeout=timeout, check=False)
    if check and process.returncode:
        raise QualificationError(f"docker {args[0]} failed (exit {process.returncode}): {process.stderr.strip()[:300]}")
    return process


def container_command(name: str, cpu_binary: Path):
    return [
        "create", "--name", name,
        "--label", "deposium.passage-cpu-run=1", "--network=none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m", "--memory=4g", "--memory-swap=4g",
        "--tmpfs", "/app/cache:rw,nosuid,nodev,size=64m", "--runtime=runc",
        "--cpus=2", "--pids-limit=128", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--restart=no", "--no-healthcheck",
        "--mount", f"type=bind,source={cpu_binary},target={BINARY_PATH},readonly",
        "--env=NVIDIA_VISIBLE_DEVICES=void", "--env=CUDA_VISIBLE_DEVICES=-1",
        "--entrypoint=/usr/bin/env", IMAGE, "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "HOST=127.0.0.1", "PORT=11435",
        "MODELS_DIR=/app/local_models", "HF_HOME=/app/local_models/hf-cache", "HF_HUB_OFFLINE=1",
        f"ORT_DYLIB_PATH={ORT_PATH}", "LD_LIBRARY_PATH=/opt/onnxruntime/lib",
        "CUDA_VISIBLE_DEVICES=-1", "NVIDIA_VISIBLE_DEVICES=void",
        "ENABLE_GPU=false", "OMP_NUM_THREADS=2", "OMP_DYNAMIC=false", "RAYON_NUM_THREADS=2",
        "TOKENIZERS_PARALLELISM=false",
        f"DEFAULT_RERANK_MODEL={MODEL}", f"PRELOAD_MODELS={MODEL}", f"PINNED_MODELS={MODEL}",
        "ORT_INTRA_THREADS=2", "RERANK_SESSION_POOL=1", "RERANK_CONCURRENCY=1",
        "EMBEDDING_SESSION_POOL=1", "EMBED_CONCURRENCY=1", "INFERENCE_CONCURRENCY=1",
        "RERANK_MAX_SEQ_LEN=512", "RERANK_ONNX_FILE=model_int8.onnx",
        "MODEL_IDLE_TIMEOUT=0", "INFERENCE_REQUEST_TIMEOUT_SECS=60",
        "RUST_LOG=info", BINARY_PATH,
    ]


def verify_prestart(name: str, cpu_binary: Path):
    """Hash mounted artifacts from the stopped container before preload."""
    image = docker_command(["inspect", "--format", "{{.Image}}", name]).stdout.strip()
    if image != IMAGE:
        raise QualificationError("isolated container image ID mismatch")
    mounts = json.loads(docker_command(["inspect", "--format", "{{json .HostConfig.Mounts}}", name]).stdout)
    expected_mount = {"Type": "bind", "Source": str(cpu_binary), "Target": BINARY_PATH, "ReadOnly": True}
    if mounts != [expected_mount]:
        raise QualificationError("isolated container CPU binary bind mount differs from frozen profile")
    rootfs = docker_command(["inspect", "--format", "{{.HostConfig.ReadonlyRootfs}}", name]).stdout.strip()
    network = docker_command(["inspect", "--format", "{{.HostConfig.NetworkMode}}", name]).stdout.strip()
    if rootfs != "true" or network != "none":
        raise QualificationError("isolated container rootfs or network differs from frozen profile")
    for field in ("DeviceRequests", "Devices"):
        value = docker_command(["inspect", "--format", "{{json .HostConfig." + field + "}}", name]).stdout.strip()
        if json.loads(value) not in (None, []):
            raise QualificationError("isolated container has device access")
    actual = {}
    with tempfile.TemporaryDirectory(prefix="passage-native-artifacts-") as folder:
        for index, path in enumerate(EXPECTED_HASHES):
            copy = Path(folder) / f"artifact-{index}"
            docker_command(["cp", f"{name}:{path}", str(copy)], timeout=90)
            actual[path] = sha256_file(copy)
    expected_mounted = {**EXPECTED_HASHES, BINARY_PATH: CPU_BINARY_SHA256}
    if actual != expected_mounted:
        raise QualificationError("native model, tokenizer, ORT or binary SHA-256 mismatch")
    return actual


def verify_no_gpu_device(name: str):
    devices = docker_command(["exec", name, "sh", "-c", "ls /dev/nvidia* 2>/dev/null"], check=False).stdout.strip()
    if devices:
        raise QualificationError("NVIDIA device present in isolated container")


def verify_running_binary(name: str):
    """Check the mounted executable in the running namespace before requests."""
    result = docker_command(["exec", name, "sha256sum", BINARY_PATH], timeout=20).stdout.strip()
    if result != f"{CPU_BINARY_SHA256}  {BINARY_PATH}":
        raise QualificationError("running CPU binary SHA-256 mismatch")
    return CPU_BINARY_SHA256


def read_resource_peaks(name: str):
    """Whole-container/process peaks; neither value is reranker-only memory."""
    memory = docker_command(["exec", name, "cat", "/sys/fs/cgroup/memory.peak"], timeout=5).stdout.strip()
    process = docker_command(["exec", name, "cat", "/proc/1/status"], timeout=5).stdout
    match = re.search(r"(?m)^VmHWM:\s+(\d+)\s+kB$", process)
    if not memory.isdecimal() or match is None:
        raise QualificationError("container/process memory peak unavailable")
    return {"container_cgroup_memory_peak_bytes": int(memory),
            "server_process_VmHWM_kib": int(match.group(1)),
            "scope": "whole isolated container/process; includes warmup and runtime, not model-only"}


def require_host_memory(minimum_bytes: int):
    try:
        value = re.search(r"(?m)^MemAvailable:\s+(\d+)\s+kB$", Path("/proc/meminfo").read_text())
    except OSError as exc:
        raise QualificationError("host MemAvailable unavailable") from exc
    if value is None:
        raise QualificationError("host MemAvailable unavailable")
    available = int(value.group(1)) * 1024
    if available < minimum_bytes:
        raise QualificationError(f"host MemAvailable below {minimum_bytes} bytes")
    return available


def require_clean_bench_source():
    root = Path(__file__).resolve().parents[1]
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], text=True,
                            encoding="utf-8", capture_output=True, timeout=10, check=True).stdout
    if status.strip():
        raise QualificationError("bench worktree must be committed and clean before inference")
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
                          encoding="utf-8", capture_output=True, timeout=10, check=True).stdout.strip()


def cpu_proof(logs: str):
    clean = ANSI.sub("", logs)
    model_lines = [line for line in clean.splitlines() if "ORT session created" in line and MODEL_PATH in line]
    reranker_lines = [line for line in clean.splitlines() if "ONNX reranker:" in line and MODEL_PATH in line]
    if len(model_lines) != 1 or len(reranker_lines) != 1:
        raise QualificationError("expected exactly one native BGE session and reranker load log")
    for line in model_lines + reranker_lines:
        if not re.search(r'provider="cpu"', line):
            raise QualificationError("native reranker provider is not proven CPU-only")
    if "pool: 1" not in reranker_lines[0] or "max_len: 512" not in reranker_lines[0]:
        raise QualificationError("reranker pool or sequence cap differs from frozen profile")
    return {"provider": "cpu",
            "session_log": model_lines[0], "reranker_log": reranker_lines[0]}


def wait_ready(name: str, deadline: float):
    while time.monotonic() < deadline:
        response = docker_command(["exec", name, "curl", "--silent", "--output", "/dev/null",
                                   "--write-out", "%{http_code}", "--max-time", "2",
                                   "http://127.0.0.1:11435/ready"], timeout=5, check=False)
        if response.returncode == 0 and response.stdout.strip() == "200":
            return
        state = docker_command(["inspect", "--format", "{{.State.Running}}", name]).stdout.strip()
        if state != "true":
            raise QualificationError("isolated TurboV3 exited before readiness")
        time.sleep(1)
    raise QualificationError("isolated TurboV3 readiness timeout")


def parse_response(row, body: str, status: str):
    if status != "200":
        raise QualificationError(f"rerank HTTP {status}")
    try:
        payload = json.loads(body, object_pairs_hook=unique_object)
    except ValueError as exc:
        raise QualificationError("invalid rerank JSON") from exc
    if not isinstance(payload, dict) or payload.get("model") != MODEL:
        raise QualificationError("rerank response model mismatch")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != TOP_K:
        raise QualificationError("rerank response missing four results")
    passages = row["input"]["passages"]
    seen = set()
    scored = []
    for result in results:
        if not isinstance(result, dict) or set(result) != {"index", "document", "relevance_score"}:
            raise QualificationError("unexpected rerank result fields")
        index, score = result["index"], result["relevance_score"]
        if type(index) is not int or index not in range(TOP_K) or index in seen:
            raise QualificationError("rerank indices incomplete or duplicated")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise QualificationError("nonfinite rerank score")
        if result["document"] != passages[index]["text"]:
            raise QualificationError("rerank result text/index mismatch")
        seen.add(index)
        scored.append({"index": index, "passage_id": passages[index]["id"], "raw_logit": score})
    if seen != set(range(TOP_K)):
        raise QualificationError("rerank omitted an index")
    return {"case_id": row["case_id"], "status": "ok", "ranking": [item["passage_id"] for item in scored],
            "scores": scored, "native_response": payload}


def rerank(name: str, row, timeout: int):
    body = json.dumps({"model": MODEL, "query": row["input"]["query"],
                       "documents": [p["text"] for p in row["input"]["passages"]], "top_k": TOP_K},
                      ensure_ascii=False, separators=(",", ":"))
    started = time.monotonic()
    process = docker_command(["exec", "--interactive", name, "curl", "--silent", "--show-error",
                              "--max-time", str(timeout), "--header", "Content-Type: application/json",
                              "--data-binary", "@-", "--write-out", "\n%{http_code}",
                              "http://127.0.0.1:11435/api/rerank"], input_text=body, timeout=timeout + 5,
                             check=False)
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    if process.returncode:
        raise QualificationError(f"rerank transport failed (curl exit {process.returncode})")
    if "\n" not in process.stdout:
        raise QualificationError("rerank response lacks HTTP status")
    response_body, status = process.stdout.rsplit("\n", 1)
    parsed = parse_response(row, response_body, status.strip())
    parsed["latency_ms"] = elapsed_ms
    return parsed


def write_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        target.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        target.flush()
        os.fsync(target.fileno())
    temporary.replace(path)


def write_text_durable(path: Path, value: str):
    with path.open("x", encoding="utf-8") as target:
        target.write(value)
        target.flush()
        os.fsync(target.fileno())


def seal_archive(out: Path):
    files = {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "seal.json"}
    encoded_files = (json.dumps(files, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    seal = {"schema_version": "deposium.archive-seal/v1", "files": files,
            "sha256": sha256_bytes(encoded_files)}
    write_json(out / "seal.json", seal)
    return seal


def append_durable(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def execute(rows, raw: bytes, digest: str, token_stats: dict, out: Path, timeout: int, cpu_binary: Path):
    out.mkdir(parents=True, exist_ok=False)
    (out / "ranking-inputs.jsonl").write_bytes(raw)
    name = "deposium-passage-cpu-" + uuid.uuid4().hex[:12]
    started = time.monotonic()
    archive = {"status": "not_started", "image": IMAGE, "model": MODEL, "input_sha256": digest,
               "container_name": name, "container_label": "deposium.passage-cpu-run=1",
               "case_count": len(rows), "profile": {"top_k": TOP_K, "max_seq_len": MAX_TOKENS,
               "ort_intra_threads": 2, "rerank_session_pool": 1, "cpus": 2, "memory_bytes": 4 * 1024 ** 3,
               "network": "none", "gpu_devices": 0, "runtime": "runc", "rootfs": "read_only",
               "tmpfs": ["/tmp", "/app/cache"]}, "token_preflight": token_stats,
               "source_revision": "unproven_for_image_and_host_binary; artifact_hashes_are_authoritative",
               "scores_observed": 0}
    created = False
    write_json(out / "manifest.json", archive)
    try:
        archive["bench_source_head"] = require_clean_bench_source()
        archive["cpu_binary"] = verify_cpu_binary(cpu_binary)
        write_json(out / "manifest.json", archive)
        archive["host_available_before_bytes"] = require_host_memory(8 * 1024 ** 3)
        process = docker_command(container_command(name, cpu_binary), timeout=30)
        created = bool(process.stdout.strip())
        if not created:
            raise QualificationError("docker create returned no container ID")
        archive["status"] = "container_created"
        archive["container_id"] = process.stdout.strip()
        write_json(out / "manifest.json", archive)
        hashes = verify_prestart(name, cpu_binary)
        archive["mounted_artifact_sha256"] = hashes
        archive["image_original_binary"] = {
            "sha256": EXPECTED_HASHES[BINARY_PATH],
            "observation_archive": "passage-bge-cpu-20261015-001/seal.json",
            "observation_archive_seal_sha256": "b71ab768fffa07a8c70fdcaec0e5fe39a38f283ac6a8db3bfa94891da2d9b638",
            "observation": "stopped-container copy without CPU override from the same pinned image",
            "verified_in_this_run": False,
        }
        archive["status"] = "artifacts_verified_before_start"
        write_json(out / "manifest.json", archive)
        require_host_memory(8 * 1024 ** 3)
        # Recheck the bind source immediately before Docker starts it.
        verify_cpu_binary(cpu_binary)
        docker_command(["start", name], timeout=30)
        archive["running_binary_sha256"] = verify_running_binary(name)
        write_json(out / "manifest.json", archive)
        verify_no_gpu_device(name)
        wait_ready(name, min(started + 120, started + MAX_SECONDS))
        log_result = docker_command(["logs", name], timeout=10)
        logs = log_result.stdout + "\n" + log_result.stderr
        archive["cpu_proof"] = cpu_proof(logs)
        archive["status"] = "running"
        write_json(out / "manifest.json", archive)
        with (out / "native-rows.jsonl").open("x", encoding="utf-8") as raw_rows, \
             (out / "predictions.jsonl").open("x", encoding="utf-8") as predictions:
            for position, row in enumerate(rows):
                attempted = time.monotonic()
                try:
                    remaining = started + MAX_SECONDS - time.monotonic()
                    if remaining <= 6:
                        raise QualificationError("campaign deadline exceeded")
                    require_host_memory(4 * 1024 ** 3)
                    result = rerank(name, row, min(timeout, int(remaining - 5)))
                except (QualificationError, subprocess.TimeoutExpired, OSError, KeyboardInterrupt) as exc:
                    status = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "error"
                    failure = {"case_id": row["case_id"], "status": status,
                               "error": type(exc).__name__ + ": " + str(exc)[:250],
                               "latency_ms": round((time.monotonic() - attempted) * 1000, 3)}
                    append_durable(raw_rows, failure)
                    append_durable(predictions, {k: failure[k] for k in ("case_id", "status", "error")})
                    for remaining_row in rows[position + 1:]:
                        append_durable(predictions, {"case_id": remaining_row["case_id"], "status": "missing"})
                    raise
                append_durable(raw_rows, result)
                append_durable(predictions, {k: result[k] for k in ("case_id", "status", "ranking")})
                archive["scores_observed"] += 1
        archive["resource_peaks"] = read_resource_peaks(name)
        archive["status"] = "complete"
    except KeyboardInterrupt:
        archive["status"] = "interrupted"
        archive["error"] = "KeyboardInterrupt"
        raise
    except (QualificationError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        archive["status"] = "failed"
        archive["error"] = str(exc)[:400]
        raise
    finally:
        if created:
            # Only the freshly generated container name owned by this invocation.
            try:
                label = docker_command(["inspect", "--format",
                                        '{{index .Config.Labels "deposium.passage-cpu-run"}}', name],
                                       timeout=5).stdout.strip()
                if label == "1":
                    try:
                        archive.setdefault("resource_peaks", read_resource_peaks(name))
                    except (QualificationError, subprocess.TimeoutExpired, OSError):
                        archive["resource_peaks_status"] = "unavailable"
                    try:
                        log_result = docker_command(["logs", "--timestamps", name], timeout=15, check=False)
                        write_text_durable(out / "container.log", log_result.stdout + log_result.stderr)
                        archive["container_log_status"] = "captured" if log_result.returncode == 0 else "unavailable"
                    except (QualificationError, subprocess.TimeoutExpired, OSError):
                        archive["container_log_status"] = "unavailable"
                    finally:
                        removed = docker_command(["rm", "--force", "--volumes", name], timeout=20, check=False)
                        archive["container_cleanup"] = "removed_with_anonymous_volumes" if removed.returncode == 0 else "failed"
                else:
                    archive["container_cleanup"] = "refused_label_mismatch"
            except (QualificationError, subprocess.TimeoutExpired, OSError):
                archive["container_cleanup"] = "failed_to_verify_ownership"
            if archive.get("container_cleanup") != "removed_with_anonymous_volumes" and archive["status"] != "interrupted":
                archive["status"] = "failed"
        archive["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        write_json(out / "manifest.json", archive)
        files = sorted(p for p in out.iterdir() if p.is_file())
        (out / "SHA256SUMS").write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in files), encoding="utf-8")
        seal_archive(out)
    if archive["status"] != "complete":
        raise QualificationError("isolated run or container cleanup failed; see archived manifest")
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True, help="frozen ranking-inputs.jsonl export")
    parser.add_argument("--expected-input-sha256", required=True, help="pre-registered 64-hex input digest")
    parser.add_argument("--case-count", type=int, choices=ALLOWED_CASE_COUNTS, default=DEFAULT_CASE_COUNT,
                        help="frozen export size (default: 128; balanced four-rotation run: 512)")
    parser.add_argument("--tokenizer", type=Path, required=True, help="exact BGE tokenizer.json copied from pinned image")
    parser.add_argument("--cpu-binary", type=Path, help="pinned CPU-only TurboV3 executable; required with --execute")
    parser.add_argument("--out", type=Path, help="fresh ignored result directory, required with --execute")
    parser.add_argument("--execute", action="store_true", help="start one isolated native CPU container and score the frozen cases")
    parser.add_argument("--request-timeout", type=int, default=60)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_input_sha256):
        parser.error("--expected-input-sha256 must be lowercase SHA-256")
    if args.request_timeout < 1 or args.request_timeout > 60:
        parser.error("--request-timeout must be 1..60 seconds")
    if args.execute and args.out is None:
        parser.error("--out is required with --execute")
    if args.execute and args.cpu_binary is None:
        parser.error("--cpu-binary is required with --execute")
    try:
        rows, raw, digest = load_inputs(args.inputs, args.expected_input_sha256, args.case_count)
        token_stats = token_preflight(rows, args.tokenizer)
        if not args.execute:
            binary = verify_cpu_binary(args.cpu_binary) if args.cpu_binary is not None else None
            print(json.dumps({"status": "preflight_pass", "input_sha256": digest, "case_count": len(rows),
                              "cpu_binary": binary, **token_stats}, sort_keys=True))
            return 0
        result = execute(rows, raw, digest, token_stats, args.out, args.request_timeout, args.cpu_binary)
        print(json.dumps({"status": result["status"], "scores_observed": result["scores_observed"],
                          "result_dir": str(args.out)}, sort_keys=True))
        return 0
    except (QualificationError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        print(f"native rerank qualification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
