# Bounded tool-plan contract v1

This is the initial implementation slice for
[#9](https://github.com/theseedship/classification_tests_deposium/issues/9).
It adds a versioned structured **proposal** contract to the shared engine and
one synthetic lookup-to-sum family in French and English, both **training**
cases. It does not execute tools, qualify model JSON generation, or provide a
held-out benchmark. References are agent-authored and pending human review.

## Scope and allowed input

The contract ID is `bench.tool-plan`. It is a benchmark-native task, separate
from the application contract registry. The generic `deposium.case/v1` envelope
uses pack `PRODUCT` only as an existing grouping key; this is no product result.

`deposium.tool-plan-input/v1` contains exactly:

| Field | Meaning and bound |
|---|---|
| `schema_version` | Exactly `deposium.tool-plan-input/v1`. |
| `request` | Synthetic request, nonempty text without control characters, at most 8,192 characters. |
| `catalogue` | Between 1 and 32 synthetic tool descriptions; unique `tool_id` values. No executable handles, credentials, tenant identifiers or live services. |
| `max_calls` | Integer 1 or 2; booleans are rejected. It bounds proposed calls, not actual tool execution. |

Each catalogue entry contains exactly `tool_id`, `description`, `arguments`
and `output_type`. Text fields have the same 8,192-character bound. `arguments`
is an object with at most 16 required argument names. There are two argument
specifications:

- `{"type":"enum","values":[...]}`: 1–32 distinct nonempty text values.
- `{"type":"artifact_ref","artifact_type":"numeric_series"}`: a reference
  to an earlier proposed artifact with the advertised type.

Unknown fields and argument domains are refused. The shared transport also
bounds the serialized candidate request to 1 MiB. A catalogue entry is an
advertised synthetic interface, not evidence of an installed or callable tool.
No plugin/capability/tool discovery hierarchy is inferred from these IDs.

Task content crosses the candidate boundary as `input`. The recorded adapter
also receives the shared transport's `case_id` and `contract_id` for dispatch; a future
model integration must audit its actual model projection separately. References,
rationales, splits, scenario/family IDs and document annotations stay outside
`input`. The engine rejects annotation keys in candidate-visible data.

## Output and artifact bindings

`deposium.tool-plan-output/v1` contains exactly:

| Field | Meaning |
|---|---|
| `schema_version` | Exactly `deposium.tool-plan-output/v1`. |
| `decision` | Exactly `propose`. `success`, final answers and execution receipts are not supported outputs. |
| `calls` | One or two ordered proposed calls, within the input budget. |
| `result_artifact_id` | The last proposed artifact ID, `a1` or `a2`. No computed result value is claimed. |

Each call contains exactly `tool_id`, `arguments` and `output_artifact_id`.
The tool must appear in the catalogue and every declared argument is required;
unknown arguments are refused. Enum arguments must match a declared string.
Artifact arguments bind an **earlier** proposed artifact of the declared type.
Call 1 must declare `a1`, call 2 `a2`; canonical names avoid scoring arbitrary
alpha-renaming. Forward/self references, unknown artifacts, wrong advertised
types and arbitrary output names are invalid.

For the materialized training family, a valid proposal is:

```json
{
  "schema_version": "deposium.tool-plan-output/v1",
  "decision": "propose",
  "calls": [
    {
      "tool_id": "dataset.lookup",
      "arguments": {"dataset_id": "monthly-sales", "field": "amount_eur"},
      "output_artifact_id": "a1"
    },
    {
      "tool_id": "numeric.sum",
      "arguments": {"values": "a1"},
      "output_artifact_id": "a2"
    }
  ],
  "result_artifact_id": "a2"
}
```

The complete alternative replaces the second call with `numeric.aggregate`
and arguments `{"values":"a1","operation":"sum"}`. Both are valid
agent-authored proposals for this family. No dataset values, tool responses or
numeric total are fabricated or executed. An artifact binding is a plan edge,
not a receipt proving that an artifact exists.

## Reference and scorer

[`deposium_bench/tool_plan.py`](../deposium_bench/tool_plan.py) validates the
bounded input and every complete reference output. It supplies no independent
scoring pipeline. The shared typed exact scorer checks one root `one_of`
assertion over the two complete valid outputs. It rejects extra fields,
missing calls or altered arguments through full typed equality. Python
boolean/number equality cannot make an invalid reference match.

A well-typed plan may still be wrong: selecting `quarterly-sales`, `quantity`
or aggregate operation `mean` is within the catalogue but fails this family's
reference. An unlisted plan fails the exact oracle; that is not a claim that
all conceivable equivalent real-world plans are wrong. Broader alternative or
unordered plans require a separately reviewed oracle and contract version.

The ordinary result envelope retains `ok`, `unsupported`, `missing`, `error`,
`timeout` and `abstain`. `ok` means an adapter returned an output, not that its
proposal passed. Empty, wrong, malformed, over-budget, unknown-tool,
forward-binding and premature-success outputs cannot pass. Abstention is
forbidden in these two controls. Failures retain their shared coverage/status
accounting; zero scored cases cannot yield a pass.

## Runtime support audit

This table audits the checked-in adapter boundaries. It is not a claim about
unexercised publisher capabilities or a new live provider review.

| Current route | Delivered task boundary | `bench.tool-plan` status |
|---|---|---|
| Recorded control, `profiles/tool-plan-control.json` | Replays two fixed positive training outputs; `qualification=harness_control`, model/revision null. | Supported **control only**. It does not generate or execute a plan. |
| Native/GGUF D3 and Clef through `systemone_local` | `native_request` builds a single closed `choice` question; the response maps the chosen criterion back to its option. | Not run / unqualified; the profile capability is rejected. No arbitrary JSON generation is implemented. |
| GLiClass v4 9B | Scores the supplied labels/options using its pinned classification path. | Not run / unqualified; no structured multi-call output path. |
| Jev HTTP and hosted Decision3 HTTP profiles | Declared closed-choice requests and strict choice/probability response validation. | Not run / unqualified; provider JSON claims do not establish this transport. |
| Remaining pinned local choice profiles (Julia choice, GLiNER, Decision2, Vela, D3 and other choice backbones) | Their existing adapter-specific choice readouts; Julia's separate document-plan mapping is also a bounded legacy task. | Not run / unqualified; none declares the new proposal capability. |
| Application MCP replay profiles | Existing application contract invocations; no benchmark-native plan handler. | Not run / unqualified; a registry is not an integration receipt. |

Both the candidate schema and runtime profile validation restrict the new
capability to `adapter=recorded`, `qualification=harness_control`. Editing a
real model profile to advertise it is refused before runtime creation. Future
qualification needs an audited real output representation, parsing, input
projection, pinned helper/runtime, resource admission and negative controls;
converting these plans back into four choices would remain a different task.

## Pilot expansion and later contracts

The [dataset manifest](../datasets/tool-plan-pilot-v1/manifest.json) proposes
12 families, provisionally four train / four calibration / four test. **Only
one train family exists**, as two correlated FR/EN cases; calibration/test have
zero materialized cases. Names in the proposal are design directions, not
fresh held-out data or a frozen campaign. Some require reviewed extensions
beyond this proposal-only contract. Do not populate exposed test references
by adapting to current model failures, or modify any v1 choice dataset.

[#10](https://github.com/theseedship/classification_tests_deposium/issues/10)
adds discovery and single/multiple selection, including no-suitable-tool and
permissions boundaries.
[#11](https://github.com/theseedship/classification_tests_deposium/issues/11)
adds executable argument/value checks and bindings to **actual** prior tool
responses. This slice checks only enum syntax, advertised types and plan edges.
[#12](https://github.com/theseedship/classification_tests_deposium/issues/12)
adds bounded adaptive episodes: execute deterministic synthetic tools, feed
observations back, test recovery and stopping, and retain actual traces.
There is no feedback loop or actual tool invocation in this PR.

## Offline replay and evidence preservation

Use Python 3.11+; neither model assets nor services are needed:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-plan-pilot-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_plan.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-plan-pilot-v1/cases.jsonl \
  --profile profiles/tool-plan-control.json \
  --output results/tool-plan-control-001
```

Use a new output directory. Expect two training cases to pass with qualification
`harness_control`; no model leaderboard score follows. Invalid-output tests also
run through the shared CLI/campaign/scorer, rather than a replacement harness.

The scorer fingerprint now includes `tool_plan.py`, so source/scorer identities
change. Preserve old archives and their original fingerprints. A derived
`rescore` writes a new archive using current code and retained raw outputs; it
creates neither new inference nor timing. Resume still requires matching
adapter/runtime provenance. Never rewrite historical archive identities to
make changed code appear to be the original experiment.
