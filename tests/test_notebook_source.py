"""Source notebook invariants, with no Jupyter dependency or campaign execution."""

import ast
import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "decision_bench.ipynb"


class NotebookSourceTests(unittest.TestCase):
    def setUp(self):
        self.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        self.code_cells = [cell for cell in self.notebook["cells"] if cell["cell_type"] == "code"]

    def test_source_has_no_outputs_or_execution_state(self):
        self.assertEqual(self.notebook["nbformat"], 4)
        self.assertGreater(len(self.code_cells), 0)
        for cell in self.code_cells:
            self.assertEqual(cell["outputs"], [])
            self.assertIsNone(cell["execution_count"])
            ast.parse("".join(cell["source"]))

    def test_parameters_are_simple_and_control_is_default(self):
        cells = [cell for cell in self.code_cells if "parameters" in cell["metadata"].get("tags", [])]
        self.assertEqual(len(cells), 1)
        self.assertIs(cells[0], self.code_cells[0])
        parameters = {}
        for node in ast.parse("".join(cells[0]["source"])).body:
            self.assertIsInstance(node, ast.Assign)
            self.assertEqual(len(node.targets), 1)
            self.assertIsInstance(node.targets[0], ast.Name)
            parameters[node.targets[0].id] = ast.literal_eval(node.value)
        self.assertEqual(parameters, {
            "dataset_path": "datasets/decisions-v1/cases.jsonl",
            "profile_path": "profiles/fixture-control.json",
            "output_dir": None, "stack_root": None,
            "run_mode": "run", "source_archive": None, "max_new_cases": None,
        })

    def test_campaign_and_report_use_common_api_only(self):
        tree = ast.parse("\n".join("".join(cell["source"]) for cell in self.code_cells))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        bench_imports = [node for node in imports if (node.module or "").startswith("deposium_bench")]
        self.assertEqual(len(bench_imports), 1)
        self.assertEqual(bench_imports[0].module, "deposium_bench.campaigns")
        self.assertEqual({name.name for name in bench_imports[0].names}, {
            "run_campaign", "resume_campaign", "rescore_campaign", "render_report",
        })
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertEqual([node.name for node in functions], ["resolve_path"])
        calls = {node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertTrue({"run_campaign", "resume_campaign", "rescore_campaign", "render_report"} <= calls)
        source = "\n".join("".join(cell["source"]) for cell in self.code_cells)
        self.assertNotIn("/home/", source)

    def test_opt_in_parity_comparator_preserves_types_and_rejects_duplicate_cases(self):
        # Loading verifier helpers requires no notebook extra and executes no campaign.
        verifier = runpy.run_path(str(ROOT / "scripts" / "verify-notebook.py"))
        same_json = verifier["same_json"]
        self.assertTrue(same_json({"raw": {"a": True, "b": [1]}},
                                  {"raw": {"b": [1], "a": True}}))
        self.assertFalse(same_json({"raw": [True]}, {"raw": [1]}))
        self.assertFalse(same_json({"output": 1}, {"output": 1.0}))
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp)
            record = {"case_id": "case", "status": "ok", "output": True,
                      "raw_output": 1, "duration_ms": 3.0, "run_id": "first"}
            path = archive / "raw.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            stable = verifier["stable_records"](archive)["case"]
            self.assertEqual(set(stable), {"case_id", "status", "output", "raw_output"})
            self.assertIs(stable["output"], True)
            self.assertIs(type(stable["raw_output"]), int)
            path.write_text((json.dumps(record) + "\n") * 2, encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Duplicate case_id"):
                verifier["stable_records"](archive)


if __name__ == "__main__":
    unittest.main()
