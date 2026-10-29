"""Build-scope and provenance controls; no compiler, model or native API runs."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_preflight_builder", ROOT / "scripts/build-systemone-preflight.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def snapshot(root):
    # Only newly allocated temporary fixtures are inventoried here.
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class NativePreflightBuilderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.checkout = self.root / "bench"
        self.source = self.root / "native-source"
        self.native = self.root / "native-build"
        self.output = self.checkout / "results" / "new-helper"
        for directory in (self.source, self.checkout / "native", self.native / "tools/server",
                          self.native / "src"):
            directory.mkdir(parents=True)
        self.helper = self.checkout / "native/systemone-preflight.cpp"
        self.helper.write_text("// synthetic helper source fixture, never compiled\n")
        (self.source / "header.h").write_text("// synthetic native header\n")
        self.compiler_target = self.root / "clang"
        self.compiler_target.write_bytes(b"synthetic compiler, never executed")
        self.compiler = self.root / "c++"
        self.compiler.symlink_to(self.compiler_target.name)
        self.flags = self.native / "tools/server/CMakeFiles/server-context.dir/flags.make"
        self.link = self.native / "tools/server/CMakeFiles/llama-server.dir/link.txt"
        self.flags.parent.mkdir(parents=True)
        self.link.parent.mkdir(parents=True)
        self.flags.write_text("CXX_DEFINES = -DGGML_USE_CPU\n"
                              f"CXX_INCLUDES = -I{self.source}\n"
                              "CXX_FLAGS = -O3 -std=gnu++17\n")
        self.link.write_text(shlex.join([str(self.compiler), "-O3",
            "CMakeFiles/llama-server.dir/main.cpp.o", "-o", "../../bin/llama-server",
            "libserver-context.a", "../../src/libllama.a", "-lm"]) + "\n")
        (self.native / "CMakeCache.txt").write_text(f"CMAKE_HOME_DIRECTORY:INTERNAL={self.source}\n")
        self.library = self.native / "tools/server/libserver-context.a"
        self.library.write_bytes(b"synthetic native archive")
        (self.native / "src/libllama.a").write_bytes(b"synthetic llama archive")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(builder, "ROOT", self.checkout))
        stack.enter_context(patch.object(builder, "HELPER", self.helper))
        self.commands = []

    def captured(self, command, *, cwd=None):
        self.commands.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            self.assertEqual(cwd, self.source)
            return builder.PIN
        if command == ["git", "remote", "get-url", "origin"]:
            return builder.REPOSITORY
        if command == ["git", "status", "--porcelain", "--untracked-files=all"]:
            return ""
        if command == [str(self.compiler), "--version"]:
            return "synthetic C++ driver version"
        if command == [str(self.output / "systemone-preflight"), "--help"]:
            return "synthetic help response; no model opened"
        raise AssertionError("unexpected command in build-only fixture")

    def simulated_compile(self, command, *, cwd, stdout, stderr, check):
        self.assertEqual(cwd, self.native / "tools/server")
        self.assertTrue(check)
        self.assertEqual(command[0], str(self.compiler))
        self.assertNotIn("--model", command)
        destination = Path(command[command.index("-o") + 1])
        self.assertTrue(destination.is_relative_to(self.output))
        destination.write_bytes(b"synthetic object" if "-c" in command else b"synthetic helper binary")
        if "-c" in command:
            depfile = Path(command[command.index("-MF") + 1])
            depfile.write_text(f"{destination}: {self.helper} {self.source / 'header.h'}\n")

    def test_flags_parser_preserves_quoted_arguments_and_rejects_missing_or_ambiguous_keys(self):
        self.flags.write_text('CXX_FLAGS = -O3 -I"a path with spaces" -std=gnu++17\n')
        self.assertEqual(builder.make_flags(self.flags, "CXX_FLAGS"),
                         ["-O3", "-Ia path with spaces", "-std=gnu++17"])
        with self.assertRaises(ValueError):
            builder.make_flags(self.flags, "CXX_INCLUDES")
        self.flags.write_text("CXX_FLAGS = -O3\nCXX_FLAGS = -O2\n")
        with self.assertRaises(ValueError):
            builder.make_flags(self.flags, "CXX_FLAGS")

    def test_outputs_cannot_target_application_source_build_or_existing_directory(self):
        before_source, before_native = snapshot(self.source), snapshot(self.native)
        existing = self.checkout / "results/existing"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("retain contributor data")
        for destination in (self.source / "new", self.native / "new", self.root / "elsewhere", existing):
            with self.subTest(destination=destination.name), \
                    patch.object(builder, "captured") as commands, \
                    patch.object(builder.subprocess, "run") as compiler, self.assertRaises(ValueError):
                builder.build(self.source, self.native, destination)
            commands.assert_not_called()
            compiler.assert_not_called()
        self.assertEqual(snapshot(self.source), before_source)
        self.assertEqual(snapshot(self.native), before_native)
        self.assertEqual((existing / "keep.txt").read_text(), "retain contributor data")

    def test_symlinked_results_root_cannot_redirect_a_build_to_native_cache(self):
        (self.checkout / "results").symlink_to(self.native, target_is_directory=True)
        before = snapshot(self.native)
        with patch.object(builder, "captured") as commands, \
                patch.object(builder.subprocess, "run") as compiler, self.assertRaises(ValueError):
            builder.build(self.source, self.native, self.output)
        commands.assert_not_called()
        compiler.assert_not_called()
        self.assertEqual(snapshot(self.native), before)

    def test_wrong_native_pin_origin_or_dirty_source_stops_before_any_compilation(self):
        bad_responses = {
            ("git", "rev-parse", "HEAD"): "0" * 40,
            ("git", "remote", "get-url", "origin"): "https://example.invalid/other.git",
            ("git", "status", "--porcelain", "--untracked-files=all"): " M native.cpp",
        }
        for wanted, bad in bad_responses.items():
            def capture(command, *, cwd=None):
                return bad if tuple(command) == wanted else self.captured(command, cwd=cwd)
            with self.subTest(guard=wanted[1]), patch.object(builder, "captured", side_effect=capture), \
                    patch.object(builder.subprocess, "run") as compiler, self.assertRaises(ValueError):
                builder.build(self.source, self.native, self.output)
            compiler.assert_not_called()
            self.assertFalse(self.output.exists())

    def test_build_cache_must_name_the_verified_source_tree(self):
        (self.native / "CMakeCache.txt").write_text("CMAKE_HOME_DIRECTORY:INTERNAL=/nonexistent/source\n")
        with patch.object(builder, "captured", side_effect=self.captured), \
                patch.object(builder.subprocess, "run") as compiler, self.assertRaises(ValueError):
            builder.build(self.source, self.native, self.output)
        compiler.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_native_archive_cannot_escape_the_existing_runtime_build(self):
        external = self.root / "outside.a"
        external.write_bytes(b"synthetic outside archive")
        self.link.write_text(self.link.read_text().replace("../../src/libllama.a", str(external)))
        with patch.object(builder, "captured", side_effect=self.captured), \
                patch.object(builder.subprocess, "run") as compiler, self.assertRaises(ValueError):
            builder.build(self.source, self.native, self.output)
        compiler.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual(external.read_bytes(), b"synthetic outside archive")

    def test_simulated_build_writes_only_fresh_results_and_hashes_its_real_dependencies(self):
        source_before, native_before = snapshot(self.source), snapshot(self.native)
        with patch.object(builder, "captured", side_effect=self.captured), \
                patch.object(builder.subprocess, "run", side_effect=self.simulated_compile) as compiler:
            report = builder.build(self.source, self.native, self.output)
        self.assertEqual(compiler.call_count, 2)
        self.assertEqual(report["status"], "built_help_checked_no_model_loaded")
        self.assertEqual(snapshot(self.source), source_before)
        self.assertEqual(snapshot(self.native), native_before)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertFalse(manifest["model_or_vocabulary_loaded"])
        self.assertFalse(manifest["inference_run"])
        self.assertIn("local_private", manifest["scope"])
        self.assertEqual(manifest["native_revision"], builder.PIN)
        for path in (self.helper, self.source / "header.h", self.library):
            self.assertEqual(manifest["dependency_files_sha256"][str(path)],
                             hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(manifest["compile_command"][0], str(self.compiler))
        self.assertNotEqual(str(self.compiler), str(self.compiler.resolve()))
        self.assertEqual([cmd[-1] for cmd in self.commands if cmd[-1] == "--help"], ["--help"])

    def test_dependency_change_during_compile_prevents_a_success_manifest(self):
        def concurrent_change(command, **kwargs):
            self.simulated_compile(command, **kwargs)
            if "-c" not in command:
                self.library.write_bytes(b"concurrent synthetic change")
        with patch.object(builder, "captured", side_effect=self.captured), \
                patch.object(builder.subprocess, "run", side_effect=concurrent_change), \
                self.assertRaisesRegex(ValueError, "input changed"):
            builder.build(self.source, self.native, self.output)
        self.assertFalse((self.output / "build.json").exists())
        self.assertTrue((self.output / "build.log").is_file())


if __name__ == "__main__":
    unittest.main()
