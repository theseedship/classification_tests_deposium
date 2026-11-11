# GLiClass v4 2B · BF16 MPS

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 2B class |
| Runtime | PyTorch MPS, Apple M5 Pro |
| Family | GLiClass v4 |
| Precision | BF16 |
| Hardware | Apple M5 Pro GPU (MPS); 64 GiB unified memory |
| Observed | 2026-11-11 |
| Protocol / evidence | [GLICLASS_V4_2B_PROTOCOL_20261111.md](../../GLICLASS_V4_2B_PROTOCOL_20261111.md), [GLICLASS_V4_2B_RESULTS_20261111.md](../../GLICLASS_V4_2B_RESULTS_20261111.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 103/132 | 57/66 | 20 | 19 | all `ok` | [GLICLASS_V4_2B_PROTOCOL_20261111](../../GLICLASS_V4_2B_PROTOCOL_20261111.md), [GLICLASS_V4_2B_RESULTS_20261111](../../GLICLASS_V4_2B_RESULTS_20261111.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | not run | — | — | — | — | — |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | 186/192 | 95/96 | 11 | 9 | all `ok` | [report](../../GLICLASS_V4_2B_RESULTS_20261111.md) |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | 28/48 | 20/36 | 9 | 11 | all `ok` | [report](../../GLICLASS_V4_2B_RESULTS_20261111.md) |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | not run | — | — | — | — | — |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | 76/80 | 44/48 | 7 | 8 | all `ok` | [report](../../GLICLASS_V4_2B_RESULTS_20261111.md) |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | not run | — | — | — | — | — |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Routing tiers, relevance v2 and human confirmation

Packs added on 1 November 2026, joined to this observation by weights and runtime identity. Human confirmation counts are on TEST.

| Pack | Result | Rank | Report |
|---|---|---:|---|
| Facade routing, advanced tier | 85/96 (test 55/64) | 7 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Facade routing, complex tier | 86/96 (test 56/64) | 6 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Passage relevance v2 | 359/512 (test 181/256; macro 51.2%) | 7 | [report](../../PASSAGE_RELEVANCE_V2_RESULTS_20261101.md) |
| Human confirmation, explicit option | asks before 4/12 irreversible actions and 0/12 hesitations; 5/38 false alarms | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |
| Human confirmation, own confidence | detects 20/24; 19/38 false alarms; AUC 0.77 | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 130.2 | 392.8 | 132 | NR | 1.14 | NR | 4.41 |

Scope: maximum of the worker's own ru_maxrss after loading and after each case; single MPS worker process, not a process-group sample. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
