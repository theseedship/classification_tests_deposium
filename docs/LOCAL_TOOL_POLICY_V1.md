# Local generated tool-policy qualification v1

This is a bounded first step from scripted tool controls to **actual generated
JSON proposals** through one explicitly supervised local candidate. It uses the
shared campaign engine, projections, tool guards and task scorers. It adds no
second notebook runner, copies no application routing and calls no live MCP.

The [canary](../datasets/tool-policy-canary-v1/README.md) is frozen as ten TRAIN
cases in five FR/EN families before candidate predictions. At freeze there are
**zero actual model cases and zero scored model cases**. Implemented transport
controls and publisher claims do not supply those observations. Any later
attempt must retain its failures and report the actual scope, rather than
silently updating this initial qualification statement.

## A distinct generative candidate

The selected additional candidate is the Q8_0 quantization of
[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
with the exact asset identity in
[the public manifest](../profiles/qwen3-4b-instruct-q8-assets.json):

| Field | Pinned value |
|---|---|
| Quantized repository | `unsloth/Qwen3-4B-Instruct-2507-GGUF` |
| Quantized repository revision | `a06e946bb6b655725eafa393f4a9745d460374c9` |
| File | `Qwen3-4B-Instruct-2507-Q8_0.gguf` |
| File bytes | `4280405600` |
| File SHA-256 | `391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068` |
| Exact upstream revision used by this conversion | **Unknown / not attested**. |

The upstream model is Apache-2.0. Its current upstream revision is not asserted
to be the source revision of this community conversion. This observation must
identify the quantized repository/file, rather than relabeling it as another
checkpoint or precision. File size is not a resident-memory requirement or a
prediction of peak unified memory.

This technical canary does not replace or reorder the frozen D3/GLiClass/Vela
classifier cohort. The model has a different role: qualify a supported local
generative output path, not claim that a larger or better historical classifier
can already generate arbitrary arguments. The first local route uses pinned
llama.cpp `efe3626b119ff81033e309c3ba07a770bef2c546` with Metal and a separately
retained chat template. Actual binary, template, device and session evidence
must be archived before a result is attributed to that route. This does not
qualify WSL/CUDA/CPU numerics or performance; the shared interfaces remain
portable while runtime observations stay platform-specific.

## Candidate output and independent execution

The `llama_cpp_json` adapter requests one generated JSON value from the
explicit owned loopback endpoint. Its schema requests syntax and declared
field domains through the pinned runtime's supported grammar subset; parsing
and task guards independently validate every output. It is not a list of complete authored plans, an oracle
or evidence that a generated field is correct. The retained response must be
the actual model response; parsing does not repair or replace its contents.

| Task | Model generation | Independent runtime/scorer responsibility |
|---|---|---|
| Discovery | A shortlist plus semantic selection and tool IDs. | Catalogue eligibility/availability, namespace validity, shortlist/final sets, sufficiency and unnecessary tools. No tool executes for this task. |
| Arguments | One proposed sum tool and its artifact/column/unit/scope arguments, after an actual fixed lookup. | Bind the exact actual artifact, validate argument values and permissions, execute guarded sum and check the independently authored result. |
| Episodes | One next action after each actual observation: a call or a success/stop/clarification finish. | Case-local tool execution, fault handling, binding, retry/step/call/time limits and whether actual receipts justify stopping or task success. |

Arguments and artifact IDs are generated from the supplied observation. The
harness does not resolve a symbolic placeholder on the candidate's behalf.
An episode's internal fault schedule and fixture source stay outside its
whitelisted projection. Missing identifiers remain missing. Candidate output
never grants permission, supplies an execution receipt or changes the oracle.

The arithmetic references are independently authored literals: `25 kg`,
`33 EUR` and `19 kg`. The missing-ID family expects clarification with null
value/unit and `task_success=false`. No result from this candidate or an executed
tool was used to choose those references. New TRAIN identities do not create
held-out generalization evidence. Any later expansion needs its own family
freeze and split review before predictions.

## Prompt versions

The system prompt is versioned in `deposium_bench/local_tool_policy.py`
(`PROMPTS`) and bound into every retained request hash. `prompt/v1` ran the
first TRAIN canary; it omitted two public contract rules (selected discovery
tools must appear in the shortlist; an episode finishes once an actual
observation justifies an outcome). `prompt/v2` states those rules and names
no case, identifier or answer. Both texts stay in the module so a pure
rescore of any archive rebuilds its exact request bytes. The
[held-out protocol](LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md) fixes the
order TRAIN-v2 then held-out-v2; no prompt change follows a held-out result.

## Versioned budgets and actual time

Only the new canary episodes use `deposium.tool-episode-input/v2`: at most five
policy decisions, three tool calls, two lookup attempts and **60,000 ms**.
The existing input/v1 remains bounded at 1,000 ms, with all old cases/receipts
unchanged. Both use the same v1 output receipt and existing state machine.

The new elapsed envelope includes the actual local model/policy invocation,
along with tool/runtime work. The candidate cannot extend that budget. Elapsed
time is checked before and after synchronous invocations; this does not
hard-preempt an in-flight generation. Per-call HTTP timeouts and the owned
supervisor's session/memory/time limits remain separate enforced boundaries.
Exact ideal step counts are diagnostics, not requirements excluding another
valid within-budget trajectory. Across the ten cases, the case caps allow no
more than 34 policy generations and 22 synthetic tool calls; the actual session
can impose stricter bounds. Loading/warm-up work is separate from scored cases.

Before any real attempt, freeze actual generation settings, seed, output-token
cap, complete-input context limit, model/runtime/template hashes and supervisor
resource/time envelope. Do not silently truncate, fit, change device, replace
the model or raise limits after observing failures. Keep a new archive for each
attempt and preserve partial attempts. This document does not claim a successful
preflight, installation, native input preparation or model run merely because
an asset manifest exists.

## Profiles, receipts and reproduction

The public asset manifest contains identities only. A usable candidate profile
and session are generated **only by the explicit local supervisor** after its
actual owned service and assets have been verified. No fabricated public
profile/session is supplied, and editing a contract string on a classifier
profile does not qualify this adapter. The constructor requires the matching
live supervision and session links; it does not discover or start a service.

Retain actual request/projection hashes, generated response bytes and hashes,
parse/HTTP status, call duration, model/runtime/template identity and actual
tool/episode traces in ignored archives. A pure rescore validates these retained
bindings without making another model call or executing tools. An absent
response cannot be turned into a generated proposal, and schema-valid wrong
JSON must still fail the relevant task checks. Seals establish byte integrity,
not external producer authenticity or human reference approval.

The public clone can validate the frozen inputs without a model:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-policy-canary-v1/cases.jsonl
```

Real execution uses the shared engine inside the newly generated supervised
session, with a new ignored results directory. Exact supervisor commands and
their actual attempt receipts must accompany a later execution report; no
standalone command with an invented profile substitutes for that lifecycle.

Report each task with its eligible/scored totals and all missing, unsupported,
error, timeout and abstain statuses. Correct clarification is procedure handling,
not a numeric task result. Separate initialization, first/subsequent model calls,
tool execution and memory scopes; no old short-choice latency predicts this
generation workload. No accuracy threshold selects or discards canary cases,
and this small TRAIN pack provides no model ranking, RAG answer-quality,
production MCP integration or empirical small/large allocation qualification.

Weights, installations, credentials, private paths and raw operational archives
stay outside Git. Public reports may contain only reviewed synthetic aggregates
and safe identity hashes. No paid API, application database or production
service is needed for this initial local qualification.
