# D3 Flash Q8: capability and workflow choices

**29 October 2026 — first completed candidate in the
[progressive campaign](CAPABILITY_CAMPAIGN_PLAN.md).** D3 Flash Q8 agreed with
all **192/192** authored references, including **96/96 held-out test cases**.
The fresh historical anchor scored **124/132**, including **61/66 test cases**.
These are separate packs and are never pooled into one accuracy.

This is an isolated model experiment on synthetic closed choices. References
and translations are agent-authored and pending human review. Each request
contains four proposed answers; an 8- or 32-card catalogue supplies context.
The model does not discover arbitrary tools or generate executable arguments.
**192/192 is a ceiling observation on this pack, not proof of general routing
accuracy or successful MCP execution.** No references were changed after seeing
the predictions.

[Public aggregate JSON](evidence/capability-flash-20261029/analysis.json) ·
[Every group](evidence/capability-flash-20261029/groups.csv) ·
[Paired variants](evidence/capability-flash-20261029/paired-variants.csv) ·
[Family outcomes](evidence/capability-flash-20261029/families.csv) ·
[Frozen execution protocol](CAPABILITY_NATIVE_PROTOCOL_20261029.md) ·
[Full results](RESULTS.md)

## Scores and coverage

Every denominator retains missing and unsuccessful cases. `ok` describes a
valid choice, not correctness. All three completed phases have full scored
coverage; `missing`, `unsupported`, `error`, `timeout` and `abstain` are each zero.
The calibration canary is a technical gate with no accuracy threshold and does
not add twelve cases to either full-pack score.

| Phase | Correct / all cases | Scored / all cases | Test only | Families |
|---|---:|---:|---:|---:|
| Calibration canary | 12/12 | 12/12 | Not a test score | 3 |
| Fresh context-choice anchor | 124/132 (93.94%) | 132/132 | 61/66 (92.42%) | 66 |
| Capability-choice-v1 | 192/192 (100%) | 192/192 | 96/96 (100%) | 48 |

The anchor reproduces the historical Flash Q8 totals: documentary **72/76**,
mathematics **26/28**, chemistry **26/28**. Matching totals alone do not prove
identical predictions or bitwise reproducibility. The old archive is unchanged.
The new campaign does not repeat the separate 24-case first-tool observation.

| New-pack track | All cases | Test cases | Families |
|---|---:|---:|---:|
| Capability and tool-set selection | 64/64 | 32/32 | 16 |
| Arguments and dependencies | 64/64 | 32/32 | 16 |
| Next step after fixed observations | 64/64 | 32/32 | 16 |

| New-pack view or use case | Correct / all cases |
|---|---:|
| French | 96/96 |
| English | 96/96 |
| Compact catalogue: 8 cards | 96/96 |
| Expanded catalogue: 32 cards | 96/96 |
| Geospatial | 52/52 |
| Open data | 48/48 |
| Web | 32/32 |
| Local document/RAG | 32/32 |
| Cross-source | 28/28 |

The linked group export also includes every task subtype, split and authored
D1/D2/D3 stratum. Those strata are not an empirical difficulty predictor.
All **48 families**, including **24 test families**, have all four variants
correct. There are 96 compact/expanded pairs and 96 FR/EN pairs, including 48
test pairs of each kind; both members are correct in every pair. Choice agreement
and paired correctness remain separate fields in the export. Translations and
catalogue variants are correlated observations, not 192 independent scenarios.
No confidence interval or stable population ranking is claimed.

## Speed and memory on the measured host

Host: Apple M5 Pro, 64 GiB unified memory. Native llama.cpp used Metal with
**33/33 layers offloaded**; context, batch and microbatch were **4096**. There
was one slot, one request and one question at a time, with a 30-second per-call
timeout and no retry or backend fallback.

| Phase/view | Successful calls | Adapter median | Adapter p95 | Sampled group RSS peak |
|---|---:|---:|---:|---:|
| Fresh 132-case anchor | 132 | 196.3 ms | 204.3 ms | 9.38 GiB |
| New 192-case pack | 192 | 576.9 ms | 985.8 ms | 9.48 GiB |
| Compact view | 96 | 456.6 ms | 561.7 ms | Not measured separately |
| Expanded view | 96 | 780.7 ms | 1,001.4 ms | Not measured separately |

These are adapter call durations following a synthetic warm-up in each fresh
session. They exclude model loading/startup and are not cold-start or production
latencies. The JSON separately records the first corpus call, later calls and
HTTP durations; missing startup or server-only timings remain unreported.
Median uses the central-pair midpoint, and p95 uses nearest rank. This is one
ordered pass, with no repeated-run or tail guarantee. Expanded inputs change
length, distractors and card positions together; they do not isolate tool count.

RSS is sampled over the owned process group every 250 ms. It is neither a
minimum RAM requirement nor total unified-memory use. GPU allocation and
per-response worker RSS were not separately measured. The fixed envelope was
**18 GiB group RSS plus an 8 GiB host reserve**, declared before predictions.
The minimum available-memory estimate was 20.81 GiB for the anchor and 20.77 GiB
for the new pack; no resource guard stopped either session. The macOS estimate
counts free, inactive and speculative pages; it is not Linux `MemAvailable`.

One initial anchor launch was refused by admission before a service or campaign
archive was created: **zero scored cases and no inference**. Its launch trace is
preserved privately. After memory recovered, a new attempt completed with the
same budgets, inputs, model and code. Limits were not raised to obtain a score.

## Input integrity and runtime evidence

The code was frozen at benchmark commit
`7e61b6d4660bae81ca97d06d464fb02fac4ec4ef` before all three phases. The shared
CLI engine, adapter, projection and scorer performed the campaign; notebook
cells did not implement another scoring path. Dataset SHA-256 values are:

| Pack | SHA-256 |
|---|---|
| Context-choice-v1, 132 cases | `767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616` |
| Capability-choice-v1, 192 cases | `0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0` |

The bounded vocabulary-only helper reused the exact pinned C++ SystemOne
renderer, Jinja template and tokenizer before any corpus prediction. All **324
unique inputs** prepared successfully, from **128 to 1,214 native tokens**,
below 4096. A separate oversized synthetic negative control was refused.
Preparation loaded no inference tensors, created no inference context and
executed no decode/forward.

During the completed phases, exact request-body hashes and native input counts
matched preparation for **12/12 canary, 132/132 anchor and 192/192 new-pack
responses**. Annotations, reference answers, family/case IDs and split labels
were absent from the native request. Physical-forward counters and native
`usage.truncated` receipts are **unknown for every response**: this pin does not
report them. Zero explicit truncation flags is not a fabricated `false` receipt;
token-count agreement does not independently compare live-forward token IDs.

| Identity | Pinned revision or SHA-256 |
|---|---|
| GGUF repository | `ggml-org/vllm-d3-flash-GGUF` |
| Model revision | `3d53d13778bf8035e6e1e534ce489ed052ee5663` |
| File / nominal class | `vllm-d3-flash-Q8_0.gguf`, nominal 9B class, text-only |
| Actual GGUF SHA-256 | `7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b` |
| llama.cpp revision | `efe3626b119ff81033e309c3ba07a770bef2c546` |
| Actual runtime binary SHA-256 | `3bc062d01ef3278441a357552c201c87032ee52cdcffbc9034dd43d5d1b25e6b` |
| Preparation helper SHA-256 | `20ed5552a634a648aded5f37c80b04ebd2193792ddb5f638fcc9fa34746c9a3e` |

The public JSON adds safe gateway, supervisor, preparation dependency and archive
fingerprints. Exact sources, original outputs, logs, resource samples and sealed
archives remain private. Source snapshots and binary hashes establish recorded
identity, not a reproducible-build certification. The application checkout had
local modifications; it was read and captured without being edited or rebuilt.
No full-stack or production integration was exercised.

## What this changes

Flash Q8 is now a measured reference for this complementary pack. Its perfect
agreement leaves no accuracy gap for a larger model to improve on these exact
cases. The planned larger and smaller candidates can still reveal differences
in robustness, coverage, latency, memory and the smallest model that reaches
this level. Keep the fixed initial cohort rather than selecting later models
from the observed test score.

The next two planned candidates, historical D3 27B Q4 and GLiClass v4 9B, were
not run: the post-cleanup admission check did not meet their respective
**32 GiB** and **40 GiB** available-memory requirements, including the same
8 GiB reserve. This is a resource preflight, not a failed model evaluation.
Repeat admission before the next session; do not lift guards or stop unrelated
workloads to complete a score. The six remaining candidates remain `not_run`.

Before expanding the benchmark again, retain this v1 result and review harder,
independently annotated scenarios as a new version: ambiguous capability sets,
free-form tool/argument proposals, real tool observations and complete guarded
execution loops. This pack alone does not validate access decisions, executable
geospatial work, evidence quality, adaptive model assignment or end-to-end RAG.
