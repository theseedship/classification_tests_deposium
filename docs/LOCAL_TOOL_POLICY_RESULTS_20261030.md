# Local JSON-policy TRAIN canary: results

**30 October 2026: collected, quality verdict `fail`, 5/10 cases passed.** This is
the first actual run of the prepared [local generated-JSON path](LOCAL_TOOL_POLICY_V1.md)
under the fixed [native protocol](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md).
It qualifies that the runtime, supervision and scoring path works with a real
model. It is not a model ranking, a held-out result or a product qualification.

Reviewed aggregates: [analysis.json](evidence/local-tool-policy-20261030/analysis.json),
produced by `scripts/export-local-tool-policy.py` from the sealed private archive.
Raw generations, the chat template, logs and local paths stay outside Git.

## Identity

| Item | Value |
|---|---|
| Dataset | [tool-policy-canary-v1](../datasets/tool-policy-canary-v1/README.md), 10 TRAIN cases, 5 FR/EN families, SHA-256 `6add6d14…fcdbc2a6d` |
| Model | `unsloth/Qwen3-4B-Instruct-2507-GGUF` at `a06e946b…`, `Qwen3-4B-Instruct-2507-Q8_0.gguf`, 4,280,405,600 bytes, SHA-256 `391c1e41…ef068` (verified) |
| Runtime | llama.cpp `efe3626b119ff81033e309c3ba07a770bef2c546`, binary SHA-256 `3bc062d0…25e6b` |
| Device | macOS arm64, 64 GiB unified memory; Metal offloaded 37/37 layers |
| Envelope | context/batch/microbatch 4096, one slot, 256 output tokens, seed 42, temperature 0, 20 s per call, 600 s session, no retry or fallback |

## Technical controls

Run before the cases and **not** counted in any quality denominator.

| Control | Observed |
|---|---|
| Authenticated `/props` | HTTP 200; alias, context, slot count and Q8 metadata checked |
| Unauthenticated chat | HTTP 401 |
| Synthetic JSON/schema request | HTTP 200; parsed without repair. Covers one control, not grammar enforcement in general |
| Unknown request-model name (diagnostic) | HTTP 200; `native_request_alias_enforcement=false`. The pinned single-model server ignores the name; the fixed client alias and file/session identity remain the guard |
| Oversized chat input | HTTP 400 with the engine's explicit context-size error |

Admission saw about 30.2 GiB estimated available memory against the 16 GiB
requirement. Peak sampled process-group RSS was 6,552 MiB (ceiling 8,192 MiB);
minimum estimated available memory was 24,288 MiB. No resource stop occurred.
The owned process was terminated, the resource writer closed and the outer
archive sealed.

## Coverage and results

All ten cases were attempted: `ok` 10, and 0 each for `unsupported`, `missing`,
`error`, `timeout` and `abstain`. Collection completed; quality did not.

| Measure | Correct / eligible |
|---|---:|
| All cases | 5 / 10 |
| French / English | 3 / 5 · 2 / 5 |
| Discovery (final set, minimal set) | 0 / 2 · 0 / 2 |
| Arguments (tool, arguments, binding, execution, result) | 2 / 2 each |
| Episodes, procedure | 3 / 6 |
| Episodes, task success | 3 / 4 success-eligible (3 / 6 overall) |
| Episode stages: tool, arguments, binding | 4 / 4 each |
| Episode stages: execution, result | 3 / 4 each |
| Episode stages: stopping, budget | 3 / 6 each |

Observed 25 policy decisions, 22 tool-call attempts and 10 actual tool calls.
Per-case wall time ranged from 1.1 s to 7.8 s (median 3.5 s, 35.7 s in total);
this is a single descriptive pass, not a latency guarantee.

### What failed

- **Discovery (both languages):** the model returned a syntactically valid
  `select` with an empty `shortlist`. The contract requires the shortlist, so
  the output is `invalid_tool_discovery_output`: zero valid select observations,
  and every discovery metric stays zero over its two-case denominator.
- **Episodes (three cases):** the model kept proposing tool calls until the
  step limit instead of finishing or requesting clarification. They fail the
  stopping, budget and procedure checks. One of them (`tp004-en`) required a
  verified sum, so it also fails task success; the other two expected a
  clarification.
- **What worked:** both argument cases passed every stage. Of the four
  episodes that required a verified sum, three succeeded with actual
  lookup/sum receipts.

These are model behaviors on synthetic cases. No reference was changed to
obtain this score, and the guards were not relaxed.

## Rescore

A pure rescore of the retained archive into a new directory reproduced the same
5/10 and per-case outcomes. It invoked no model, tool, clock or credential, and
the original `raw.jsonl` hash was unchanged.

## Limits

- Ten TRAIN cases in five families; each FR/EN pair is correlated. No held-out
  claim, confidence interval or ranking is made, and the candidate stays
  outside the frozen classifier cohort.
- References are agent-authored and pending human review.
- One model, one runtime, one device and one temperature-0 pass.
- A requested schema is not proof of grammar enforcement; output is scored
  without repair.
- Sampled RSS is not a unified-memory cap, and available memory is a
  reclaimable-page estimate.
- Synthetic lookup/sum tools only: no live MCP, application replay or answer quality.

Any held-out comparison needs separately frozen fresh families and a new
archive. Existing datasets, references and archives remain unchanged.
