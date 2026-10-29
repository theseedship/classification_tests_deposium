# Tool-plan pilot v1

**Implementation fixture, not a model benchmark campaign.** This pack contains
one synthetic lookup-to-sum family, translated into French and English: **two
training cases, zero calibration cases, zero test cases**. References and
translations are agent-authored and pending human review. It is the initial
contract slice for [issue #9](https://github.com/theseedship/classification_tests_deposium/issues/9).

The [bounded contract](../../docs/TOOL_PLAN_CONTRACT_V1.md) specifies allowed
inputs, exact alternative outputs, artifact IDs, failure handling and current
runtime support. No tool is executed. No model has produced a scored result on
this contract; the recorded positive control tests the shared harness only.

## Construction and reference

The input supplies a synthetic request, a three-entry catalogue and a maximum
of two proposed calls. `dataset.lookup` advertises a numeric series, followed
by either `numeric.sum` or `numeric.aggregate` with operation `sum`. Dataset
and field IDs are synthetic enum values. Output artifacts are canonically
named `a1`, then `a2`; the second proposal binds to the first. The output says
`decision=propose` and supplies no numeric answer or execution-success claim.

Each reference is one root `one_of` assertion over two complete valid outputs,
scored by the existing typed exact scorer. A quarterly dataset, quantity field
or mean operation is structurally possible but wrong for this request. Unknown
tools, forward bindings, extra calls/fields, empty outputs, malformed plans and
premature success fail. Passing checks proposal agreement with the authored
alternatives, not numeric computation, retrieval success or application safety.

The two languages share `scenario_id`, `translation_family`, split and reference.
They are **one family**, not two independent scenarios. Generic case-envelope
pack `PRODUCT` is an existing grouping label, not a qualified product result.
No private conversations, documents, metadata or application tool inventory
were copied into this dataset. Catalogue entries are synthetic descriptions.

## Proposed expansion, not held-out evidence

[manifest.json](manifest.json) records corpus bytes and a **proposed**, unfrozen
12-family direction: four train / four calibration / four test. Only its first
training family is materialized. The remaining names have no cases, references,
measured coverage or held-out qualification. Several need future contract
extensions for clarification, unavailable tools, actual artifact values and
adaptive stopping. Review the design before adding them; do not alter old
choice datasets or treat exposed controls as a new test set.

## Offline checks

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-plan-pilot-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_plan.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-plan-pilot-v1/cases.jsonl \
  --profile profiles/tool-plan-control.json \
  --output results/tool-plan-control-001
```

Use Python 3.11+ and a new output directory. Expected validation: two valid
cases. Expected replay: two passing cases with `qualification=harness_control`.
The FR control records the `numeric.sum` alternative; EN records
`numeric.aggregate(sum)`. This scripted fixture requires no weights, APIs,
Docker or application stack. It supplies no model timing or quality ranking.
Current model adapter claims for `bench.tool-plan` are rejected until a real
structured-output path is separately qualified.
