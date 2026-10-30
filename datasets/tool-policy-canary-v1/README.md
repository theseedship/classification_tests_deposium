# Local tool-policy canary v1

**10 TRAIN cases, five FR/EN families, zero held-out cases.** Frozen on
30 October 2026 before any candidate prediction. This small technical canary
prepares one real local JSON-generation path for the shared discovery,
argument-execution and episode contracts. It is not a model ranking or a new
held-out workflow benchmark. References and translations are agent-authored,
pending human review.

At freeze: **zero real-model cases, zero scored model cases and zero human
judgments**. The [manifest](manifest.json) records source hashes, all families,
literal references, the new episode input version and the distinction between
diagnostic trajectory counts and grading assertions. Existing v1 datasets,
references and historical receipts remain unchanged.

| Family | Cases | Task | Independent reference |
|---|---:|---|---|
| `tp001` | 2 | Select one tool from a synthetic catalogue for an already supplied table. | Select row counting; value summation, column names and web search do not answer this request. |
| `tp002` | 2 | Propose sum arguments after an actual case-local lookup. | `4 + 9 + 12 = 25 kg`, with the actual artifact ID, `mass` column, unit and scope. |
| `tp003` | 2 | Complete a normal lookup/sum episode. | `8 + 11 + 14 = 33 EUR`, with success only after the real sum response. |
| `tp004` | 2 | Recover from one controlled transient lookup error. | One retry is permitted; `5 + 6 + 8 = 19 kg` after actual execution. |
| `tp005` | 2 | Handle a missing table identifier. | `clarify / missing_information`, null value/unit and no task success. The hidden fixture ID must not be guessed. |

The catalogue, table rows, dataset/scope/document IDs and requests are entirely
synthetic. Catalogue tools are advertised selection options, not live services.
Only the guarded Python `fixture.lookup` and `fixture.sum` functions execute in
the argument/episode paths. There is no Deposium tenant, private document,
production metadata, web request or live MCP operation in the cases.

## Projection and reference boundaries

The generic `deposium.case/v1` envelope uses pack `PRODUCT` as a grouping key,
without implying product qualification. Each translation pair and source
document stays TRAIN. These operation motifs relate to previous training
fixtures; new source identities do not establish fresh held-out reasoning types.

The candidate receives the existing task-specific whitelist only. Discovery
receives its request/catalogue; arguments receive the actual lookup observation;
an episode receives the current permitted interfaces, remaining budget and
actual observations. Gold assertions, rationales, family/split/document labels,
hidden fault schedules and unexposed table data do not reach the model. The
missing-input episode must not expose the internal dataset identifier.

The reference sums above were authored as literals before predictions, not
obtained from a candidate or a runtime result. Seven argument assertions and
eight episode assertions use the existing shared oracle paths. The tool runtime
never reads them. Artifact IDs identify actual source content and scope; the
model must bind its proposal to the observed ID, without a harness-filled
placeholder.

## Versioned timing and accounting

The six episode cases explicitly use **`deposium.tool-episode-input/v2`** with
`max_elapsed_ms=60000`, five policy decisions, three actual tool calls and two
lookup attempts at most. Actual model/policy time counts in that elapsed budget.
The original one-second input/v1 fixtures and their archived references remain
unchanged; the output receipt stays `deposium.tool-episode-output/v1`.

Exact ideal trajectories are diagnostics, not grading references. A fully
correct ideal path would use 20 model-policy generations and 14 actual Python
tool calls: 12 `ok`, two `controlled_error`. Four of the six episodes would
produce successful numeric task results; two would correctly clarify. These
are **planned controls, not observed model counts**. The case-level caps permit
at most 34 policy generations and 22 fixture-tool calls across the pack; any
lower supervisor/session limit remains independent.

Report discovery, arguments and episodes separately. Keep tool selection,
arguments, binding, execution, result, stopping and budget denominators; a
correct clarification is procedure handling, not task success. Structurally
valid wrong predictions remain scored. Technical failures remain distinct as
missing, unsupported, error, timeout or abstain, with every eligible case
retained. A technical canary has no accuracy threshold for selecting or dropping
cases; no exposed error is repaired by changing this reference version.

## Offline validation and execution status

From the public repository root, no weights, Docker, keys or application stack
are required:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-policy-canary-v1/cases.jsonl
```

A real attempt additionally needs the explicit local supervisor, pinned model,
runtime, template and a newly generated candidate profile/session. No fake
public model profile or session is supplied by this dataset. The
[local-policy protocol](../../docs/LOCAL_TOOL_POLICY_V1.md) records the candidate
identity and qualification boundary. A successful scripted test, model install
or JSON grammar alone does not qualify the generation path. Later meaningful
comparisons need separately frozen fresh families and held-out splits.
