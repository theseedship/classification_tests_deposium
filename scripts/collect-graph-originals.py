#!/usr/bin/env python3
"""Collect an authorized local graph corpus's original PDFs and page text.

This is an explicit, private data collection command. Importing it performs no
I/O. It uses the already running local MCPs container only to read exact S3
objects; PDF inspection and text extraction run on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


MAX_PDF_BYTES = 40 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 90
LOCAL_ENDPOINT = "http://storage-rustfs:9000"
DOC_ID_RE = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9.-]{1,62}\Z")
ROOT = Path(__file__).resolve().parents[1]

# Input travels on stdin. Only the PDF body is written to stdout; Python binds
# that descriptor directly to a mode-0600 .part file. No key or credential is
# passed in argv or included in error output.
NODE_GET_OBJECT = r"""
'use strict';
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
async function main() {
  if (process.env.MINIO_PRIVATE_ENDPOINT &&
      process.env.MINIO_PRIVATE_ENDPOINT !== 'http://storage-rustfs:9000') {
    throw new Error('nonlocal_endpoint');
  }
  const accessKeyId = process.env.MINIO_ACCESS_KEY;
  const secretAccessKey = process.env.MINIO_SECRET_KEY;
  if (!accessKeyId || !secretAccessKey) throw new Error('missing_local_credentials');
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const client = new S3Client({
    endpoint: 'http://storage-rustfs:9000', region: 'us-east-1',
    forcePathStyle: true, credentials: { accessKeyId, secretAccessKey },
    maxAttempts: 1,
  });
  try {
    const result = await client.send(new GetObjectCommand({Bucket: input.bucket, Key: input.key}));
    if (Number(result.ContentLength || 0) > input.maxBytes) throw new Error('pdf_limit');
    let received = 0;
    for await (const chunk of result.Body) {
      received += chunk.length;
      if (received > input.maxBytes) throw new Error('pdf_limit');
      if (!process.stdout.write(chunk)) {
        await new Promise(resolve => process.stdout.once('drain', resolve));
      }
    }
  } finally {
    client.destroy();
  }
}
main().catch(error => {
  const allowed = new Set(['nonlocal_endpoint', 'missing_local_credentials', 'pdf_limit',
    'NoSuchKey', 'NoSuchBucket', 'AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']);
  const safe = allowed.has(error.message) ? error.message
    : allowed.has(error.name) ? error.name
    : ['403', '404', '500', '503'].includes(String(error?.$metadata?.httpStatusCode))
      ? 'http_' + error.$metadata.httpStatusCode : 'object_read_failed';
  process.stderr.write(safe + '\n');
  process.exitCode = 1;
});
"""


class CollectionError(Exception):
    pass


def validate_private_paths(
    files_path: Path, scope_path: Path, output_dir: Path, *, root: Path = ROOT
) -> tuple[Path, Path, Path]:
    """Confine inputs and outputs before reading any private metadata.

    Resolve existing symlinks, then ask Git whether each input and destination
    is actually ignored in this checkout. A tracked child under the output is
    rejected even if the enclosing directory matches an ignore rule.
    """
    root = root.resolve(strict=True)
    private_roots = tuple(
        (root / name).resolve() for name in ("results", "datasets/private", "data/private")
    )
    inputs = (files_path.resolve(strict=True), scope_path.resolve(strict=True))
    output = output_dir.resolve()
    results_root = (root / "results").resolve()
    if any(not base.is_relative_to(root) for base in private_roots):
        raise CollectionError("private_root_symlink_escape")
    if any(not path.is_file() or not any(path.is_relative_to(base) for base in private_roots)
           for path in inputs):
        raise CollectionError("input_not_in_ignored_private_directory")
    if output == results_root or not output.is_relative_to(results_root):
        raise CollectionError("output_not_under_results")
    paths_to_check = (*inputs, output, output / "originals",
                      output / "original-documents.private.json")
    for path in paths_to_check:
        relative = str(path.relative_to(root))
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if ignored.returncode != 0:
            raise CollectionError("private_path_not_git_ignored")
        tracked = subprocess.run(
            ["git", "ls-files", "--cached", "-z", "--", relative], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if tracked.returncode != 0 or tracked.stdout:
            raise CollectionError("private_output_or_input_tracked")
    return inputs[0], inputs[1], output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def parse_sources(files_path: Path, scope_path: Path) -> list[dict]:
    files = json.loads(files_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    if not isinstance(files, list) or len(files) != 9 or not isinstance(scope, dict):
        raise CollectionError("expected_nine_files_and_scope")
    owner = scope.get("owner_tenant_id")
    folders = {str(value) for value in scope.get("folder_ids", [])}
    if not isinstance(owner, str) or len(folders) != 9 or not all(
        re.fullmatch(r"[1-9][0-9]*", folder) for folder in folders
    ):
        raise CollectionError("invalid_scope")
    seen_docs: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    expected_total = 0
    normalized: list[dict] = []
    for file in files:
        if not isinstance(file, dict):
            raise CollectionError("invalid_file_metadata")
        doc_id = file.get("document_id")
        bucket = file.get("bucket_name")
        key = file.get("filepath")
        folder_path = file.get("bucket_path")
        size = file.get("size")
        pages = file.get("num_pages")
        if not isinstance(doc_id, str) or not DOC_ID_RE.fullmatch(doc_id):
            raise CollectionError("invalid_document_id")
        if not isinstance(bucket, str) or not BUCKET_RE.fullmatch(bucket):
            raise CollectionError("invalid_bucket")
        if not isinstance(folder_path, str) or not isinstance(key, str):
            raise CollectionError("invalid_storage_key")
        parts = folder_path.split("/")
        if (
            len(parts) != 2
            or parts[0] != owner
            or parts[1] not in folders
            or not key.startswith(folder_path + "/")
            or not key.lower().endswith(".pdf")
            or ".." in Path(key).parts
        ):
            raise CollectionError("storage_key_outside_scope")
        if file.get("user_id") != owner or file.get("mime_type") != "application/pdf":
            raise CollectionError("file_outside_scope_or_not_pdf")
        if file.get("active") is not True:
            raise CollectionError("inactive_file")
        if isinstance(size, bool) or not isinstance(size, int) or size < 4 or size > MAX_PDF_BYTES:
            raise CollectionError("pdf_size_limit")
        if isinstance(pages, bool) or not isinstance(pages, int) or pages < 1:
            raise CollectionError("invalid_page_count")
        if doc_id in seen_docs or (bucket, key) in seen_keys:
            raise CollectionError("duplicate_document_or_object")
        seen_docs.add(doc_id)
        seen_keys.add((bucket, key))
        expected_total += size
        normalized.append({
            "doc_id": doc_id,
            "name": file.get("file_name"),
            "folder_id": parts[1],
            "bucket": bucket,
            "key": key,
            "size": size,
            "num_pages": pages,
        })
    if expected_total > MAX_TOTAL_BYTES or sum(x["num_pages"] for x in normalized) != 396:
        raise CollectionError("corpus_size_or_page_limit")
    if {x["folder_id"] for x in normalized} != folders:
        raise CollectionError("folder_coverage_mismatch")
    if any(not isinstance(x["name"], str) or not x["name"] for x in normalized):
        raise CollectionError("missing_document_name")
    return sorted(normalized, key=lambda item: item["doc_id"])


def download_pdf(
    source: dict, path: Path, *, remaining_bytes: int, resume: bool = False
) -> int:
    part = path.with_suffix(".pdf.part")
    if path.exists():
        raise CollectionError("output_exists")
    if part.exists():
        if not resume:
            raise CollectionError("partial_exists_use_resume")
        retry = 2
        while part.exists():
            part = path.with_suffix(f".pdf.retry-{retry}.part")
            retry += 1
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    payload = json.dumps({
        "bucket": source["bucket"], "key": source["key"],
        "maxBytes": min(MAX_PDF_BYTES, remaining_bytes),
    }).encode("utf-8")
    with os.fdopen(fd, "wb") as output:
        process = subprocess.Popen(
            ["docker", "exec", "-i", "deposium-mcps", "node", "-e", NODE_GET_OBJECT],
            stdin=subprocess.PIPE, stdout=output, stderr=subprocess.PIPE,
        )
        try:
            _, stderr = process.communicate(input=payload, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise CollectionError("download_timeout_part_retained") from None
        output.flush()
        os.fsync(output.fileno())
    if process.returncode != 0:
        # The Node bridge emits only a fixed error code, never a storage key.
        reason = stderr.decode("ascii", errors="ignore").strip()
        if reason not in {"nonlocal_endpoint", "missing_local_credentials", "pdf_limit",
                          "NoSuchKey", "NoSuchBucket", "AccessDenied", "InvalidAccessKeyId",
                          "SignatureDoesNotMatch", "http_403", "http_404", "http_500", "http_503"}:
            reason = "object_read_failed"
        raise CollectionError(reason + "_part_retained")
    actual_size = part.stat().st_size
    if actual_size != source["size"] or actual_size > MAX_PDF_BYTES or actual_size > remaining_bytes:
        raise CollectionError("pdf_size_mismatch_part_retained")
    with part.open("rb") as stream:
        if stream.read(4) != b"%PDF":
            raise CollectionError("invalid_pdf_magic_part_retained")
    os.link(part, path)
    part.unlink()
    return actual_size


def page_count(pdf_path: Path) -> int:
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)], capture_output=True, timeout=30, check=True
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise CollectionError("pdfinfo_failed") from error
    match = re.search(rb"^Pages:\s*([0-9]+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise CollectionError("pdfinfo_missing_pages")
    return int(match.group(1))


def extract_pages(source: dict, pdf_path: Path, originals_dir: Path) -> tuple[list[dict], list[int]]:
    actual_pages = page_count(pdf_path)
    if actual_pages != source["num_pages"]:
        raise CollectionError("pdf_page_count_mismatch")
    page_dir = originals_dir / source["doc_id"]
    page_dir.mkdir(mode=0o700, exist_ok=False)
    pages: list[dict] = []
    empty: list[int] = []
    for number in range(1, actual_pages + 1):
        try:
            extracted = subprocess.run(
                ["pdftotext", "-f", str(number), "-l", str(number), "-layout",
                 "-nopgbrk", "-enc", "UTF-8", str(pdf_path), "-"],
                capture_output=True, timeout=30, check=True,
            ).stdout
            decoded = extracted.decode("utf-8", errors="strict")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, UnicodeDecodeError) as error:
            raise CollectionError("page_text_extraction_failed") from error
        if not decoded.strip():
            empty.append(number)
        page_path = page_dir / f"page-{number:04d}.txt"
        private_file(page_path, extracted)
        pages.append({
            "number": number,
            "path": str(page_path.relative_to(originals_dir.parent)),
            "sha256": hashlib.sha256(extracted).hexdigest(),
        })
    return pages, empty


def collect(
    files_path: Path, scope_path: Path, output_dir: Path, *, resume: bool = False,
    root: Path = ROOT,
) -> dict:
    files_path, scope_path, output_dir = validate_private_paths(
        files_path, scope_path, output_dir, root=root
    )
    sources = parse_sources(files_path, scope_path)
    originals_dir = output_dir / "originals"
    manifest_path = output_dir / "original-documents.private.json"
    if manifest_path.exists() or (originals_dir.exists() and not resume):
        raise CollectionError("output_exists")
    if not output_dir.is_dir():
        raise CollectionError("output_directory_missing")
    if resume and originals_dir.exists() and any(
        child.suffix == ".pdf" or child.is_dir() for child in originals_dir.iterdir()
    ):
        raise CollectionError("resume_after_completed_pdf_unsupported")
    originals_dir.mkdir(mode=0o700, exist_ok=resume)
    documents: list[dict] = []
    downloaded_bytes = 0
    for index, source in enumerate(sources, start=1):
        pdf_path = originals_dir / (source["doc_id"] + ".pdf")
        downloaded_bytes += download_pdf(
            source, pdf_path, remaining_bytes=MAX_TOTAL_BYTES - downloaded_bytes, resume=resume
        )
        if downloaded_bytes > MAX_TOTAL_BYTES:
            raise CollectionError("total_pdf_limit")
        pages, empty = extract_pages(source, pdf_path, originals_dir)
        documents.append({
            "doc_id": source["doc_id"],
            "name": source["name"],
            "folder_id": source["folder_id"],
            "path": str(pdf_path.relative_to(output_dir)),
            "sha256": sha256_file(pdf_path),
            "pages": pages,
            "page_completeness_observed": {
                "metadata_pages": source["num_pages"],
                "pdfinfo_pages": len(pages),
                "extracted_pages": len(pages),
                "empty_text_pages": empty,
                "status": "all_pages_extracted",
                "ocr_performed": False,
            },
        })
        print(f"collected {index}/{len(sources)} PDFs; {len(pages)} pages", flush=True)
    manifest = {
        "schema_version": "deposium.graph-original-documents/v1",
        "source_files_sha256": sha256_file(files_path),
        "source_scope_sha256": sha256_file(scope_path),
        "collection": {
            "document_count": len(documents),
            "page_count": sum(len(doc["pages"]) for doc in documents),
            "empty_text_page_count": sum(
                len(doc["page_completeness_observed"]["empty_text_pages"]) for doc in documents
            ),
            "pdf_bytes": downloaded_bytes,
            "local_endpoint": LOCAL_ENDPOINT,
            "source_runtime": "deposium-mcps",
            "pdf_text_tool": "pdftotext -layout -nopgbrk -enc UTF-8",
        },
        "documents": documents,
    }
    temp_manifest = manifest_path.with_suffix(".json.part")
    private_file(temp_manifest, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    os.link(temp_manifest, manifest_path)
    temp_manifest.unlink()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true",
                        help="retry initial .part downloads only, before any PDF has completed")
    args = parser.parse_args()
    try:
        manifest = collect(args.files, args.scope, args.output, resume=args.resume)
    except (CollectionError, OSError, ValueError, json.JSONDecodeError) as error:
        code = str(error) if isinstance(error, CollectionError) else "collection_io_or_metadata_error"
        print(f"collection failed: {code}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "complete", **manifest["collection"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
