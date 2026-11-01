# D3 mini · macOS CPU

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 4.539B backbone |
| Runtime | macOS arm64 CPU, pinned runtime |
| Family | Decision 3.0 |
| Precision | BF16 backbone / FP32 readout |
| Hardware | Apple M5 Pro CPU; 64 GiB unified memory |
| Observed | 2026-10-31 |
| Protocol / evidence | [D3_MINI_MACOS_CPU_PROTOCOL_20261031.md](../../D3_MINI_MACOS_CPU_PROTOCOL_20261031.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 119/132 | 60/66 | 8 | 11 | all `ok` | [D3_MINI_MACOS_CPU_PROTOCOL_20261031](../../D3_MINI_MACOS_CPU_PROTOCOL_20261031.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | 20/24 | no test split | — | — | all `ok` | provisional agreement, zero qualified cases |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | 192/192 | 96/96 | 1 | 1 | all `ok` | [report](../../D3_MINI_MACOS_RESULTS_20261031.md) |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | 39/48 | 32/36 | 3 | 1 | all `ok` | [report](../../D3_MINI_MACOS_RESULTS_20261031.md) |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | 28/32 | 10/12 | 1 | 1 | all `ok` | [report](../../TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md) |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | 79/80 | 47/48 | 1 | 1 | all `ok` | [report](../../FACADE_ROUTING_RESULTS_20261101.md) |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | 266/512 | no split ranking | 2 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | 527/768 | no split ranking | 2 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | 104/128 | no split ranking | 4 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 17,251.7 | 20,198.2 | 132 | 12,279.6 | NR | 7.35 | NR |

Scope: Per-response worker RSS, context-choice phase; not total host memory. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
