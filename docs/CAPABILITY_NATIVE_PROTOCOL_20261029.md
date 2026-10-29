# D3 Flash Q8 complementary campaign protocol

Fixed before new predictions, 29 October 2026. This protocol executes the first
candidate in the [progressive plan](CAPABILITY_CAMPAIGN_PLAN.md), using the
shared campaign engine and scorer. References remain synthetic, agent-authored
and pending human review. The task is closed-choice proposal agreement, with
no real MCP tool execution or product qualification.

## Frozen inputs and identity

- New pack: `datasets/capability-choice-v1/cases.jsonl`, 192 cases/48 families,
  SHA-256 `0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0`.
- Historical anchor: `datasets/context-choice-v1/cases.jsonl`, 132 cases/66
  families, SHA-256 `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
- Canary: the exact twelve calibration cases in
  [the sequence](../plans/capability-choice-v1-sequence.json), three families
  across the selection/arguments/observations tracks and all four catalogue/
  language views. It is a technical gate, with no accuracy threshold.
- Model: `ggml-org/vllm-d3-flash-GGUF` at
  `3d53d13778bf8035e6e1e534ce489ed052ee5663`, file
  `vllm-d3-flash-Q8_0.gguf`; exact size/hash in
  [the asset manifest](../profiles/d3-flash-q8-assets.json).
- Native runtime: llama.cpp at `efe3626b119ff81033e309c3ba07a770bef2c546`,
  Metal requested. Record and verify the actual executable, gateway, helper,
  runtime pin, supervisor and benchmark fingerprints. Capture exact sources
  separately from Git HEAD and preserve any source/build provenance limits.

No weight/helper/runtime upgrade is implicit. No changes are made to the
application repository, its gitlinks, production configuration or deployment.
Native preparation and execution create their artifacts in new ignored local
directories. Public reports contain reviewed aggregates and safe identities.

## Declared resource envelope

Context and physical/logical batch remain **4096**, one slot, one request and
one question at a time. The per-call timeout remains **30 seconds**, with no
automatic HTTP retry or model/backend fallback.

This new run uses **18 GiB maximum sampled process-group RSS (18,432 MiB)**
and **8 GiB reserve (8,192 MiB)**. The 18 GiB ceiling is stricter than the
historical Flash Q8 ceiling of 20 GiB. It is declared before any new prediction;
the reserve and stop policy are unchanged. Admission therefore requires at
least **26 GiB estimated available memory before the model hash**. Lowering
the model's permitted maximum does not authorize use of the reserve. If the
stricter ceiling is reached, preserve the failed/partial archive and do not
raise the ceiling to complete its score.

| Phase | Whole supervised-session time budget |
|---|---:|
| Canary (12 calibration cases) | 600 seconds |
| Historical anchor (132 cases) | 1,200 seconds |
| Complementary pack (192 cases) | 1,800 seconds |

The watcher samples every 250 ms and stops only its owned process group on
RSS, host-reserve or time limits, or failed resource observation. Sampled RSS
is not an instantaneous cap or total unified-memory measurement. macOS
available memory is a reclaimable-page estimate. Record each phase's actual
minimum available estimate, peak group RSS and stop reason separately.

## Input and native preparation checks

Before corpus predictions, validate the unchanged source cases and shared
`native_request` projection for all 192 inputs. Preserve exact UTF-8 wire-body
hashes, ordinal option mappings and byte sizes; only context, question and
ordered descriptions enter the native request. No annotations, semantic case
identifiers or expected choices enter model input.

The pinned HTTP SystemOne API does not expose a preparation-only operation.
Its usage response has input/output token counts and does not provide a
`truncated:false` receipt. Missing flags remain **unknown**. The client rejects
any explicit native truncation or malformed flag; it never invents a negative
truncation receipt or a physical-forward receipt.

Prepare a benchmark-side tokenizer helper that reuses the pinned native C++
`server_decision_context` and `fill_task` implementation. Link existing pinned
native objects in read-only fashion; do not copy its renderer or modify the
application/runtime checkout. A vocabulary-only model load supplies the real
metadata, Jinja template and tokenizer, with no inference context, weight
tensors or decode calls. The helper's source, dependency objects, compiler,
binary and exact request bodies are separately fingerprinted.

Run this preparation over all 192 requests and compare every native variant's
token count with 4096. Preserve token IDs and their hashes privately. Distinguish
within-limit, unsupported and error cases; record maximum lengths and audit
coverage. This is native preparation evidence, not an independent comparison
with the IDs inside a later live forward. If the helper cannot be validated,
retain that limitation and do not claim this preparation gate passed.

The initial preparation also includes all 132 anchor requests. Bound the
vocabulary-only process separately to 2 GiB sampled group RSS, 8 GiB host
reserve and 600 seconds. Verify one oversized synthetic request is refused;
it is a negative control, not a scored case. For this pin's single-question,
single-variant D3 path, compare each live response's `usage.input_tokens` with
the corresponding prepared count and exact wire-body hash. Count agreement
does not establish equality of the actual token IDs inside a later forward.

## Execution and interpretation

Each phase uses a fresh owned gateway/model session and a new output directory.
The supervisor verifies model hashes under admission, runtime identities,
loopback authentication/model/route guards and native overflow rejection. A
synthetic choice smoke precedes corpus calls; these controls are archived
separately and never added to the 12/132/192 quality denominators.

All dataset phases use explicit `--dataset`, yielding one `campaign/` archive
and no Mastra phase. The launcher's historical default 132+24 behavior is
preserved. Archive the selected dataset bytes before model work can mutate
the source path; include the versioned oracle dependencies in the source
capture. Worker termination and resource-writer closure precede outer sealing.

For the canary, require structurally valid choices, the expected model/runtime
and no observed truncation/overflow. A valid wrong answer passes the technical
gate. For full phases, preserve all failures and full denominators; resource
stops remain partial and zero scored cases remain invalid. The supervisor's
`completed` field describes collection, not semantic qualification or an
accuracy PASS.

Report full/test scores separately (old /132 and /66; new /192 and /96), with
track, task type, use case, language, catalogue, split and family breakdowns.
Pair model outputs and catalogue/language variants only within their proper
pack/family. Report HTTP attempts and cached failures as well as recorded rows.
Never pool the two packs into one accuracy.

Archive loading/startup, synthetic warm-up, first corpus call and later calls
separately. Dataset latencies follow the synthetic warm-up; they are not cold
start or production latency. Backend/offload evidence comes from captured
native logs, not merely `backend_requested`. HTTP success alone does not prove
a new physical forward: unobserved forward counters remain unknown.

Retain every initial attempt and source archive. Publish only aggregate metrics,
safe model/runtime/scorer/dataset pins, measurement scopes and evidence hashes;
keep absolute paths, PIDs, keys, source snapshots, raw outputs and logs local.
