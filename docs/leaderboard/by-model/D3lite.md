# D3 lite · CPU

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 0.853B backbone |
| Runtime | Historical Linux/WSL CPU (processor not identified) |
| Family | Decision 3.0 |
| Precision | BF16 backbone / FP32 readout |
| Hardware | Historical Linux/WSL CPU; processor not identified here |
| Observed | 2026-10-11 |
| Protocol / evidence | [D3_CPU_PILOT.md](../../D3_CPU_PILOT.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 95/132 | 50/66 | 17 | 17 | all `ok` | [D3_CPU_PILOT](../../D3_CPU_PILOT.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | 19/24 | no test split | — | — | all `ok` | provisional agreement, zero qualified cases |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | not run | — | — | — | — | — |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | not run | — | — | — | — | — |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | not run | — | — | — | — | — |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | not run | — | — | — | — | — |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 1,002.3 | 1,349.6 | 132 | 11,239.6 | NR | 1.80 | NR |

Scope: Per-response worker RSS, context-choice phase; not total host memory. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
