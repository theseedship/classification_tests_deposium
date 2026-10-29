# Executable argument and artifact-binding contract v1

This is a bounded initial contribution for
[#11](https://github.com/theseedship/classification_tests_deposium/issues/11):
one fixed synthetic lookup followed by one proposed sum call using its actual
result. It extends the shared case, adapter, campaign, scorer and archive path.
It is not an application router, live MCP integration or arbitrary agent
execution environment.

The [fixture card](../datasets/tool-arguments-v1/README.md) contains four
FR/EN training cases in two synthetic families. The independently authored
integer results are 60 EUR and 12 kg. There are no calibration/test cases,
candidate-model results or human-certified references.

## Source input and candidate boundary

The case contract is `bench.tool-arguments`, carried by `deposium.case/v1`
with pack `PRODUCT`. The benchmark-native contract remains separate from the
application component registry. `PRODUCT` is a grouping label, not an
end-to-end quality claim.

The exact source input has these fields:

| Field | Constraint |
|---|---|
| `schema_version` | `deposium.tool-arguments-input/v1` |
| `request` | Bounded nonempty synthetic request |
| `scope_id` | Explicit permitted synthetic scope |
| `dataset.dataset_id` | Bounded synthetic table identifier |
| `dataset.column` | The column to expose and sum |
| `dataset.unit` | One of the fixture's declared unit strings: EUR, USD, kg or m |
| `dataset.values` | Between 1 and 32 JSON integers, each within ±1,000,000,000; booleans and floats are refused |

No field is interpreted as a filesystem path, command, network URL or
executable handle; the tools perform no such I/O or live-service access.
A scope ID is fixture data, never a source of application authority.

The execution adapter actually calls `fixture.lookup` on that table and creates
a fresh case-local artifact store. Only the request, allowed next-call
interface, permitted scope and actual observation are projected to the
candidate. Reference answers, rationales, split/family labels and synthetic
document annotations are not part of that projection. The internal recorded
transport uses the opaque case ID for dispatch; no real-model projection is
qualified by that fact.

The archive records the exact projected candidate input and its hash along
with the actual tool receipts. This separates the frozen source fixture from
the runtime observation the proposed call must consume.

## Actual artifact identity and proposal

The lookup returns a content-addressed identifier and the observed table.
The ID is `artifact:` followed by the SHA-256 of this canonical payload:

```python
json.dumps(
    {"scope_id": scope_id, "dataset": dataset},
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
    allow_nan=False,
).encode("utf-8")
```

Both the permitted scope and table identity/content participate in this hash.
Different values, units, columns, dataset IDs or scopes change it. A matching
hash alone does not grant access: the later call must also resolve the artifact
in the current case-local store and satisfy the independently fixed scope.
Identical FR/EN fixtures can share a content ID without sharing a runtime store.

The candidate proposal contains exactly `tool_id` and `arguments`:

```json
{
  "tool_id": "fixture.sum",
  "arguments": {
    "artifact_id": "artifact:<actual returned SHA-256>",
    "column": "amount",
    "unit": "EUR",
    "scope_id": "scope-alpha"
  }
}
```

The angle-bracket value illustrates the field; the checked-in recorded control
contains a literal complete ID, not a placeholder. The harness does not repair
or bind a symbolic candidate argument automatically.

## Guards and actual execution

The wrapper validates the proposed operation and arguments before summation:

- The selected tool is the allowed `fixture.sum` interface.
- Required fields, types and bounded values are correct; unknown fields fail.
- Column and unit match the actual observed artifact.
- Scope matches the independently permitted scope.
- The artifact ID names the exact earlier artifact in the current case store.

Wrong-but-well-typed values, units, foreign scopes and stale/invented bindings
fail. Summation cannot occur before lookup or after a rejected guard. The
fixture has only the fixed lookup and at most one sum call; the data and
operation bounds keep execution finite. There is no filesystem, network,
subprocess, arbitrary expression evaluation or paid service in either tool.

The returned `deposium.tool-arguments-output/v1` is constructed by the adapter,
with the candidate proposal, actual trace/observation, projection hash, guard
checks and execution receipt. Candidate-provided execution records or success
flags are not trusted output fields. A successful result is calculated from
the stored integer values, not read from the reference assertions.

## References and metrics

Each fixture reference contains seven exact assertions:

| Path | Required value |
|---|---|
| `/checks/tool_selected` | `true` |
| `/checks/arguments_valid` | `true` |
| `/checks/binding_valid` | `true` |
| `/execution/executed` | `true` |
| `/execution/status` | `ok` |
| `/execution/value` | The independently authored integer total: 60 or 12 |
| `/execution/unit` | EUR or kg, matching the family's declared unit |

Empty assertions or a partial reference cannot certify this task. The generic
shared exact scorer remains the case-decision path. Task-specific diagnostics
separate tool selection, argument validity, dependency binding, execution and
result correctness, with explicit denominators and unsuccessful states kept.
An argument failure must not disappear merely because no second tool ran.

The shared summary's `task_metrics["bench.tool-arguments"]` reports
`eligible_cases` and `scored_cases`, then `tool_correct_cases`,
`arguments_correct_cases`, `binding_correct_cases`, `execution_correct_cases`
and `result_correct_cases`. Each corresponding `_over_all_eligible` rate keeps
every case in its denominator. The report also retains
`cases_with_execution_trace`, `cases_without_execution_trace` and
`tool_calls_observed`, with language and split breakdowns.
`cases_with_execution_trace` counts validated retained traces;
`cases_without_execution_trace` includes absent or inconsistent receipts and
does not prove that zero operations occurred. Only validated receipts
contribute to `tool_calls_observed`. A non-`ok` candidate response after lookup
can retain one observed lookup while receiving no successful stage credit.
The four valid control cases
are expected to produce eight actual fixture calls: four lookups and four sums.

An explicit transport failure remains `unsupported`, `missing`, `error`,
`timeout` or `abstain` as applicable. A proposal can be returned with transport
`ok` while its guarded execution is blocked and its case fails. A script that
knows the expected arguments is an implementation control, not a model score.

## Profile, provenance and rescore

The only qualified path is the explicit `fixture_arguments` adapter using
`qualification=harness_control`, `model=null`, `revision=null` and the public
scripted-proposal recordings. The runtime and schema guards refuse ordinary
recorded, real-model or application profiles that claim this execution contract.
Changing a capability string cannot manufacture a tool receipt.

Source/scorer fingerprints include the fixture implementation, and adapter
identity includes the combined `adapters.py`, `synthetic_tools.py` and
`tool_arguments.py` runtime closure rather than a single-file adapter hash.
Archives retain the source
case bytes, control profile, original proposals, actual receipts, projection
hashes, metrics and seal. An explicit derived rescore verifies the retained
records and does not re-execute either tool. It creates no new execution or
inference result; the original archive stays unchanged.

## Run the bounded control

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-arguments-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_arguments.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-arguments-v1/cases.jsonl \
  --profile profiles/tool-arguments-control.json \
  --output results/tool-arguments-control-001
```

Use Python 3.11+ and a new output directory. These checks need no model assets
or services. The expected control outcome is four passing training cases;
negative tests cover empty/malformed proposals, wrong values/types/units/scope,
unknown/stale bindings, fabricated execution fields and preservation on rescore.

## Boundary with adaptive episodes

The first lookup is fixed, and the candidate proposes only one next call.
This is an actual two-step dependency fixture, not a retry or stopping loop.
[#12](https://github.com/theseedship/classification_tests_deposium/issues/12)
will reuse bounded tools to deliver successive actual observations, enforce
step/call/time budgets and assess recovery and stopping. Real candidates need
a separately qualified output adapter, pinned runtime, fresh scenarios and
campaign budget. Existing v1 references and historical model scores are preserved.
