# Vela 2.0 0.3B · macOS CPU

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 0.309B declared |
| Runtime | macOS arm64 CPU, pinned runtime |
| Family | Vela 2.0 |
| Precision | FP32 |
| Hardware | Apple M5 Pro CPU; 64 GiB unified memory |
| Observed | 2026-10-30 |
| Protocol / evidence | [VELA2_03_MACOS_CPU_PROTOCOL_20261030.md](../../VELA2_03_MACOS_CPU_PROTOCOL_20261030.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 65/132 | 37/66 | 31 | 30 | all `ok` | [VELA2_03_MACOS_CPU_PROTOCOL_20261030](../../VELA2_03_MACOS_CPU_PROTOCOL_20261030.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | 18/24 | no test split | — | — | all `ok` | provisional agreement, zero qualified cases |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | 128/192 | 62/96 | 12 | 12 | all `ok` | [report](../../VELA2_03_MACOS_RESULTS_20261030.md) |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | 18/48 | 14/36 | 10 | 10 | all `ok` | [report](../../VELA2_03_MACOS_RESULTS_20261030.md) |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | 0/32 | 0/12 | 4 | 4 | all `ok` | [report](../../TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md) |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | 64/80 | 34/48 | 10 | 10 | all `ok` | [report](../../FACADE_ROUTING_RESULTS_20261101.md) |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | 112/512 | no split ranking | 12 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | 151/768 | no split ranking | 12 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | 93/128 | no split ranking | 8 | — | all `ok` | [report](../../PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Routing tiers, relevance v2 and human confirmation

Packs added on 1 November 2026, joined to this observation by weights and runtime identity. Human confirmation counts are on TEST.

| Pack | Result | Rank | Report |
|---|---|---:|---|
| Facade routing, advanced tier | 71/96 (test 53/64) | 6 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Facade routing, complex tier | 49/96 (test 24/64) | 7 | [report](../../FACADE_ROUTING_TIERS_RESULTS_20261101.md) |
| Passage relevance v2 | 113/512 (test 59/256; macro 27.4%) | 7 | [report](../../PASSAGE_RELEVANCE_V2_RESULTS_20261101.md) |
| Human confirmation, explicit option | asks before 1/12 irreversible actions and 0/12 hesitations; 4/38 false alarms | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |
| Human confirmation, own confidence | detects 20/24; 22/38 false alarms; AUC 0.72 | — | [report](../../FACADE_ROUTING_HITL_RESULTS_20261101.md) |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 154.0 | 195.8 | 132 | 5,922.9 | NR | 1.18 | NR |

Scope: Per-response worker RSS, context-choice phase; not total host memory. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
