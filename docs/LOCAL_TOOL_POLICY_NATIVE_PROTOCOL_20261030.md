# Supervised local JSON-policy canary

**30 October 2026: prepared, `not_run`, zero real-model cases scored.**
Offline tests use synthetic files, HTTP responses and process objects. They do
not establish model loading, generation, Metal execution or benchmark quality.
The larger historical D3 27B campaign remains deferred. This small Qwen
candidate is an additional engineering canary,
outside the frozen seven-candidate closed-choice cohort.

## Fixed inputs and limits

Use [tool-policy-canary-v1](../datasets/tool-policy-canary-v1/README.md): ten
TRAIN cases in five FR/EN families, SHA-256
`6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d`.
It includes discovery, executed arguments, and bounded episodes with actual
synthetic observations. References are agent-authored and pending human
review; these are qualification inputs, not an independent held-out ranking.
Freeze their bytes and references before the first prediction. Keep any later
revision separate instead of repairing a case to match a model.

The selected asset is `unsloth/Qwen3-4B-Instruct-2507-GGUF` at
`a06e946bb6b655725eafa393f4a9745d460374c9`, file
`Qwen3-4B-Instruct-2507-Q8_0.gguf`, 4,280,405,600 bytes, SHA-256
`391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068`.
The [asset manifest](../profiles/qwen3-4b-instruct-q8-assets.json) is declarative:
reading it downloads or executes nothing. The fixed alias is
`qwen3-4b-instruct-q8-tool-policy-v1`.

| Setting | Fixed value |
|---|---:|
| Context, logical batch, microbatch | 4096 each |
| Maximum output tokens | 256 |
| Seed; temperature | 42; 0 |
| Slots, worker, request concurrency | 1 each |
| Per-call timeout | 20 seconds |
| Whole supervised session | 600 seconds |
| Sampled owned-group RSS ceiling | 8,192 MiB |
| Estimated available host reserve | 8,192 MiB |
| Admission before model-byte reads | 16,384 MiB |
| HTTP retry, backend/model fallback | None |
| Host prompt cache (`--cache-ram`) | 0 since the [30 October amendment](LOCAL_TOOL_POLICY_PROMPT_CACHE_AMENDMENT_20261030.md); earlier attempts ran with the 8,192 MiB default |

The CLI exposes no resource or sampling overrides. Native fitting, context
shifting and automatic warm-up are disabled. Metal must actually offload every
model layer. Sampled RSS is not a hard instantaneous or total unified-memory
cap; the macOS available-memory value is a reclaimable-page estimate.

## Preparation and lifecycle

`scripts/run-local-tool-policy-pilot.py` reuses the existing pinned upstream
runtime validator, resource watcher, owned-process cleanup, source capture,
campaign engine, task guards, scorers and live native supervision. It adds no
second evaluation implementation and starts no application stack or database.
Native source must remain clean at
`efe3626b119ff81033e309c3ba07a770bef2c546`; the actual binary hash must match its
runtime manifest. Dataset, asset declaration, source and executable identity
checks precede model hashing or loading.

If available memory is below 16 GiB, retain a fresh ignored preflight receipt
and sealed `not_run` attempt with zero campaign cases. Do not hash weights,
force admission, stop unrelated workloads or silently use a smaller model.
After admitted model verification, preserve the 8 GiB reserve throughout the
owned session. Each attempt uses a new directory and a fresh IPv4 loopback
port. The launcher never discovers or attaches to an existing server.

The child receives an explicit environment allowlist and an ephemeral API key
through its environment. It inherits no `LLAMA_`/`GATEWAY_` configuration or
provider credentials. The key appears in neither command arguments nor
retained files. Credential-bearing responses, including escaped JSON echoes,
are refused and retained as hashes with a redaction marker only.

Native arguments explicitly request Jinja, one slot, Metal, fixed batches,
`--fit off`, `--no-context-shift`, `--no-warmup`, `--no-webui` and, since the
amendment, `--cache-ram 0`. Capture actual Metal offload and the disabled
prompt cache from the new owned log. Authenticate `/props`, check the actual
alias/context/slots/Q8 metadata and preserve the returned default chat template
as its **exact UTF-8 bytes**, without adding a newline. The session binds that
template, model, runtime, supervisor and source hashes. HTTP requests use the
fixed client alias; a candidate cannot choose a server or model.

## Technical controls before campaign cases

Run these controls separately from the ten quality cases:

1. Require the unauthenticated chat request to return 401.
2. Make a real synthetic JSON/schema request, validate the native model and
   token metadata, parse its returned JSON without repair and check the small
   control shape. A requested schema alone is not enforcement evidence; this
   observation covers one control, not every grammar or semantic task.
3. Probe an unknown request-model name as a diagnostic. The pinned single-model
   server may ignore it. If accepted, it must still return the loaded expected
   alias; record `native_request_alias_enforcement=false`. Do not claim native
   routing rejection or model selection when the server does not implement it.
   File/session identity and the fixed client/returned-alias guards stay required.
4. Send a separate oversized chat input. Require the pinned engine's explicit
   context-size error, including actual prompt-token and context counts. A
   generic error or a successful truncated answer does not pass this control.

All technical HTTP statuses and exact response hashes/bytes stay in the local
archive, subject to credential redaction. Synthetic warm-up/guard outputs are
never counted as benchmark predictions. Missing native truncation flags and
physical-forward counters remain unknown. Explicit truncation is refused;
reported token counts do not independently attest to internal token IDs.

Only after these controls may `run_campaign` execute, inside a matching live
owned process/watcher supervision scope. The model supplies generated JSON
proposals. The existing Python runtime independently validates scope, units,
artifact bindings and tool budgets and actually performs the synthetic tools.
Episode input/v1 retains its 1,000 ms limit. The canary explicitly uses v2 with
60,000 ms, counting model generation time in the same bounded loop.

## Explicit future launch

Use Python 3.11+ in a clean public checkout, after runtime preparation and fresh
admission. Actual local paths and execution artifacts remain ignored:

```bash
python3 scripts/run-local-tool-policy-pilot.py \
  --source-root "$NATIVE_SOURCE" --binary "$NATIVE_BINARY" \
  --runtime-manifest "$NATIVE_MANIFEST" --model "$MODEL_FILE" \
  --assets-manifest profiles/qwen3-4b-instruct-q8-assets.json \
  --output results/local-tool-policy-NEXT
```

The default input is the frozen ten-case canary; `--dataset` may point to an
identical local byte copy. The default fresh port is 11446. Model download,
runtime build and launch are explicit separate actions; imports, help, dataset
validation and tests perform no such work.

## Collection and interpretation

Retain every failed, refused and partial attempt. Stop only the owned child or
owned group; never signal unrelated groups. Close and verify the process and
resource writer before outer sealing. With unresolved cleanup, preserve the
unsealed attempt and report that limitation.

Collection completion is separate from quality. Valid but incorrect proposals
must not stop collection. Zero scored cases remain invalid. Keep discovery,
arguments, binding, execution, stopping, budget, procedure and numeric task
success metrics separate; ten TRAIN cases do not qualify general tool routing
or held-out model superiority. Rescore reads retained generation/tool traces
without a model, tool execution, clock, saved service or credentials.

Publish only reviewed aggregates and safe identities. Raw generated text,
private locators, logs, process metadata, source snapshots and keys are excluded
from public Git. This canary does not qualify an application integration,
production RAG, network plugins or real geospatial/open-data operations.
