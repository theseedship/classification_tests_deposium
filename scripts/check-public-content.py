"""Check only Git's index; never read or print ignored local private contents."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "provider_token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{28,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}|AKIA[A-Z0-9]{16})"),
    "personal_home_path": re.compile(r"/(?:Users|home)/(?!fixture-user/|user/|runner/|example/)[A-Za-z0-9_.-]+/"),
}


def git(*args, **kwargs):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def main():
    rows = [r for r in git("ls-files", "--stage", "-z").split(b"\0") if r]
    findings = Counter()
    names = []
    entries = []
    for row in rows:
        metadata, name = row.split(b"\t", 1)
        mode, _oid, stage = metadata.split()
        if mode not in {b"100644", b"100755"} or stage != b"0":
            findings["unreviewed_index_entry"] += 1
        names.append(name)
        entries.append((mode, name))
    # Git reads ignore rules from the working tree. Refuse a policy that is not
    # exactly the policy being committed, including unindexed ancestor rules.
    indexed = {name.decode("utf-8") for name in names}
    policies = {".gitignore"}
    for name in indexed:
        for parent in Path(name).parents:
            policies.add((parent / ".gitignore").as_posix())
    for name in sorted(policies):
        path = ROOT / name
        if path.is_symlink():
            findings["ignore_policy_drift"] += 1
        elif path.is_file():
            if name not in indexed or path.stat().st_size > 1024 * 1024:
                findings["ignore_policy_drift"] += 1
            elif path.read_bytes() != git("show", ":" + name):
                findings["ignore_policy_drift"] += 1
        elif name in indexed:
            findings["ignore_policy_drift"] += 1
    if findings.get("ignore_policy_drift"):
        print(json.dumps({"status": "failed", "indexed_files": len(rows),
                          "findings": {"ignore_policy_drift": findings["ignore_policy_drift"]},
                          "scope": "ignore rules must match the index"}))
        return 1
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", "--stdin", "-z"],
                             input=b"\0".join(names) + (b"\0" if names else b""),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if ignored.returncode not in (0, 1):
        raise RuntimeError("ignore policy could not be checked")
    private_names = {n for n in ignored.stdout.split(b"\0") if n}
    findings["ignored_path_in_index"] += len(private_names)
    for mode, encoded in entries:
        if encoded in private_names or mode not in {b"100644", b"100755"}:
            continue
        name = encoded.decode("utf-8")
        data = git("show", ":" + name)
        if len(data) > 8 * 1024 * 1024:
            findings["oversized_public_blob"] += 1
            continue
        try:
            value = data.decode("utf-8")
        except UnicodeDecodeError:
            findings["unreviewed_binary_blob"] += 1
            continue
        for rule, pattern in PATTERNS.items():
            if pattern.search(value):
                findings[rule] += 1
    failures = {k: v for k, v in sorted(findings.items()) if v}
    # Never print matching values or potentially confidential filenames.
    print(json.dumps({"status": "failed" if failures else "passed",
                      "indexed_files": len(rows), "findings": failures,
                      "scope": "indexed files only; pattern check, not a proof of absence"}))
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
