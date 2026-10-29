#!/usr/bin/env python3
"""Link a tokenizer-only helper against an existing pinned native runtime build.

Explicit build only: no import-time I/O, downloads, service changes, model reads
or model execution. Existing native source/build inputs remain read-only. Output
and its local path-bearing provenance must stay under this checkout's results/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = "efe3626b119ff81033e309c3ba07a770bef2c546"
REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
HELPER = ROOT / "native/systemone-preflight.cpp"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(part)
    return value.hexdigest()


def captured(command, *, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def make_flags(path, key):
    prefix = key + " = "
    lines = [line[len(prefix):] for line in path.read_text().splitlines() if line.startswith(prefix)]
    require(len(lines) == 1, "missing native compiler flags")
    return shlex.split(lines[0])


def build(source, runtime_build, output):
    source, runtime_build = Path(source).resolve(strict=True), Path(runtime_build).resolve(strict=True)
    output = Path(output).absolute()
    allowed = ROOT / "results"
    require(not allowed.is_symlink() and output.resolve().is_relative_to(allowed.resolve()),
            "helper output must be a new ignored results directory")
    require(not output.exists() and not output.is_symlink(), "helper output already exists")
    require(not output.resolve().is_relative_to(source) and not output.resolve().is_relative_to(runtime_build),
            "helper output cannot modify native source/build")
    require(captured(["git", "rev-parse", "HEAD"], cwd=source) == PIN, "native source revision mismatch")
    require(captured(["git", "remote", "get-url", "origin"], cwd=source) == REPOSITORY,
            "native source repository mismatch")
    require(not captured(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source),
            "native source must remain clean")
    cache = runtime_build / "CMakeCache.txt"
    home = "CMAKE_HOME_DIRECTORY:INTERNAL="
    directories = [line[len(home):] for line in cache.read_text().splitlines() if line.startswith(home)]
    require(len(directories) == 1 and Path(directories[0]).resolve() == source,
            "native build source mismatch")
    flags = runtime_build / "tools/server/CMakeFiles/server-context.dir/flags.make"
    link = runtime_build / "tools/server/CMakeFiles/llama-server.dir/link.txt"
    link_cwd = runtime_build / "tools/server"
    native_command = shlex.split(link.read_text())
    require(native_command and native_command.count("-o") == 1, "invalid native link command")
    # Preserve the C++ driver's basename: resolving c++ -> clang changes linking.
    compiler = Path(native_command[0]).absolute()
    require(compiler.is_file(), "native C++ compiler missing")
    output_index = native_command.index("-o")
    require(output_index + 1 < len(native_command), "missing native executable output")
    executable_output = native_command[output_index + 1]
    native_objects = [arg for arg in native_command[1:] if arg.endswith(".o")]
    require(len(native_objects) == 1 and native_objects[0].endswith("/main.cpp.o"),
            "unexpected native entry-point objects")
    archives = []
    link_flags = []
    index = 1
    while index < len(native_command):
        arg = native_command[index]
        if arg == "-o":
            index += 2
            continue
        if arg in native_objects:
            index += 1
            continue
        if arg.endswith(".a"):
            path = (link_cwd / arg).resolve(strict=True)
            require(path.is_relative_to(runtime_build) and path.is_file(), "native archive escaped build")
            archives.append(path)
            arg = str(path)
        link_flags.append(arg)
        index += 1
    require(any(path.name == "libserver-context.a" for path in archives)
            and any(path.name == "libllama.a" for path in archives), "required native libraries missing")
    dependencies = {str(path): digest(path) for path in (cache, flags, link, compiler, HELPER, Path(__file__), *archives)}
    output.mkdir(parents=True)
    object_path = output / "systemone-preflight.o"
    depfile = output / "systemone-preflight.d"
    binary = output / "systemone-preflight"
    cxx_flags = make_flags(flags, "CXX_FLAGS")
    sdk_roots = [Path(cxx_flags[i + 1]).resolve(strict=True) for i, value in enumerate(cxx_flags)
                 if value == "-isysroot" and i + 1 < len(cxx_flags)]
    compile_command = [str(compiler), *make_flags(flags, "CXX_DEFINES"),
        *make_flags(flags, "CXX_INCLUDES"), *cxx_flags,
        "-MMD", "-MF", str(depfile), "-c", str(HELPER), "-o", str(object_path)]
    link_command = [str(compiler), str(object_path), "-o", str(binary), *link_flags]
    with (output / "build.log").open("xb") as log:
        subprocess.run(compile_command, cwd=link_cwd, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(link_command, cwd=link_cwd, stdout=log, stderr=subprocess.STDOUT, check=True)
    # No model argument is passed: --help returns before any model/vocabulary I/O.
    help_text = captured([str(binary), "--help"])
    dep_text = depfile.read_text().replace("\\\n", " ")
    _, separator, dependency_text = dep_text.partition(":")
    require(separator, "invalid compiler dependency file")
    for item in shlex.split(dependency_text):
        path = Path(item).resolve(strict=True)
        require(path.is_file() and (path.is_relative_to(source) or path.is_relative_to(runtime_build)
                or path == HELPER.resolve() or any(path.is_relative_to(sdk) for sdk in sdk_roots)),
                "unexpected native source dependency")
        dependencies[str(path)] = digest(path)
    for path, expected in dependencies.items():
        require(digest(Path(path)) == expected, "native input changed while building helper")
    require(captured(["git", "rev-parse", "HEAD"], cwd=source) == PIN
            and not captured(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source),
            "native source changed while building helper")
    manifest = {"schema_version": "deposium.native-preflight-build/v1",
        "scope": "local_private_build_provenance_contains_paths_do_not_publish_verbatim",
        "native_repository": REPOSITORY, "native_revision": PIN,
        "native_source": str(source), "native_runtime_build": str(runtime_build),
        "native_executable_output_not_modified": executable_output,
        "helper_source_sha256": digest(HELPER), "builder_sha256": digest(Path(__file__)),
        "compiler_version": captured([str(compiler), "--version"]),
        "compile_command": compile_command, "link_command": link_command,
        "dependency_files_sha256": dict(sorted(dependencies.items())),
        "helper_binary_sha256": digest(binary), "help_output": help_text,
        "model_or_vocabulary_loaded": False, "inference_run": False,
        "validation": "compiled and linked; help path only; native preparation on a model not observed"}
    (output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"status": "built_help_checked_no_model_loaded", "native_revision": PIN,
            "helper_binary_sha256": manifest["helper_binary_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--runtime-build-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build(args.source_dir, args.runtime_build_dir, args.output_dir)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Native preflight build failed; inspect the ignored build log.", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
