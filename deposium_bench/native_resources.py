"""Conservative host memory and process-group RSS observations; no side effects."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import subprocess


def _capture(command):
    return subprocess.check_output(command, text=True, timeout=3)


def parse_vm_stat(text):
    match = re.search(r"page size of (\d+) bytes", text)
    if not match:
        raise ValueError("native_memory_page_size_missing")
    pages = {key.strip(): int(value) for key, value in
             re.findall(r"^([^:\n]+):\s+(\d+)\.?$", text, re.M)}
    # Purgeable pages can overlap other categories: do not add them again.
    names = ("Pages free", "Pages inactive", "Pages speculative")
    if not all(name in pages for name in names):
        raise ValueError("native_memory_counters_missing")
    return sum(pages[name] for name in names) * int(match[1]) / 2**20


def memory_snapshot():
    system = platform.system()
    if system == "Linux":
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, _, value = line.partition(":")
            if name in {"MemAvailable", "MemTotal"}:
                values[name + "_mib"] = int(value.split()[0]) / 1024
        if "MemAvailable_mib" not in values:
            raise ValueError("native_memory_unavailable")
        return {**values, "method": "linux_proc_meminfo"}
    if system == "Darwin":
        return {"MemAvailable_mib": parse_vm_stat(_capture(["/usr/bin/vm_stat"])),
                "MemTotal_mib": int(_capture(["/usr/sbin/sysctl", "-n", "hw.memsize"])) / 2**20,
                "method": "macos_free_inactive_speculative_estimate",
                "limitation": "Reclaimable-page estimate, not Linux MemAvailable or a GPU allocation measurement"}
    raise ValueError("native_memory_platform_unsupported")


def process_group_rss_mib(pgid):
    if type(pgid) is not int or pgid <= 1 or pgid == os.getpgrp():
        raise ValueError("native_group_must_be_a_separate_owned_session")
    total = 0
    for line in _capture(["ps", "-axo", "pgid=,rss="]).splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit():
            if int(fields[0]) == pgid:
                total += int(fields[1])
    return total / 1024
