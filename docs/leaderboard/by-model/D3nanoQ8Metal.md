# D3 nano · Q8 Metal

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 2.213B backbone |
| Runtime | Direct upstream native Metal, Apple M5 Pro |
| Family | Decision 3.0 |
| Precision | Q8_0 GGUF (ggml-org conversion of the same weights) |
| Hardware | Apple M5 Pro GPU (Metal); 64 GiB unified memory |
| Observed | 2026-11-01 |
| Protocol / evidence | [D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md](../../D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 117/132 | 61/66 | 12 | 4 | all `ok` | [D3_SMALL_GGUF_GPU_PROTOCOL_20261101](../../D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | not run | — | — | — | — | — |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | 187/192 | 91/96 | 9 | 9 | all `ok` | [report](../../D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | 27/48 | 21/36 | 9 | 9 | all `ok` | [report](../../D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | not run | — | — | — | — | — |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | 75/80 | 44/48 | 7 | 7 | all `ok` | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | 252/512 | no split ranking | 5 | — | all `ok` | [report](../../D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | 366/768 | no split ranking | 10 | — | all `ok` | [report](../../D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | 94/128 | no split ranking | 7 | — | all `ok` | [report](../../D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Routing tiers, relevance v2 and human confirmation

Packs added on 1 November 2026, joined to this observation by weights and runtime identity. Human confirmation counts are on TEST.

| Pack | Result | Rank | Report |
|---|---|---:|---|
| Facade routing, advanced tier | 86/96 (test 59/64) | 5 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Facade routing, complex tier | 79/96 (test 49/64) | 5 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Passage relevance v2 | 371/512 (test 181/256; macro 84.6%) | 5 | [report](../../PASSAGE_RELEVANCE_V2_RESULTS_20261101.md) |
| Human confirmation, explicit option | asks before 5/12 irreversible actions and 0/12 hesitations; 2/38 false alarms | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |
| Human confirmation, own confidence | detects 18/24; 14/38 false alarms; AUC 0.81 | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 52.0 | 54.0 | 132 | NR | 2.75 | NR | NR |

Scope: Sampled owned process-group peak over fresh session startup, controls, warm-up and this pack; not total GPU memory. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
