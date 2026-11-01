# D3 flash · Q8 direct Metal

[All results](../../RESULTS.md) · [All models](README.md) · [Coverage overview](../../RESULTS.md#coverage-overview)

One observation: one checkpoint, one runtime, one pass per case. Scores are **correct / all cases** with failures kept in the denominator; **rank** is the competition rank among completely scored observations on the same task. References are agent-authored and pending human review; a few-case lead on correlated FR/EN variants is not a general ranking.

## Identity

| Item | Value |
|---|---|
| Size | 9B class |
| Runtime | Direct upstream native Metal, Apple M5 Pro |
| Family | Decision 3.0 |
| Precision | Q8_0 |
| Hardware | Apple M5 Pro; 64 GiB unified memory |
| Observed | 2026-10-29 |
| Protocol / evidence | [PHYSICS_FLASH_RESULTS_20261029.md](../../PHYSICS_FLASH_RESULTS_20261029.md) |

## Results by task

| Family | Task | Correct / all | Held-out test | Rank all | Rank test | Execution | Report |
|---|---|---:|---:|---:|---:|---|---|
| RAG decision | [Context choices](../../RESULTS.md#model-quality) | 124/132 | 61/66 | 2 | 4 | all `ok` | [PHYSICS_FLASH_RESULTS_20261029](../../PHYSICS_FLASH_RESULTS_20261029.md) |
| RAG decision | [First-tool proposals](../../RESULTS.md#model-quality) | not run | — | — | — | — | — |
| Tool workflow | [Capability and workflow choices](../../RESULTS.md#capability-choices) | not run | — | — | — | — | — |
| Reasoning with a supplied law | [Physics choices](../../RESULTS.md#physics-choices) | 39/48 | 32/36 | 2 | 1 | all `ok` | [report](../../PHYSICS_FLASH_RESULTS_20261029.md) |
| Tool workflow, executed | [Executed tool episodes (closed choice)](../../RESULTS.md#executed-tool-episodes-closed-choice) | not run | — | — | — | — | — |
| Tool routing | [Facade routing (model vs router)](../../RESULTS.md#facade-routing-model-vs-router) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage relevance](../../RESULTS.md#passage-relevance) | 252/512 | no split ranking | 4 | — | all `ok` | [report](../../PASSAGE_FLASH_RESULTS_20261029.md) |
| Retrieved evidence | [Claim support](../../RESULTS.md#claim-support) | 460/768 | no split ranking | 3 | — | all `ok` | [report](../../PASSAGE_FLASH_RESULTS_20261029.md) |
| Retrieved evidence | [Answerability](../../RESULTS.md#answerability) | 122/128 | no split ranking | 1 | — | all `ok` | [report](../../PASSAGE_FLASH_RESULTS_20261029.md) |
| Retrieved evidence | [Passage relevance, four rotations](../../RESULTS.md#passage-relevance) | not run | — | — | — | — | — |
| Retrieved evidence | [Passage ranking](../../leaderboard/other-benchmarks.md#passage-ranking-and-evidence) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool discovery (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool arguments (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |
| Tool policy, generated | [Tool episodes (generated JSON)](../../RESULTS.md#generated-json-tool-policy-observations) | not run | — | — | — | — | — |

## Speed and memory (context session)

| Median call ms | p95 call ms | Timed calls | Initialization ms | Session RSS GiB | Worker RSS GiB | GPU allocated GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 194.6 | 200.6 | 132 | NR | 9.36 | NR | NR |

Scope: Sampled owned process-group peak over fresh session startup, controls, warm-up and this pack; not total GPU memory. Latency is descriptive, not a throughput guarantee.

## Reading this page

- **Execution** says whether the campaign ran cleanly: `all ok` means every case produced a valid answer; other statuses (`timeout`, `error`, `missing`, `unsupported`, `abstain`) are counted and stay in the denominator of the score.
- **not run** means no public observation for this task on this runtime; it is not a zero.
- Partial campaigns are shown with their scored count and are never ranked.
- Generated regularly from the sealed public aggregates by `scripts/build-full-results.py`; nothing here reruns a model.
