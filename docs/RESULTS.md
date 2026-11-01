# Full results

[README](../README.md) · [At a glance](#at-a-glance) · [Contents](#contents) · [Every model, every task](leaderboard/by-model/README.md) · [Passages and other campaigns](leaderboard/other-benchmarks.md) · [Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)

**40 context model/runtime observations through 1 November 2026**: 28 earlier observations, the macOS CPU D3 lite, Vela 2.0 0.3B, D3 nano and D3 mini runtimes, Clef Flash Q8, the direct upstream D3 Flash Q8 runtime, D3 lite, nano and mini Q8 on Metal, and the deployment variants D3 mini Q4 and D3 Flash Q4 on Metal and D3 Flash 4-bit on Uzu.
Rows identify observations, not independent model families. Gateway-backed and direct native binaries remain distinct. Repeated exports of the same sealed run are deduplicated;
quantizations and devices remain separate. Rendering this page does not rerun or rescore models.

**Exploratory evidence:** synthetic, agent-authored references and translations await human review.
The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.
FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.

## Contents

- [At a glance](#at-a-glance)
- [Coverage overview](#coverage-overview)
  - [Context model/runtime observations](#context-modelruntime-observations)
  - [Passage-only observations and ranking methods](#passage-only-observations-and-ranking-methods)
  - [Generated-JSON tool-policy observations](#generated-json-tool-policy-observations)
- [Harness coverage](#harness-coverage)
- [Updated task rankings](#updated-task-rankings)
  - [Capability choices](#capability-choices)
  - [Physics choices](#physics-choices)
  - [Passage relevance](#passage-relevance)
  - [Claim support](#claim-support)
  - [Answerability](#answerability)
  - [Executed tool episodes (closed choice)](#executed-tool-episodes-closed-choice)
  - [Facade routing (model vs router)](#facade-routing-model-vs-router)
  - [Facade routing: harder tiers](#facade-routing-harder-tiers)
  - [Passage relevance v2 (three levels)](#passage-relevance-v2-three-levels)
  - [Facade routing: human confirmation](#facade-routing-human-confirmation)
  - [Deployment variants: Q4 and Uzu](#deployment-variants-q4-and-uzu)
  - [Campaign latency and memory](#campaign-latency-and-memory)
- [Model quality](#model-quality)
- [Language and task complexity](#language-and-task-complexity)
- [Speed and memory](#speed-and-memory)
- [Other evaluated protocols](#other-evaluated-protocols)
  - [Passage ranking and evidence](#passage-ranking-and-evidence)
  - [Passage latency and memory](#passage-latency-and-memory)
  - [Longer contexts](#longer-contexts)
  - [Repeated timing and stability](#repeated-timing-and-stability)
  - [Initial documentary routing pilot](#initial-documentary-routing-pilot)
- [Every task and downloadable data](#every-task-and-downloadable-data)
- [Provenance and reproduction](#provenance-and-reproduction)

## At a glance

One line per task, grouped by family: **RAG decision** (which source or first tool to use for a request), **Retrieved evidence** (judging passages: relevance, claim support, answerability), **Tool workflow** (selection, arguments, next step after observations; **executed** when real fixture tools run step by step), **Tool routing** (which tool category a request needs, small models against the production router), **Reasoning** (physics with the law supplied) and **Tool policy, generated** (free-form JSON actions). **Leader over all cases** counts every case of the pack, including failures; **leader on held-out test** uses only the test cases, the better signal against tuning. Ties are listed together. Tasks are never pooled into one score; a lead of a few cases on correlated FR/EN variants is not a general ranking. References are agent-authored and pending human review.

| Family | Task | Cases | Observations | Leader over all cases | Leader on held-out test | Details |
|---|---|---|---:|---|---|---|
| RAG decision | Context choices | 132 (66 test) | 40 | D3 27B · Q4 Metal (128/132) | D3 27B · Q4 Metal (65/66 test) | [Model quality](#model-quality) |
| RAG decision | First-tool proposals | 24 (no test split) | 32 | D3 27B · Q4 Metal (24/24) | provisional agreement, not routing accuracy | [Model quality](#model-quality) |
| Tool workflow | Capability and workflow choices | 192 (96 test) | 12 | Clef Flash Q8 · direct Metal (192/192), D3 flash · 4-bit Uzu (192/192), D3 flash · Q4 direct Metal (192/192), D3 Flash Q8 · gateway Metal (192/192), D3 mini · macOS CPU (192/192), D3 mini · Q4 Metal (192/192), D3 mini · Q8 Metal (192/192) (tie) | Clef Flash Q8 · direct Metal (96/96 test), D3 flash · 4-bit Uzu (96/96 test), D3 flash · Q4 direct Metal (96/96 test), D3 Flash Q8 · gateway Metal (96/96 test), D3 mini · macOS CPU (96/96 test), D3 mini · Q4 Metal (96/96 test), D3 mini · Q8 Metal (96/96 test) (tie) | [Capability](#capability-choices) |
| Reasoning with a supplied law | Physics choices | 48 (36 test) | 12 | Clef Flash Q8 · direct Metal (41/48) | D3 flash · 4-bit Uzu (32/36 test), D3 flash · Q4 direct Metal (32/36 test), D3 Flash Q8 · direct Metal (32/36 test), D3 mini · macOS CPU (32/36 test), D3 mini · Q8 Metal (32/36 test) (tie) | [Physics choices](#physics-choices) |
| Tool workflow, executed | Executed tool episodes (closed choice) | 32 (12 test) | 4 | D3 mini · macOS CPU (28/32) | D3 mini · macOS CPU (10/12 test) | [Executed episodes](#executed-tool-episodes-closed-choice) |
| Tool routing | Facade routing (model vs router) | 80 (48 test) | 11 | D3 flash · Q4 direct Metal (79/80), D3 mini · Q4 Metal (79/80), D3 mini · Q8 Metal (79/80), D3 mini · macOS CPU (79/80) (tie) | D3 flash · Q4 direct Metal (47/48 test), D3 mini · Q4 Metal (47/48 test), D3 mini · Q8 Metal (47/48 test), D3 mini · macOS CPU (47/48 test) (tie) | [Facade routing](#facade-routing-model-vs-router) |
| Tool routing | Facade routing, advanced tier | 96 (64 test) | 8 | D3 mini · Q4 Metal (94/96), D3 mini · Q8 Metal (94/96), D3 flash · Q4 direct Metal (94/96) (tie) | D3 mini · Q4 Metal (62/64 test), D3 mini · Q8 Metal (62/64 test), D3 flash · Q4 direct Metal (62/64 test) (tie) | [Harder tiers](#facade-routing-harder-tiers) |
| Tool routing | Facade routing, complex tier | 96 (64 test) | 8 | D3 mini · Q4 Metal (93/96) | D3 mini · Q4 Metal (61/64 test) | [Harder tiers](#facade-routing-harder-tiers) |
| Retrieved evidence | Passage relevance v2 (three levels) | 512 (256 test) | 7 | D3 mini · Q8 Metal (406/512), D3 mini · Q4 Metal (406/512) (tie) | D3 mini · Q8 Metal (200/256 test), D3 mini · Q4 Metal (200/256 test) (tie) | [Relevance v2](#passage-relevance-v2-three-levels) |
| Tool routing | Human confirmation (explicit option) | 90 (62 test) | 7 | D3 flash · Q4 direct Metal (asks on 11/24 test requests needing a human, 0/38 false alarms), D3 flash · 4-bit Uzu (asks on 11/24 test requests needing a human, 2/38 false alarms) (tie) | TEST only; own-confidence detection in the section | [Human confirmation](#facade-routing-human-confirmation) |
| Retrieved evidence | Passage relevance | 512 (rotation 0) | 12 | D3 mini · Q4 Metal (272/512) | no split ranking | [Passage relevance](#passage-relevance) |
| Retrieved evidence | Claim support | 768 (rotation 0) | 13 | D3 mini · Q4 Metal (540/768) | no split ranking | [Claim support](#claim-support) |
| Retrieved evidence | Answerability | 128 (rotation 0) | 13 | D3 flash · Q4 direct Metal (126/128) | no split ranking | [Answerability](#answerability) |
| Tool policy, generated | Generated-JSON tool policy | 10 + 6 + 18 (TRAIN canary + held-out) | 1 | Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2: discovery 3/10; arguments 6/6; episodes 7/18 passed (single observation, unranked) | held-out pack 9/24 over the three contracts; see the report | [Generated-JSON observations](#generated-json-tool-policy-observations) |

Rows further down keep every observation, partial campaigns included, with their denominators and statuses. For one model across every task, open [Every model, every task](leaderboard/by-model/README.md): one page per observation with scores, ranks, execution outcomes, speed and reports.

## Coverage overview

**Execution coverage, not accuracy.** Each cell is `complete`, `partial`, or `not_run`, followed by scored/valid decisions over the planned denominator when observed. All references remain **review_pending**, independently of execution. No overall accuracy combines these tasks.

`not_run` means no matching public observation; it does not mean unsupported or zero accuracy. A source with no attempted answerability decisions explicitly shows `not_run 0/128`. Unreported measurements remain NR in the [speed and memory table](#speed-and-memory). Recorded `missing`, `unsupported`, `error`, `timeout`, and `abstain` outcomes remain separate in the [coverage CSV](leaderboard/coverage.csv) and [JSON](leaderboard/coverage.json).

### Context model/runtime observations

The 40 rows below preserve quantization and runtime identities; sizes are publisher classes or declared counts, not independent measurements. **Metal gateway** and **direct Metal** are different paths; scores and task rankings follow below. Context/132 contains text/76, mathematics/28 and chemistry/28; [their scores and held-out test results](#model-quality) remain separate.

| Model / runtime observation | Size | Context /132 | Tool proposal /24 | Capability /192 | Physics /48 | Episodes (choice) /32 | Facade routing /80 | Relevance R0 /512 | Support R0 /768 | Answerability R0 /128 | Relevance R0–3 /2048 | Ranking R0–3 /512 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D3 27B · Q4 Metal | 27B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 flash · Q8 Metal (gateway) | 9B class | complete 132/132 | complete 24/24 | complete 192/192 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 flash · Q8 direct Metal | 9B class | complete 132/132 | not_run | not_run | complete 48/48 | not_run | not_run | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 flash · CPU | 8.393B backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Jev 1.13 · HTTP API | NR | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 flash · Q4 Metal | 9B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 flash · Q4 direct Metal | 9B class | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 mini · CPU | 4.539B backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 mini · macOS CPU | 4.539B backbone | complete 132/132 | complete 24/24 | complete 192/192 | complete 48/48 | complete 32/32 | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 mini · Q8 Metal | 4.539B backbone | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 flash · 4-bit Uzu | 9B class | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | not_run | not_run | not_run | not_run | not_run |
| D3 mini · Q4 Metal | 4.539B backbone | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 nano · CPU | 2.213B backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 nano · macOS CPU | 2.213B backbone | complete 132/132 | complete 24/24 | complete 192/192 | complete 48/48 | complete 32/32 | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 nano · Q8 Metal | 2.213B backbone | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| GLiClass v4 9B · BF16 MPS | 9B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Clef Flash · Q8 direct Metal | 9B class | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | not_run | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| Vela 2.0 4B · CPU | 4.211B | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Decision 2.0 Nox 4B · CPU | 4.208B | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Liquid d1-3B · CPU | 3.123B | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Noma · CPU | ~2.67B declared | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 lite · CPU | 0.853B backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 lite · macOS CPU | 0.853B backbone | complete 132/132 | complete 24/24 | complete 192/192 | complete 48/48 | complete 32/32 | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| D3 lite · Q8 Metal | 0.853B backbone | complete 132/132 | not_run | complete 192/192 | complete 48/48 | not_run | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| Decision 2.0 Sol 2B · CPU | 2B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Vela 2.0 0.8B · CPU | 0.755B declared | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Decision 2.0 Eos 0.8B · CPU | 0.8B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Decision 2.0 Eos 0.8B · Q8 Metal | 0.8B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| D3 edge · CPU | 0.594B backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Decision 2.0 Kai 0.6B · CPU | 0.6B class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Vela 2.0 0.3B · CPU | 0.309B declared | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Vela 2.0 0.3B · macOS CPU | 0.309B declared | complete 132/132 | complete 24/24 | complete 192/192 | complete 48/48 | complete 32/32 | complete 80/80 | complete 512/512 | complete 768/768 | complete 128/128 | not_run | not_run |
| GLiNER2.5-multi-Decide · CPU | NR | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Vela 3.0 fast · decision only · CPU | 0.380B decision backbone | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Laya multilingual · CPU | 322M declared | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Julia-1 · CPU | NR | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Liquid d1-omni-600M · CPU | 600M class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Indecis · untrained open mode · CPU | NR | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| ModernJEV-Decide-Preview · CPU | NR | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |
| Muose-50M-Decision · CPU | 50M class | complete 132/132 | complete 24/24 | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run | not_run |

### Passage-only observations and ranking methods

These do not add context models. D3-lite's passage session has a different runtime/settings identity fingerprint from its historical context session. Jev 1.14 is distinct from context Jev 1.13. BGE and tie-break methods are ranking observations, not newly evaluated context models.

| Model / method | Relevance R0 /512 | Support R0 /768 | Answerability R0 /128 | Relevance R0–3 /2048 | Ranking R0–3 /512 |
|---|---|---|---|---|---|
| D3 lite · CPU passage session | complete 512/512 | complete 768/768 | complete 128/128 | complete 2048/2048 | complete 512/512 |
| Jev 1.14 · HTTP API | not_run | partial 514/768 | not_run 0/128 | complete 2048/2048 | complete 512/512 |
| BGE v2-m3 · INT8 CPU | not_run | not_run | not_run | not_run | complete 512/512 |
| D3 lite + BGE tie-break · CPU | not_run | not_run | not_run | not_run | complete 512/512 |
| Jev 1.14 + BGE tie-break | not_run | not_run | not_run | not_run | complete 512/512 |

R0 means rotation 0 (128 pools, eight families, two correlated views). Relevance/512 and replayed relevance/2048 have different protocols; neither is ranking/512. Ranking cells cover 512 pools over four balanced rotations; nDCG@1 is defined on 480/480 eligible pools. D3-lite/Jev ranking replays existing relevance decisions; rotations add no model calls. Tie-break rows are offline combined methods, with projected sequential cost rather than a measured integrated pipeline. [Ranking scores, controls and evidence retention](#passage-ranking-and-evidence) remain separate from classification.

### Generated-JSON tool-policy observations

A different candidate output path: the model generates a shortlist/selection, sum arguments or one episode action per step, and the runtime executes the synthetic tools. Cells count passed/scored cases over the TRAIN canary plus the held-out TEST pack under prompt v2 (complete observations only; the 30 classifier rows have no observation on these columns). Scores, failure modes and the partial first held-out attempt are in the [dated reports](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md).

| Model / runtime observation | Size | Discovery (JSON) /10 | Arguments (JSON) /6 | Episodes (JSON) /18 |
|---|---|---|---|---|
| Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2 | 4B class | complete 10/10 | complete 6/6 | complete 18/18 |

Cells are execution coverage, as above. Passed cases over scored cases: Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2: discovery 3/10 passed, arguments 6/6 passed, episodes 7/18 passed. A passed case is an exact match of the authored outcome (and minimal tool set, or actual execution receipt); a correct clarification or stop is procedure handling, not task success.

The 24-case tool column reports valid provisional proposals: **zero human-approved references and zero semantically qualified cases**. Complete coverage does not qualify routing or tool execution. See [task-specific rankings](#updated-task-rankings), [historical context quality](#model-quality), [full task CSV](leaderboard/task-breakdown.csv), and the dated [D3 capability report](CAPABILITY_FLASH_RESULTS_20261029.md) for scores and source details.

## Harness coverage

A missing model observation and a missing harness capability are different gaps. The global boundaries below apply to every model; they are not model `unsupported` outcomes. [Reference review #8](https://github.com/theseedship/classification_tests_deposium/issues/8) remains pending even where execution is complete.

| Capability | Harness / campaign status | What remains unqualified | Next issue |
|---|---|---|---|
| Closed context, first-tool, capability and physics choices | implemented | Observed only on supplied alternatives; tool/24 remains provisional and executes no tool. | — |
| Fixed-pool relevance, support, answerability and ranking | implemented | Separate rotation/metric scopes above; no live retrieval or final answers. | — |
| Versioned task contract beyond supplied proposals | fixture_only | [Bounded contract](TOOL_PLAN_CONTRACT_V1.md) and two recorded FR/EN training controls; no qualified model output path, model result or executed tools. | [#9](https://github.com/theseedship/classification_tests_deposium/issues/9) |
| Open catalogue discovery and sufficient tool sets | model_observed | [Tool-discovery contract](TOOL_DISCOVERY_CONTRACT_V1.md): 12 FR/EN recorded-control cases, separate shortlist/final-set metrics. One generative candidate observed through the local JSON route on the canary/held-out packs (see the generated-JSON coverage row); no executed tools, no application integration. | [#10](https://github.com/theseedship/classification_tests_deposium/issues/10) |
| Executable arguments and artifact bindings | model_observed | [Argument-execution contract](TOOL_ARGUMENTS_CONTRACT_V1.md): four FR/EN training controls with actual bounded lookup/sum and artifact guards. One generative candidate observed on the canary/held-out argument cases (6/6); no application integration. | [#11](https://github.com/theseedship/classification_tests_deposium/issues/11) |
| Bounded episodes with executed tools and feedback | model_observed | [Episode contract](TOOL_EPISODES_CONTRACT_V1.md): 14 FR/EN training controls with actual observations, retry/stopping guards and separate stage metrics. One generative candidate observed on the canary/held-out episodes (7/18): positive paths pass, stop/clarify outcomes mostly fail; no application qualification. | [#12](https://github.com/theseedship/classification_tests_deposium/issues/12) |
| Generated JSON proposals from a local model | model_observed | Qwen3-4B Q8, five observations: [TRAIN prompt v1](LOCAL_TOOL_POLICY_RESULTS_20261030.md) 5/10 scored of 10 (0/2 discovery, 2/2 arguments, 3/6 episodes); [TRAIN prompt v2](LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md) 7/10 scored of 10 (1/2 discovery, 2/2 arguments, 4/6 episodes), identical generated content with the [host prompt cache disabled](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md); [held-out prompt v2](LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md) attempt 1 9/18 scored of 24 (2/8 discovery, 4/4 arguments, 3/6 episodes), 6 unobserved after `rss_guard`, [attempt 2](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md) 9/24 scored of 24 (2/8 discovery, 4/4 arguments, 3/12 episodes). One model, correlated FR/EN pairs; no ranking, live MCP or product qualification. | [#35](https://github.com/theseedship/classification_tests_deposium/issues/35) |
| Order robustness and evidence retention | partial_coverage | [Offline order/retention analysis](PASSAGE_ORDER_RETENTION_V1.md) covers four rotations and both views (920 distinct test inputs); historical ranking exists, while new Flash classifications still cover rotation 0 only. No new model calls. | [#13](https://github.com/theseedship/classification_tests_deposium/issues/13) |
| Remaining cohort on new packs | not_run | [Historical 27B readiness](D3_27B_CAPABILITY_PROTOCOL_20261030.md) has a candidate-bound offline envelope; execution is deferred with zero new cases. Historical context scores cannot fill new task cells. | [#14](https://github.com/theseedship/classification_tests_deposium/issues/14) |
| Clef 27B candidate envelope | not_run | Separate runtime/resource qualification is required. | [#15](https://github.com/theseedship/classification_tests_deposium/issues/15) |
| Empirical small/large allocation and replay | not_implemented | Authored difficulty strata and confidence are not model-size ground truth. | [#16](https://github.com/theseedship/classification_tests_deposium/issues/16) |
| Pinned application harness integration | not_implemented | An integration registry or isolated model run does not establish live application behavior. | [#17](https://github.com/theseedship/classification_tests_deposium/issues/17) |
| Evidence-to-answer generation and citation fidelity | not_implemented | No complete retrieval-to-answer campaign is qualified. | [#18](https://github.com/theseedship/classification_tests_deposium/issues/18) |

The initial contract, discovery, arguments and episode fixtures are implemented as scripted controls. The [local JSON route](LOCAL_TOOL_POLICY_V1.md) has TRAIN canary observations (prompt v1 5/10, prompt v2 7/10, unchanged with the host prompt cache disabled) and a complete held-out observation of 9/24 ([report](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md)) after a first partial attempt. Every declared contract outcome has now been observed at least once; most nonselection and stop outcomes fail. See [campaign status](CAMPAIGN_STATUS.md) for the working sequence.

## Updated task rankings

These tables include every published campaign on these packs. Each task has its own ranking and denominator; there is no pooled cross-task score. Ranks use correct/all among completely scored observations on the same task/denominator. Partial and unrun campaigns remain visible but unranked. Ties share competition ranks. Canaries and repeated context anchors do not add quality cases.

### Capability choices

<sub>**Rank all**: competition rank by correct answers over every case of the pack (all splits); **Rank test**: the same rank over the held-out test cases only, the better signal against tuning; equal totals share a rank. **Correct / all** keeps failed, missing and unsupported cases in the denominator; **Scored / all** shows how many cases produced a valid answer.</sub>

**Leading on held-out test**: Clef Flash Q8 · direct Metal (96/96 test), D3 flash · 4-bit Uzu (96/96 test), D3 flash · Q4 direct Metal (96/96 test), D3 Flash Q8 · gateway Metal (96/96 test), D3 mini · macOS CPU (96/96 test), D3 mini · Q4 Metal (96/96 test), D3 mini · Q8 Metal (96/96 test) (tie); **leading over all cases**: Clef Flash Q8 · direct Metal (192/192), D3 flash · 4-bit Uzu (192/192), D3 flash · Q4 direct Metal (192/192), D3 Flash Q8 · gateway Metal (192/192), D3 mini · macOS CPU (192/192), D3 mini · Q4 Metal (192/192), D3 mini · Q8 Metal (192/192) (tie). A lead of a few cases on correlated FR/EN variants is not a general ranking.

| Rank all | Rank test | Model / execution path | Correct / all | Scored / all | Test correct / all | Source |
|---:|---:|---|---:|---:|---:|---|
| 1 | 1 | Clef Flash Q8 · direct Metal | 192/192 | 192/192 | 96/96 | [Report](CLEF_FLASH_RESULTS_20261029.md) |
| 1 | 1 | D3 flash · 4-bit Uzu | 192/192 | 192/192 | 96/96 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 1 | 1 | D3 flash · Q4 direct Metal | 192/192 | 192/192 | 96/96 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 1 | 1 | D3 Flash Q8 · gateway Metal | 192/192 | 192/192 | 96/96 | [Report](CAPABILITY_FLASH_RESULTS_20261029.md) |
| 1 | 1 | D3 mini · macOS CPU | 192/192 | 192/192 | 96/96 | [Report](D3_MINI_MACOS_RESULTS_20261031.md) |
| 1 | 1 | D3 mini · Q4 Metal | 192/192 | 192/192 | 96/96 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 1 | 1 | D3 mini · Q8 Metal | 192/192 | 192/192 | 96/96 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 8 | 8 | D3 nano · macOS CPU | 188/192 | 192/192 | 92/96 | [Report](D3_NANO_MACOS_RESULTS_20261031.md) |
| 9 | 9 | D3 nano · Q8 Metal | 187/192 | 192/192 | 91/96 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 10 | 10 | D3 lite · Q8 Metal | 170/192 | 192/192 | 82/96 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 11 | 11 | D3 lite · macOS CPU | 168/192 | 192/192 | 80/96 | [Report](D3_LITE_MACOS_RESULTS_20261030.md) |
| 12 | 12 | Vela 2.0 0.3B · macOS CPU | 128/192 | 192/192 | 62/96 | [Report](VELA2_03_MACOS_RESULTS_20261030.md) |

Clef Flash Q8 · direct Metal, D3 flash · 4-bit Uzu, D3 flash · Q4 direct Metal, D3 Flash Q8 · gateway Metal, D3 mini · macOS CPU, D3 mini · Q4 Metal, D3 mini · Q8 Metal reach the ceiling on these supplied proposals; a perfect or near-perfect closed-choice score does not qualify executable tools. Runtimes differ per row (gateway-backed Metal, direct native listener, CPU worker) and are not pooled.

<sub>**Track**: the three case families of the pack; selection = choose capabilities/tool sets, arguments = bind arguments and dependencies, observations = choose the next step after fixed tool observations.</sub>

| Model | Track | Correct / all | Test correct / all |
|---|---|---:|---:|
| Clef Flash Q8 · direct Metal | Capability selection | 64/64 | 32/32 |
| Clef Flash Q8 · direct Metal | Arguments and dependencies | 64/64 | 32/32 |
| Clef Flash Q8 · direct Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 flash · 4-bit Uzu | Capability selection | 64/64 | 32/32 |
| D3 flash · 4-bit Uzu | Arguments and dependencies | 64/64 | 32/32 |
| D3 flash · 4-bit Uzu | Next step after fixed observations | 64/64 | 32/32 |
| D3 flash · Q4 direct Metal | Capability selection | 64/64 | 32/32 |
| D3 flash · Q4 direct Metal | Arguments and dependencies | 64/64 | 32/32 |
| D3 flash · Q4 direct Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Capability selection | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Arguments and dependencies | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 mini · macOS CPU | Capability selection | 64/64 | 32/32 |
| D3 mini · macOS CPU | Arguments and dependencies | 64/64 | 32/32 |
| D3 mini · macOS CPU | Next step after fixed observations | 64/64 | 32/32 |
| D3 mini · Q4 Metal | Capability selection | 64/64 | 32/32 |
| D3 mini · Q4 Metal | Arguments and dependencies | 64/64 | 32/32 |
| D3 mini · Q4 Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 mini · Q8 Metal | Capability selection | 64/64 | 32/32 |
| D3 mini · Q8 Metal | Arguments and dependencies | 64/64 | 32/32 |
| D3 mini · Q8 Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 nano · macOS CPU | Capability selection | 63/64 | 31/32 |
| D3 nano · macOS CPU | Arguments and dependencies | 61/64 | 29/32 |
| D3 nano · macOS CPU | Next step after fixed observations | 64/64 | 32/32 |
| D3 nano · Q8 Metal | Capability selection | 63/64 | 31/32 |
| D3 nano · Q8 Metal | Arguments and dependencies | 60/64 | 28/32 |
| D3 nano · Q8 Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 lite · Q8 Metal | Capability selection | 47/64 | 23/32 |
| D3 lite · Q8 Metal | Arguments and dependencies | 59/64 | 27/32 |
| D3 lite · Q8 Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 lite · macOS CPU | Capability selection | 47/64 | 23/32 |
| D3 lite · macOS CPU | Arguments and dependencies | 57/64 | 25/32 |
| D3 lite · macOS CPU | Next step after fixed observations | 64/64 | 32/32 |
| Vela 2.0 0.3B · macOS CPU | Capability selection | 53/64 | 26/32 |
| Vela 2.0 0.3B · macOS CPU | Arguments and dependencies | 30/64 | 11/32 |
| Vela 2.0 0.3B · macOS CPU | Next step after fixed observations | 45/64 | 25/32 |

### Physics choices

<sub>**Rank all**: competition rank by correct answers over every case of the pack (all splits); **Rank test**: the same rank over the held-out test cases only, the better signal against tuning; equal totals share a rank. **Correct / all** keeps failed, missing and unsupported cases in the denominator; **Scored / all** shows how many cases produced a valid answer.</sub>

**Leading on held-out test**: D3 flash · 4-bit Uzu (32/36 test), D3 flash · Q4 direct Metal (32/36 test), D3 Flash Q8 · direct Metal (32/36 test), D3 mini · macOS CPU (32/36 test), D3 mini · Q8 Metal (32/36 test) (tie); **leading over all cases**: Clef Flash Q8 · direct Metal (41/48). A lead of a few cases on correlated FR/EN variants is not a general ranking.

| Rank all | Rank test | Model / execution path | Correct / all | Scored / all | Test correct / all | Source |
|---:|---:|---|---:|---:|---:|---|
| 1 | 6 | Clef Flash Q8 · direct Metal | 41/48 | 48/48 | 31/36 | [Report](CLEF_FLASH_RESULTS_20261029.md) |
| 2 | 1 | D3 flash · 4-bit Uzu | 40/48 | 48/48 | 32/36 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 3 | 1 | D3 flash · Q4 direct Metal | 39/48 | 48/48 | 32/36 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 3 | 1 | D3 Flash Q8 · direct Metal | 39/48 | 48/48 | 32/36 | [Report](PHYSICS_FLASH_RESULTS_20261029.md) |
| 3 | 1 | D3 mini · macOS CPU | 39/48 | 48/48 | 32/36 | [Report](D3_MINI_MACOS_RESULTS_20261031.md) |
| 3 | 1 | D3 mini · Q8 Metal | 39/48 | 48/48 | 32/36 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 7 | 7 | D3 mini · Q4 Metal | 36/48 | 48/48 | 30/36 | [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 8 | 8 | D3 nano · macOS CPU | 28/48 | 48/48 | 22/36 | [Report](D3_NANO_MACOS_RESULTS_20261031.md) |
| 9 | 9 | D3 nano · Q8 Metal | 27/48 | 48/48 | 21/36 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 10 | 10 | Vela 2.0 0.3B · macOS CPU | 18/48 | 48/48 | 14/36 | [Report](VELA2_03_MACOS_RESULTS_20261030.md) |
| 11 | 11 | D3 lite · macOS CPU | 14/48 | 48/48 | 12/36 | [Report](D3_LITE_MACOS_RESULTS_20261030.md) |
| 11 | 11 | D3 lite · Q8 Metal | 14/48 | 48/48 | 12/36 | [Report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |

Calibration (12) and test (36) are shown separately because the all-case and test leaders can differ; with four options, 12/48 is chance level. No result establishes general physics expertise: the law and assumptions are supplied in each input.

### Passage relevance

Rotation 0: 128 pools, eight families, eight language directions, two correlated views. Classes are imbalanced: always answering grade 1 (thematic) scores **224/512**, so compare macro class accuracy, not totals alone.

<sub>**Rank**: by correct/all among completely scored observations (— when partial or not run); **Macro class accuracy**: mean of the per-class accuracies, so a rare class weighs as much as a frequent one.</sub>

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | D3 mini · Q4 Metal | 272/512 | 512/512 | 61.55% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 2 | D3 mini · macOS CPU | 266/512 | 512/512 | 60.56% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 2 | D3 mini · Q8 Metal | 266/512 | 512/512 | 60.56% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 4 | Clef Flash Q8 · direct Metal | 261/512 | 512/512 | 60.40% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 5 | D3 Flash Q8 · direct Metal | 252/512 | 512/512 | 59.06% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 5 | D3 nano · macOS CPU | 252/512 | 512/512 | 62.84% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 5 | D3 nano · Q8 Metal | 252/512 | 512/512 | 62.84% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 8 | D3 flash · Q4 direct Metal | 247/512 | 512/512 | 58.24% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 9 | D3 lite · Q8 Metal | 231/512 | 512/512 | 49.82% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 10 | D3-lite · CPU | 229/512 | 512/512 | 49.60% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |
| 10 | D3 lite · macOS CPU | 229/512 | 512/512 | 49.60% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 12 | Vela 2.0 0.3B · macOS CPU | 112/512 | 512/512 | 32.46% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |

### Claim support

Rotation 0: 128 pools, eight families, eight language directions, two correlated views. Classes are imbalanced: always answering `insufficient` scores **584/768**, so compare macro class accuracy, not totals alone.

<sub>**Rank**: by correct/all among completely scored observations (— when partial or not run); **Macro class accuracy**: mean of the per-class accuracies, so a rare class weighs as much as a frequent one.</sub>

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | D3 mini · Q4 Metal | 540/768 | 768/768 | 85.14% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 2 | D3 mini · macOS CPU | 527/768 | 768/768 | 84.14% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 3 | D3 mini · Q8 Metal | 517/768 | 768/768 | 83.83% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 4 | D3 Flash Q8 · direct Metal | 460/768 | 768/768 | 79.79% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 5 | D3 lite · Q8 Metal | 449/768 | 768/768 | 81.27% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 6 | Clef Flash Q8 · direct Metal | 446/768 | 768/768 | 81.09% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 7 | D3-lite · CPU | 443/768 | 768/768 | 80.92% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |
| 8 | D3 lite · macOS CPU | 439/768 | 768/768 | 80.69% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 9 | D3 flash · Q4 direct Metal | 430/768 | 768/768 | 79.39% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 10 | D3 nano · macOS CPU | 366/768 | 768/768 | 76.79% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 10 | D3 nano · Q8 Metal | 366/768 | 768/768 | 76.79% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 12 | Vela 2.0 0.3B · macOS CPU | 151/768 | 768/768 | 41.63% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| — | Jev 1.14 · API | 394/768 | 514/768 | 90.05% | partial; [report](PASSAGE_JEV_RESULTS_20261015.md) |

### Answerability

Rotation 0: 128 pools, eight families, eight language directions, two correlated views. Classes are imbalanced: always answering `answerable` scores **88/128**, so compare macro class accuracy, not totals alone.

<sub>**Rank**: by correct/all among completely scored observations (— when partial or not run); **Macro class accuracy**: mean of the per-class accuracies, so a rare class weighs as much as a frequent one.</sub>

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | D3 flash · Q4 direct Metal | 126/128 | 128/128 | 99.24% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 2 | D3 Flash Q8 · direct Metal | 122/128 | 128/128 | 97.73% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 3 | Clef Flash Q8 · direct Metal | 109/128 | 128/128 | 68.31% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 4 | D3 mini · macOS CPU | 104/128 | 128/128 | 80.68% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 5 | D3 mini · Q8 Metal | 102/128 | 128/128 | 76.52% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 6 | D3 mini · Q4 Metal | 100/128 | 128/128 | 75.76% | complete; [report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md) |
| 7 | D3 nano · Q8 Metal | 94/128 | 128/128 | 87.12% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| 8 | D3 nano · macOS CPU | 93/128 | 128/128 | 86.74% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 8 | Vela 2.0 0.3B · macOS CPU | 93/128 | 128/128 | 46.72% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 10 | D3-lite · CPU | 88/128 | 128/128 | 80.81% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |
| 10 | D3 lite · macOS CPU | 88/128 | 128/128 | 80.81% | complete; [report](PASSAGE_SMALL_CPU_RESULTS_20261031.md) |
| 10 | D3 lite · Q8 Metal | 88/128 | 128/128 | 80.81% | complete; [report](D3_SMALL_GGUF_METAL_RESULTS_20261101.md) |
| — | Jev 1.14 · API | Not run | 0/128 | NR | not_run; [report](PASSAGE_JEV_RESULTS_20261015.md) |

Class macro accuracy averages the scored class accuracies. Jev's partial support macro is conditional on its observed subset and is not a complete-coverage comparison; unobserved decisions remain missing in the totals.

Jev's published relevance export is **1260/2048**, scored 2048/2048, over four rotations. It is retained in the downloads as `passage_relevance_four_rotations`, outside the 512-decision relevance ranking. Replayed rotations are not extra independent model calls.

Support insufficiency/refutation remains weak for both Flash candidates. Clef accepts 12/16 pools annotated as conflicting as answerable; D3 accepts none in this finite run. See [paired outcomes and confusion matrices](PASSAGE_CLEF_RESULTS_20261029.md). This is not factual-verifier or end-to-end qualification. The four macOS CPU rows (D3 lite, nano, mini, Vela 2.0 0.3B), their per-class errors and their cost per call are in the [small-CPU passage report](PASSAGE_SMALL_CPU_RESULTS_20261031.md).

### Executed tool episodes (closed choice)

32 synthetic episodes (20 TRAIN, 12 TEST) run with real fixture tools: at each step the harness lists the possible next actions, the model picks one, the tool runs and its actual result feeds the next step. A case passes when the whole procedure is valid, the stop is correct and budgets hold; **task success** counts the twelve episodes whose correct end is a computed total. Premature success and malformed actions are impossible by construction, so these scores are not comparable with the generated-JSON policy. [Pilot report](TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md).

<sub>**Rank all**: competition rank by correct answers over every case of the pack (all splits); **Rank test**: the same rank over the held-out test cases only, the better signal against tuning; equal totals share a rank. **Correct / all** keeps failed, missing and unsupported cases in the denominator; **Scored / all** shows how many cases produced a valid answer.</sub>

**Leading on held-out test**: D3 mini · macOS CPU (10/12 test); **leading over all cases**: D3 mini · macOS CPU (28/32).

| Rank all | Rank test | Model / runtime | Procedure correct / all | Test correct / all | Task success / eligible | Stop correct / all | Execution | Steps | Tool calls | Median call s |
|---:|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | 1 | D3 mini · macOS CPU | 28/32 | 10/12 | 10/12 | 28/32 | all `ok` | 76 | 44 | 74.0 |
| 2 | 3 | D3 nano · macOS CPU | 16/32 | 4/12 | 10/12 | 17/32 | all `ok` | 118 | 53 | 31.3 |
| 3 | 2 | D3 lite · macOS CPU | 14/32 | 5/12 | 9/12 | 15/32 | all `ok` | 125 | 52 | 13.8 |
| 4 | 4 | Vela 2.0 0.3B · macOS CPU | 0/32 | 0/12 | 0/12 | 0/32 | all `ok` | 32 | 0 | 0.2 |

**Steps** counts model decisions; **tool calls** counts actual fixture executions. A model that keeps choosing the first option or always the same stop shows it in the chosen-position distribution of the report.

### Facade routing (model vs router)

80 synthetic FR/EN requests to a document assistant (16 TRAIN, 16 calibration, 48 TEST): which of eight tool categories should handle the request, or *none* (out of scope or too vague). The production router is a deterministic function replayed privately at a pinned revision; only its aggregate scores are public, so its row is **not externally reproducible**. References were written without access to its rules. [Report and limits](DEPLOYMENT_VARIANTS_RESULTS_20261101.md).

<sub>**Rank all**: competition rank by correct answers over every case of the pack (all splits); **Rank test**: the same rank over the held-out test cases only, the better signal against tuning; equal totals share a rank. **Correct / all** keeps failed, missing and unsupported cases in the denominator; **Scored / all** shows how many cases produced a valid answer.</sub>

**Leading on held-out test**: D3 flash · Q4 direct Metal (47/48 test), D3 mini · Q4 Metal (47/48 test), D3 mini · Q8 Metal (47/48 test), D3 mini · macOS CPU (47/48 test) (tie); **leading over all cases**: D3 flash · Q4 direct Metal (79/80), D3 mini · Q4 Metal (79/80), D3 mini · Q8 Metal (79/80), D3 mini · macOS CPU (79/80) (tie).

| Rank all | Rank test | Model / runtime | Correct / all | Test / 48 | Direct /28 | Paraphrase /28 | Refused alternative /10 | Two-step /4 | Out of scope or vague /10 | Right where router wrong / router right where model wrong | Median call ms |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | D3 flash · Q4 direct Metal | 79/80 | 47/48 | 28/28 | 28/28 | 9/10 | 4/4 | 10/10 | 51 / 0 | 292.2 |
| 1 | 1 | D3 mini · Q4 Metal | 79/80 | 47/48 | 28/28 | 28/28 | 9/10 | 4/4 | 10/10 | 51 / 0 | 167.1 |
| 1 | 1 | D3 mini · Q8 Metal | 79/80 | 47/48 | 28/28 | 28/28 | 9/10 | 4/4 | 10/10 | 51 / 0 | 161.4 |
| 1 | 1 | D3 mini · macOS CPU | 79/80 | 47/48 | 28/28 | 28/28 | 9/10 | 4/4 | 10/10 | 51 / 0 | 29,839.1 |
| 5 | 5 | D3 flash · 4-bit Uzu | 78/80 | 46/48 | 28/28 | 27/28 | 9/10 | 4/4 | 10/10 | 50 / 0 | 110.0 |
| 6 | 6 | D3 nano · macOS CPU | 76/80 | 45/48 | 27/28 | 26/28 | 9/10 | 4/4 | 10/10 | 48 / 0 | 11,608.7 |
| 7 | 7 | D3 nano · Q8 Metal | 75/80 | 44/48 | 27/28 | 25/28 | 9/10 | 4/4 | 10/10 | 47 / 0 | 71.1 |
| 8 | 8 | D3 lite · Q8 Metal | 71/80 | 40/48 | 27/28 | 21/28 | 9/10 | 4/4 | 10/10 | 43 / 0 | 39.5 |
| 8 | 8 | D3 lite · macOS CPU | 71/80 | 40/48 | 27/28 | 21/28 | 9/10 | 4/4 | 10/10 | 43 / 0 | 5,071.3 |
| 10 | 10 | Vela 2.0 0.3B · macOS CPU | 64/80 | 34/48 | 26/28 | 17/28 | 9/10 | 2/4 | 10/10 | 37 / 1 | 63.6 |
| 11 | 11 | Production router · private replay | 28/80 | 10/48 | 14/28 | 5/28 | 0/10 | 0/4 | 9/10 | reference | NR |

The router's role in the application is narrower than this pack: a low score here does not mean the application fails on these requests. Paraphrases avoid the obvious word on purpose; correlated FR/EN pairs and ten requests per category do not support a general ranking.

### Facade routing: harder tiers

Same eight categories on two frozen harder tiers of 96 cases (64 TEST). **Advanced**: implicit requests, lexical traps toward another category, near misses, informal or misspelt requests. **Complex**: multi-step requests scored on the first step, requests that depend on a previous exchange, compound refusals, goals without the action, genuine ambiguity. Cells are correct / all (test). [Tiers report](FACADE_ROUTING_TIERS_RESULTS_20261101.md).

**Leading on the complex tier (test)**: D3 mini · Q4 Metal (61/64 test).

| Rank complex | Model / runtime | Easy /80 (test /48) | Advanced /96 (test /64) | Complex /96 (test /64) | Median call ms (advanced) |
|---:|---|---:|---:|---:|---:|
| 1 | D3 mini · Q4 Metal | 79/80 (47/48) | 94/96 (62/64) | 93/96 (61/64) | 170.4 |
| 2 | D3 mini · Q8 Metal | 79/80 (47/48) | 94/96 (62/64) | 92/96 (60/64) | 161.6 |
| 3 | D3 flash · Q4 direct Metal | 79/80 (47/48) | 94/96 (62/64) | 91/96 (59/64) | 289.8 |
| 4 | D3 flash · 4-bit Uzu | 78/80 (46/48) | 92/96 (61/64) | 88/96 (56/64) | 110.6 |
| 5 | D3 nano · Q8 Metal | 75/80 (44/48) | 86/96 (59/64) | 79/96 (49/64) | 71.3 |
| 6 | D3 lite · Q8 Metal | 71/80 (40/48) | 71/96 (51/64) | 70/96 (41/64) | 38.9 |
| 7 | Vela 2.0 0.3B · macOS CPU | 64/80 (34/48) | 71/96 (53/64) | 49/96 (24/64) | 59.0 |
| 8 | Production router · private replay | 28/80 (10/48) | 24/96 (20/64) | 24/96 (17/64) | NR |

D3 rows on these tiers ran as Q8 GGUF on Metal (same weights as their CPU rows); Vela 2.0 0.3B ran on CPU. Latency scopes differ: Metal rows time the whole adapter call (loopback HTTP included), the CPU row its worker inference. The router reads only the latest request, as in the application; the complex tier's previous exchange is visible to the classifiers only.

### Passage relevance v2 (three levels)

The v1 relevance grade 1 ("concerns the topic") was undecidable for decoy passages, and one grade-2 role depended on another passage. [passage-relevance-v2](../datasets/passage-relevance-v2/README.md) keeps three levels (direct, partial, no usable evidence), 512 unique inputs (256 TEST). Always answering *no usable evidence* scores **384/512**: compare the macro accuracy. [Report](PASSAGE_RELEVANCE_V2_RESULTS_20261101.md).

| Model / runtime | Correct / 512 | TEST / 256 | Direct | Partial | No usable evidence | Macro accuracy |
|---|---:|---:|---:|---:|---:|---:|
| D3 mini · Q4 Metal | 406/512 | 200/256 | 112/112 | 16/16 | 278/384 | 90.8% |
| D3 mini · Q8 Metal | 406/512 | 200/256 | 112/112 | 16/16 | 278/384 | 90.8% |
| D3 flash · 4-bit Uzu | 386/512 | 189/256 | 110/112 | 16/16 | 260/384 | 88.6% |
| D3 flash · Q4 direct Metal | 381/512 | 187/256 | 110/112 | 16/16 | 255/384 | 88.2% |
| D3 nano · Q8 Metal | 371/512 | 181/256 | 97/112 | 16/16 | 258/384 | 84.6% |
| D3 lite · Q8 Metal | 338/512 | 168/256 | 100/112 | 5/16 | 233/384 | 60.4% |
| Vela 2.0 0.3B · macOS CPU | 113/512 | 59/256 | 55/112 | 3/16 | 55/384 | 27.4% |

### Facade routing: human confirmation

Can a model tell when to ask a human before acting? 90 FR/EN requests (62 TEST): 12 TEST hesitations between two categories, 12 irreversible or sensitive actions, 38 clear or out-of-scope requests. **Explicit**: a ninth *human confirmation* option. **Own confidence**: eight options, ask when the top-1 probability is below a threshold fixed on TRAIN + calibration. Counts are on TEST. [Report](FACADE_ROUTING_HITL_RESULTS_20261101.md).

| Model / runtime | Explicit: hesitations asked /12 | Explicit: irreversible asked /12 | Explicit: false alarms /38 | Confidence: detected /24 | Confidence: false alarms /38 | Confidence AUC |
|---|---:|---:|---:|---:|---:|---:|
| D3 flash · 4-bit Uzu | 0/12 | 11/12 | 2/38 | 22/24 | 10/38 | 0.90 |
| D3 flash · Q4 direct Metal | 0/12 | 11/12 | 0/38 | 22/24 | 13/38 | 0.88 |
| D3 mini · Q4 Metal | 0/12 | 9/12 | 1/38 | 19/24 | 12/38 | 0.83 |
| D3 mini · Q8 Metal | 0/12 | 9/12 | 0/38 | 18/24 | 12/38 | 0.83 |
| D3 nano · Q8 Metal | 0/12 | 5/12 | 2/38 | 18/24 | 14/38 | 0.81 |
| Vela 2.0 0.3B · macOS CPU | 0/12 | 1/12 | 4/38 | 20/24 | 22/38 | 0.72 |
| D3 lite · Q8 Metal | 0/12 | 0/12 | 1/38 | 19/24 | 17/38 | 0.74 |
| Production router · private replay | 0/12 | 0/12 | 0/38 | — | — | no probabilities |

The router has no confirmation path; it is shown for reference.

### Deployment variants: Q4 and Uzu

Same packs, four ways to serve a D3 decision model on the Mac: D3 mini (4.5B) as Q8 and Q4_K_M GGUF and D3 Flash (9B class) as Q4_K_M GGUF on the same llama.cpp Metal runtime, and Mirai's 4-bit D3 Flash pack on the Uzu engine. Cells: correct / all, median call time, sampled process RSS, one pass per case. Weights format, quantization and engine change together. [Report](DEPLOYMENT_VARIANTS_RESULTS_20261101.md).

| Pack | D3 mini · Q8 Metal | D3 mini · Q4 Metal | D3 flash · Q4 direct Metal | D3 flash · 4-bit Uzu |
|---|---:|---:|---:|---:|
| capability-choice-v1 | 192/192 · 325.2 ms · 5.4 GiB | 192/192 · 338.4 ms · 4.0 GiB | 192/192 · 584.4 ms · 6.7 GiB | 192/192 · 263.5 ms · 4.2 GiB |
| context-choice-v1 | 119/132 · 104.2 ms · 5.3 GiB | 117/132 · 107.5 ms · 3.9 GiB | 122/132 · 198.3 ms · 6.6 GiB | 118/132 · 73.8 ms · 4.2 GiB |
| facade-routing-advanced-v1 | 94/96 · 161.6 ms · 5.3 GiB | 94/96 · 170.4 ms · 3.9 GiB | 94/96 · 289.8 ms · 6.7 GiB | 92/96 · 110.6 ms · 4.2 GiB |
| facade-routing-complex-v1 | 92/96 · 163.9 ms · 5.3 GiB | 93/96 · 168.7 ms · 3.9 GiB | 91/96 · 293.9 ms · 6.7 GiB | 88/96 · 111.8 ms · 4.2 GiB |
| facade-routing-hitl-8opt-v1 | 83/90 · 161.6 ms · 5.3 GiB | 81/90 · 165.2 ms · 3.9 GiB | 86/90 · 290.5 ms · 6.7 GiB | 85/90 · 107.3 ms · 4.2 GiB |
| facade-routing-hitl-v1 | 71/90 · 167.6 ms · 5.3 GiB | 69/90 · 172.6 ms · 3.9 GiB | 73/90 · 299.6 ms · 6.7 GiB | 71/90 · 119.5 ms · 4.2 GiB |
| facade-routing-v1 | 79/80 · 161.4 ms · 5.3 GiB | 79/80 · 167.1 ms · 3.9 GiB | 79/80 · 292.2 ms · 6.7 GiB | 78/80 · 110.0 ms · 4.2 GiB |
| passage-relevance-v2 | 406/512 · 110.1 ms · 5.3 GiB | 406/512 · 111.6 ms · 4.0 GiB | 381/512 · 204.7 ms · 6.6 GiB | 386/512 · 85.3 ms · 4.2 GiB |
| physics-choice-v1 | 39/48 · 103.7 ms · 5.3 GiB | 36/48 · 111.1 ms · 3.9 GiB | 39/48 · 196.8 ms · 6.6 GiB | 40/48 · 72.9 ms · 4.2 GiB |

**Same model, two engines.** D3 Flash on Uzu (Mirai INT4) and on llama.cpp Metal (Q4_K_M) give the same answer on 1297/1336 cases over the nine packs (97.1%); the two 4-bit quantizations differ, so part of the gap is the weights, not the engine.

**Repeated timing.** After the main passes, three interleaved rounds on two packs: each round starts every variant once, in a rotated order, with a fresh server per pass. Median call time per round (min–max of the three round medians); answers are compared with the main pass.

| Pack | D3 mini · Q8 Metal | D3 mini · Q4 Metal | D3 flash · Q4 direct Metal | D3 flash · 4-bit Uzu |
|---|---:|---:|---:|---:|
| context-choice-v1 | 106.0 ms (105.9–106.3) · same answers every round | 108.5 ms (107.1–108.8) · same answers every round | 199.4 ms (197.4–199.9) · same answers every round | 75.0 ms (74.9–75.1) · same answers every round |
| facade-routing-v1 | 163.4 ms (162.6–164.2) · same answers every round | 166.7 ms (166.2–167.6) · same answers every round | 290.7 ms (289.0–291.3) · same answers every round | 111.2 ms (110.8–111.6) · same answers every round |

Uzu does not report its compute backend; Metal is requested, not observed. Its stock CLI fetches an online catalogue at start (no offline claim). Timing covers the loopback HTTP call of each engine's server on one Mac; it is not a throughput benchmark.

### Campaign latency and memory

Physical-call timings are kept separate from reused logical decisions; session RSS scopes differ from the historical context + tool sessions. NR means unreported. No controlled speed ranking is inferred.

| Model / runtime | Task | Timed calls | Median ms | p95 ms | Session RSS GiB |
|---|---|---:|---:|---:|---:|
| Clef Flash Q8 · direct Metal | capability | 192 | 616.9 | 953.5 | 10.60 |
| D3 flash · 4-bit Uzu | capability | 192 | 263.5 | 421.7 | 4.18 |
| D3 flash · Q4 direct Metal | capability | 192 | 584.4 | 893.0 | 6.74 |
| D3 Flash Q8 · gateway Metal | capability | 192 | 576.9 | 985.8 | 9.48 |
| D3 mini · macOS CPU | capability | 192 | 78,891.6 | 126,723.2 | 7.82 |
| D3 mini · Q4 Metal | capability | 192 | 338.4 | 523.9 | 4.01 |
| D3 mini · Q8 Metal | capability | 192 | 325.2 | 510.8 | 5.35 |
| D3 nano · macOS CPU | capability | 192 | 29,439.4 | 49,101.0 | 3.47 |
| D3 nano · Q8 Metal | capability | 192 | 141.0 | 210.6 | 2.80 |
| D3 lite · Q8 Metal | capability | 192 | 79.1 | 116.2 | 1.41 |
| D3 lite · macOS CPU | capability | 192 | 13,298.7 | 23,008.6 | 1.83 |
| Vela 2.0 0.3B · macOS CPU | capability | 192 | 344.5 | 528.2 | 1.26 |
| D3 Flash Q8 · direct Metal | passage_answerability | 72 | 278.2 | 748.7 | 9.45 |
| Clef Flash Q8 · direct Metal | passage_answerability | 72 | 282.3 | 864.7 | 10.40 |
| Clef Flash Q8 · direct Metal | passage_relevance | 264 | 202.1 | 376.2 | 10.40 |
| D3 Flash Q8 · direct Metal | passage_relevance | 264 | 200.0 | 294.1 | 9.45 |
| D3 Flash Q8 · direct Metal | passage_support | 392 | 200.8 | 293.7 | 9.45 |
| Clef Flash Q8 · direct Metal | passage_support | 392 | 201.2 | 374.1 | 10.40 |
| Clef Flash Q8 · direct Metal | physics | 48 | 196.7 | 211.7 | 9.55 |
| D3 flash · 4-bit Uzu | physics | 48 | 72.9 | 84.9 | 4.22 |
| D3 flash · Q4 direct Metal | physics | 48 | 196.8 | 204.6 | 6.64 |
| D3 Flash Q8 · direct Metal | physics | 48 | 193.7 | 202.1 | 9.36 |
| D3 mini · macOS CPU | physics | 48 | 16,936.2 | 21,044.9 | 7.34 |
| D3 mini · Q8 Metal | physics | 48 | 103.7 | 108.9 | 5.29 |
| D3 mini · Q4 Metal | physics | 48 | 111.1 | 118.1 | 3.94 |
| D3 nano · macOS CPU | physics | 48 | 7,766.9 | 12,607.7 | 3.19 |
| D3 nano · Q8 Metal | physics | 48 | 52.4 | 54.8 | 2.75 |
| Vela 2.0 0.3B · macOS CPU | physics | 48 | 169.9 | 211.0 | 1.16 |
| D3 lite · macOS CPU | physics | 48 | 3,073.8 | 3,981.3 | 1.56 |
| D3 lite · Q8 Metal | physics | 48 | 27.6 | 30.7 | 1.38 |

[Campaign summary CSV](leaderboard/campaigns.csv) and [task breakdown CSV](leaderboard/task-breakdown.csv) contain denominators, statuses and all exported groups. Ranking/nDCG, longer contexts and repeated timing retain their separate protocols in [other campaigns](leaderboard/other-benchmarks.md). Clef 27B and the six remaining original cohort candidates remain unrun on the new packs.

## Model quality

Each score is **correct / all cases** in its column, retaining failures in the denominator.
Tool is **agreement / 24 provisional proposals**, not routing accuracy. Full scored/valid counts and separate
`missing`, `unsupported`, `error`, `timeout`, and `abstain` counts are in the downloads.
Equal all-case totals share a competition rank; row order within a tie is alphabetical by observation ID.

<sub>**Rank all**: rank by correct answers over all 132 context cases (train + calibration + test); **Rank test**: rank over the 66 held-out test cases only, the better signal against tuning; **All / Test**: correct answers over those cases; **Text / Math / Chem**: correct answers within each domain (76 documentary, 28 mathematics, 28 chemistry cases); **Tool**: provisional agreements over 24 first-tool proposals, not routing accuracy. Size¹ and Runtime² are explained below the table.</sub>

**Leading on held-out test**: D3 27B · Q4 Metal (65/66); **leading over all 132 cases**: D3 27B · Q4 Metal (128/132). Larger native models lead; the gap to the best sub-1B CPU candidates is a few dozen cases on correlated FR/EN pairs.

| Rank all | Rank test | Model observation | Size¹ | Runtime² | All /132 | Test /66 | Text /76 | Math /28 | Chem /28 | Tool /24 |
|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 1 | D3 27B · Q4 Metal | 27B class | Metal | 128 | 65 | 73 | 28 | 27 | 24 |
| 2 | 4 | D3 flash · Q8 Metal | 9B class | Metal | 124 | 61 | 72 | 26 | 26 | 20 |
| 2 | 4 | D3 flash · Q8 direct Metal | 9B class | Metal-U | 124 | 61 | 72 | 26 | 26 | Not run |
| 2 | 4 | D3 flash · CPU | 8.393B backbone | CPU-H | 124 | 61 | 72 | 26 | 26 | 20 |
| 5 | 3 | Jev 1.13 · HTTP API | NR | API | 123 | 62 | 67 | 28 | 28 | 20 |
| 6 | 14 | D3 flash · Q4 Metal | 9B class | Metal | 122 | 59 | 71 | 24 | 27 | 21 |
| 6 | 14 | D3 flash · Q4 direct Metal | 9B class | Metal-U | 122 | 59 | 71 | 24 | 27 | Not run |
| 8 | 11 | D3 mini · CPU | 4.539B backbone | CPU-H | 119 | 60 | 71 | 24 | 24 | 20 |
| 8 | 11 | D3 mini · macOS CPU | 4.539B backbone | CPU-N | 119 | 60 | 71 | 24 | 24 | 20 |
| 8 | 11 | D3 mini · Q8 Metal | 4.539B backbone | Metal-U | 119 | 60 | 71 | 24 | 24 | Not run |
| 11 | 4 | D3 flash · 4-bit Uzu | 9B class | Uzu | 118 | 61 | 67 | 27 | 24 | Not run |
| 12 | 14 | D3 mini · Q4 Metal | 4.539B backbone | Metal-U | 117 | 59 | 71 | 22 | 24 | Not run |
| 12 | 4 | D3 nano · CPU | 2.213B backbone | CPU-H | 117 | 61 | 68 | 26 | 23 | 18 |
| 12 | 4 | D3 nano · macOS CPU | 2.213B backbone | CPU-N | 117 | 61 | 68 | 26 | 23 | 18 |
| 12 | 4 | D3 nano · Q8 Metal | 2.213B backbone | Metal-U | 117 | 61 | 68 | 26 | 23 | Not run |
| 12 | 2 | GLiClass v4 9B · BF16 MPS | 9B class | MPS | 117 | 63 | 70 | 24 | 23 | 20 |
| 17 | 14 | Clef Flash · Q8 direct Metal | 9B class | Metal-U | 110 | 59 | 63 | 25 | 22 | Not run |
| 18 | 18 | Vela 2.0 4B · CPU | 4.211B | CPU-H | 106 | 56 | 64 | 20 | 22 | 18 |
| 19 | 19 | Decision 2.0 Nox 4B · CPU | 4.208B | CPU-H | 103 | 55 | 54 | 25 | 24 | 18 |
| 20 | 19 | Liquid d1-3B · CPU | 3.123B | CPU-H | 101 | 55 | 60 | 21 | 20 | 16 |
| 21 | 21 | Noma · CPU | ~2.67B declared | CPU-H | 98 | 51 | 53 | 25 | 20 | 18 |
| 22 | 22 | D3 lite · CPU | 0.853B backbone | CPU-H | 95 | 50 | 64 | 15 | 16 | 19 |
| 23 | 23 | D3 lite · macOS CPU | 0.853B backbone | CPU-N | 94 | 49 | 63 | 15 | 16 | 19 |
| 23 | 23 | D3 lite · Q8 Metal | 0.853B backbone | Metal-U | 94 | 49 | 63 | 15 | 16 | Not run |
| 25 | 25 | Decision 2.0 Sol 2B · CPU | 2B class | CPU-H | 93 | 47 | 62 | 19 | 12 | 19 |
| 26 | 26 | Vela 2.0 0.8B · CPU | 0.755B declared | CPU-H | 79 | 45 | 56 | 11 | 12 | 14 |
| 27 | 27 | Decision 2.0 Eos 0.8B · CPU | 0.8B class | CPU-H | 77 | 40 | 55 | 12 | 10 | 19 |
| 27 | 27 | Decision 2.0 Eos 0.8B · Q8 Metal | 0.8B class | Metal | 77 | 40 | 55 | 12 | 10 | 19 |
| 29 | 30 | D3 edge · CPU | 0.594B backbone | CPU-H | 74 | 37 | 48 | 12 | 14 | 18 |
| 30 | 33 | Decision 2.0 Kai 0.6B · CPU | 0.6B class | CPU-H | 70 | 36 | 56 | 7 | 7 | 16 |
| 31 | 30 | Vela 2.0 0.3B · CPU | 0.309B declared | CPU-H | 65 | 37 | 52 | 4 | 9 | 18 |
| 31 | 30 | Vela 2.0 0.3B · macOS CPU | 0.309B declared | CPU-N | 65 | 37 | 52 | 4 | 9 | 18 |
| 33 | 29 | GLiNER2.5-multi-Decide · CPU | NR | CPU-H | 59 | 38 | 41 | 5 | 13 | 12 |
| 34 | 35 | Vela 3.0 fast · decision only · CPU | 0.380B decision backbone | CPU-N | 57 | 28 | 43 | 9 | 5 | 18 |
| 35 | 34 | Laya multilingual · CPU | 322M declared | CPU-H | 56 | 30 | 42 | 8 | 6 | 10 |
| 36 | 36 | Julia-1 · CPU | NR | CPU-H | 52 | 26 | 32 | 8 | 12 | 11 |
| 37 | 36 | Liquid d1-omni-600M · CPU | 600M class | CPU-H | 51 | 26 | 39 | 4 | 8 | 16 |
| 38 | 39 | Indecis · untrained open mode · CPU | NR | CPU-H | 44 | 22 | 32 | 2 | 10 | 11 |
| 39 | 38 | ModernJEV-Decide-Preview · CPU | NR | CPU-H | 42 | 23 | 23 | 13 | 6 | 8 |
| 40 | 40 | Muose-50M-Decision · CPU | 50M class | CPU-H | 41 | 21 | 30 | 6 | 5 | 10 |

¹ Sizes describe the observed checkpoint: exact tensor counts, nominal classes, and publisher declarations
are distinguished in [metadata](leaderboard/model-metadata.json). A backbone count may exclude a separate readout;
some counts include vision weights. **NR** means not reported in the selected public evidence, not zero.
The historical 27B D3 is neither an Ultra nor a Turbo observation; neither variant was evaluated here.

² CPU-H: historical Linux/WSL CPU runs (processor not identified here); API: remote service with unknown server hardware;
Metal: native llama.cpp on Apple M5 Pro; MPS: official PyTorch pipeline on Apple M5 Pro;
CPU-N: newer macOS CPU run; Metal-U: direct upstream native listener, separate from gateway-backed historical runs; Uzu: Mirai Uzu 0.6.15 release CLI, Metal requested but not reported. Runtime, readout, serializer, precision, and input lengths differ.
Not run in the tool column means no 24-case first-tool observation was published for that runtime; it is not zero accuracy. Later passage anchors reproduce the published D3 124/132 (test 61/66) and Clef 110/132 (test 59/66) totals; those repeated checks are not additional leaderboard models.

## Language and task complexity

D1/D2/D3 are authored context-task strata, **not predictions of difficulty or evidence that escalation helps**.
A correct choice also does not prove that a plugin was executed or a useful answer generated.

| Model observation | FR /66 | EN /66 | D1 /40 | D2 /40 | D3 /52 | Scored /132 | Tool valid /24 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D3 27B · Q4 Metal | 64 | 64 | 40 | 38 | 50 | 132 | 24 |
| D3 flash · Q8 Metal | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| D3 flash · Q8 direct Metal | 62 | 62 | 39 | 37 | 48 | 132 | Not run |
| D3 flash · CPU | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| Jev 1.13 · HTTP API | 62 | 61 | 36 | 38 | 49 | 132 | 24 |
| D3 flash · Q4 Metal | 62 | 60 | 39 | 37 | 46 | 132 | 24 |
| D3 flash · Q4 direct Metal | 62 | 60 | 39 | 37 | 46 | 132 | Not run |
| D3 mini · CPU | 60 | 59 | 40 | 38 | 41 | 132 | 24 |
| D3 mini · macOS CPU | 60 | 59 | 40 | 38 | 41 | 132 | 24 |
| D3 mini · Q8 Metal | 60 | 59 | 40 | 38 | 41 | 132 | Not run |
| D3 flash · 4-bit Uzu | 60 | 58 | 38 | 34 | 46 | 132 | Not run |
| D3 mini · Q4 Metal | 59 | 58 | 40 | 37 | 40 | 132 | Not run |
| D3 nano · CPU | 58 | 59 | 37 | 38 | 42 | 132 | 24 |
| D3 nano · macOS CPU | 58 | 59 | 37 | 38 | 42 | 132 | 24 |
| D3 nano · Q8 Metal | 58 | 59 | 37 | 38 | 42 | 132 | Not run |
| GLiClass v4 9B · BF16 MPS | 58 | 59 | 39 | 35 | 43 | 132 | 24 |
| Clef Flash · Q8 direct Metal | 55 | 55 | 36 | 36 | 38 | 132 | Not run |
| Vela 2.0 4B · CPU | 52 | 54 | 38 | 33 | 35 | 132 | 24 |
| Decision 2.0 Nox 4B · CPU | 50 | 53 | 32 | 31 | 40 | 132 | 24 |
| Liquid d1-3B · CPU | 50 | 51 | 29 | 30 | 42 | 132 | 24 |
| Noma · CPU | 46 | 52 | 35 | 26 | 37 | 132 | 24 |
| D3 lite · CPU | 45 | 50 | 32 | 31 | 32 | 132 | 24 |
| D3 lite · macOS CPU | 45 | 49 | 32 | 31 | 31 | 132 | 24 |
| D3 lite · Q8 Metal | 45 | 49 | 32 | 31 | 31 | 132 | Not run |
| Decision 2.0 Sol 2B · CPU | 46 | 47 | 32 | 28 | 33 | 132 | 24 |
| Vela 2.0 0.8B · CPU | 38 | 41 | 29 | 25 | 25 | 132 | 24 |
| Decision 2.0 Eos 0.8B · CPU | 39 | 38 | 30 | 22 | 25 | 132 | 24 |
| Decision 2.0 Eos 0.8B · Q8 Metal | 39 | 38 | 30 | 22 | 25 | 132 | 24 |
| D3 edge · CPU | 34 | 40 | 24 | 21 | 29 | 132 | 24 |
| Decision 2.0 Kai 0.6B · CPU | 34 | 36 | 27 | 17 | 26 | 132 | 24 |
| Vela 2.0 0.3B · CPU | 33 | 32 | 21 | 19 | 25 | 132 | 24 |
| Vela 2.0 0.3B · macOS CPU | 33 | 32 | 21 | 19 | 25 | 132 | 24 |
| GLiNER2.5-multi-Decide · CPU | 28 | 31 | 17 | 19 | 23 | 132 | 24 |
| Vela 3.0 fast · decision only · CPU | 25 | 32 | 20 | 14 | 23 | 132 | 24 |
| Laya multilingual · CPU | 32 | 24 | 17 | 13 | 26 | 132 | 24 |
| Julia-1 · CPU | 25 | 27 | 18 | 11 | 23 | 132 | 24 |
| Liquid d1-omni-600M · CPU | 19 | 32 | 13 | 15 | 23 | 132 | 24 |
| Indecis · untrained open mode · CPU | 21 | 23 | 12 | 11 | 21 | 132 | 24 |
| ModernJEV-Decide-Preview · CPU | 24 | 18 | 14 | 15 | 13 | 132 | 24 |
| Muose-50M-Decision · CPU | 19 | 22 | 14 | 13 | 14 | 132 | 24 |

## Speed and memory

These are **context-choice adapter observations**, not controlled cross-hardware speed rankings.
Latency includes the adapter's recorded boundary and successful calls only; cold initialization is separate.
Remote latency includes its network/API path; server memory is unknown. One-pass p95 is descriptive, not a tail guarantee.
[Repeated timing and stability](leaderboard/other-benchmarks.md#repeated-timing-and-stability) use separate campaigns.

**RSS and GPU allocations are different measurements: never add them.** Neither establishes total unified-memory use.
RSS below is worker peak for the context phase unless marked **S**, which is a sampled process-group peak over
the session specified in the CSV (historical context + tool, or a fresh context-only session). An allocation or peak is not a minimum-memory requirement; allow runtime/OS headroom.
Metal/MPS/Uzu observations used a 64 GiB Apple M5 Pro. CPU-H observations are not assumed to share controlled hardware. Repeated, interleaved timing of the deployment variants is in [Deployment variants](#deployment-variants-q4-and-uzu).

| Model observation | Runtime | Median ms | p95 ms | Timed /132 | Init ms | RSS GiB³ | GPU alloc GiB |
|---|---|---:|---:|---:|---:|---:|---:|
| D3 27B · Q4 Metal | Metal | 613.7 | 629.7 | 132 | NR | 18.81 S | NR |
| D3 flash · Q8 Metal | Metal | 194.3 | 200.4 | 132 | NR | 9.39 S | NR |
| D3 flash · Q8 direct Metal | Metal-U | 194.6 | 200.6 | 132 | NR | 9.36 S | NR |
| D3 flash · CPU | CPU-H | 10,080.2 | 15,009.8 | 132 | 24,467.3 | 13.75 | NR |
| Jev 1.13 · HTTP API | API | 280.5 | 323.3 | 132 | NR | NR | NR |
| D3 flash · Q4 Metal | Metal | 197.9 | 203.8 | 132 | NR | 6.66 S | NR |
| D3 flash · Q4 direct Metal | Metal-U | 198.3 | 204.0 | 132 | NR | 6.64 S | NR |
| D3 mini · CPU | CPU-H | 5,971.7 | 8,291.9 | 132 | 16,466.7 | 7.55 | NR |
| D3 mini · macOS CPU | CPU-N | 17,251.7 | 20,198.2 | 132 | 12,279.6 | 7.35 | NR |
| D3 mini · Q8 Metal | Metal-U | 104.2 | 108.6 | 132 | NR | 5.29 S | NR |
| D3 flash · 4-bit Uzu | Uzu | 73.8 | 86.5 | 132 | NR | 4.22 S | NR |
| D3 mini · Q4 Metal | Metal-U | 107.5 | 111.9 | 132 | NR | 3.94 S | NR |
| D3 nano · CPU | CPU-H | 2,083.7 | 2,453.4 | 132 | 12,354.2 | 3.39 | NR |
| D3 nano · macOS CPU | CPU-N | 7,272.1 | 8,813.9 | 132 | 9,250.4 | 3.20 | NR |
| D3 nano · Q8 Metal | Metal-U | 52.0 | 54.0 | 132 | NR | 2.75 S | NR |
| GLiClass v4 9B · BF16 MPS | MPS | 326.5 | 615.5 | 132 | 13,465.5 | 1.14 | 16.75 |
| Clef Flash · Q8 direct Metal | Metal-U | 196.8 | 219.8 | 132 | NR | 9.56 S | NR |
| Vela 2.0 4B · CPU | CPU-H | 7,948.5 | 9,042.8 | 132 | 24,298.6 | 17.99 | NR |
| Decision 2.0 Nox 4B · CPU | CPU-H | 5,919.6 | 7,373.8 | 132 | 25,886.0 | 20.66 | NR |
| Liquid d1-3B · CPU | CPU-H | 8,079.9 | 10,717.1 | 132 | 12,649.6 | 17.80 | NR |
| Noma · CPU | CPU-H | 4,206.3 | 5,157.5 | 132 | 12,309.9 | 4.82 | NR |
| D3 lite · CPU | CPU-H | 1,002.3 | 1,349.6 | 132 | 11,239.6 | 1.80 | NR |
| D3 lite · macOS CPU | CPU-N | 3,195.5 | 3,887.9 | 132 | 6,597.5 | 1.55 | NR |
| D3 lite · Q8 Metal | Metal-U | 28.6 | 30.8 | 132 | NR | 1.38 S | NR |
| Decision 2.0 Sol 2B · CPU | CPU-H | 3,471.9 | 6,403.8 | 132 | 28,703.3 | 8.32 | NR |
| Vela 2.0 0.8B · CPU | CPU-H | 1,573.4 | 1,849.3 | 132 | 11,398.0 | 5.13 | NR |
| Decision 2.0 Eos 0.8B · CPU | CPU-H | 1,122.6 | 1,379.7 | 132 | 13,056.8 | 3.44 | NR |
| Decision 2.0 Eos 0.8B · Q8 Metal | Metal | 28.5 | 37.1 | 132 | NR | 1.37 S | NR |
| D3 edge · CPU | CPU-H | 438.4 | 564.7 | 132 | 8,443.2 | 1.32 | NR |
| Decision 2.0 Kai 0.6B · CPU | CPU-H | 1,220.8 | 2,227.8 | 132 | 19,524.6 | 3.01 | NR |
| Vela 2.0 0.3B · CPU | CPU-H | 171.2 | 252.0 | 132 | 12,767.4 | 1.17 | NR |
| Vela 2.0 0.3B · macOS CPU | CPU-N | 154.0 | 195.8 | 132 | 5,922.9 | 1.18 | NR |
| GLiNER2.5-multi-Decide · CPU | CPU-H | 234.9 | 401.0 | 132 | 13,096.7 | 2.82 | NR |
| Vela 3.0 fast · decision only · CPU | CPU-N | 80.5 | 116.4 | 132 | 8,339.1 | 3.16 | NR |
| Laya multilingual · CPU | CPU-H | 168.9 | 219.7 | 132 | 11,186.0 | 2.27 | NR |
| Julia-1 · CPU | CPU-H | 59.0 | 83.2 | 132 | 14,164.9 | 0.97 | NR |
| Liquid d1-omni-600M · CPU | CPU-H | 438.4 | 648.0 | 132 | 9,523.5 | 1.67 | NR |
| Indecis · untrained open mode · CPU | CPU-H | 34.8 | 43.0 | 132 | 1,160.5 | 1.10 | NR |
| ModernJEV-Decide-Preview · CPU | CPU-H | 668.1 | 1,142.4 | 132 | 8,849.6 | 0.86 | NR |
| Muose-50M-Decision · CPU | CPU-H | 308.0 | 748.1 | 132 | 3,113.4 | 0.61 | NR |

³ Worker RSS reporting coverage and the exact measurement scope are retained in the CSV/JSON.
NR means unreported; GPU NR must not be read as zero. Sizes, weight-file sizes, RSS, and GPU allocation are different quantities.

## Other evaluated protocols

The historical tables below are included from the tracked [other-campaign guide](leaderboard/other-benchmarks.md). Their original denominators, failure counts and timing scopes are preserved. They are not combined with the context or rotation-zero evidence rankings. Structured summary metrics and source hashes are also included under `other_campaigns` in the JSON download; detailed cross-groups, rotations and per-case rows remain in the source exports.

### Passage ranking and evidence

The evaluated test subset of the
[passage dataset](../datasets/passage-evidence-v1/README.md) contains eight
scenario families, eight language directions, two document views, and pools of
four passages. The comparison below uses all **512 test variants: four equally
weighted rotations of the initial 128 cases**. Rotations and translations are
correlated variants, not independent samples.

Higher is better. nDCG measures graded ranking quality; MRR measures the rank of
the first relevant passage; recall measures how much relevant evidence survives
the cutoff. Scores retain penalties for missing/error outcomes on eligible cases.

| Method | nDCG@1 | nDCG@3 | MRR@4 | Recall@1 | Recall@3 |
|---|---:|---:|---:|---:|---:|
| BGE v2-m3 INT8 CPU | 0.922 | 0.934 | 0.926 | 0.779 | 0.923 |
| D3-lite + BGE tie-break | 0.922 | 0.935 | 0.926 | 0.779 | 0.923 |
| JeV 1.14.0 + BGE tie-break | 0.911 | 0.931 | 0.917 | 0.769 | 0.923 |
| JeV 1.14.0 classes alone | 0.840 | 0.878 | 0.879 | 0.663 | 0.921 |
| D3-lite classes alone | 0.701 | 0.808 | 0.766 | 0.510 | 0.892 |
| Input order | 0.442 | 0.635 | 0.579 | 0.250 | 0.750 |
| Reverse input order | 0.442 | 0.635 | 0.579 | 0.250 | 0.750 |

Every row covers **512/512 pools**. For each nDCG metric the denominator is
**480 defined / 480 eligible / 512 total**; for MRR and recall it is
**416 / 416 / 512**. Pools with no eligible reference are excluded by the metric
definition, not treated as successful predictions.

The original rotation-0 nDCG@1 was 0.989 for both D3-lite and JeV. Across the four
rotations it becomes 0.701 and 0.840 respectively. Use the balanced table above
for comparisons. The detailed reports retain every rotation, language direction,
scenario, and document view.

Evidence retention asks whether the selected passages contain a complete
sufficient evidence set, or both the supporting and refuting evidence for a
conflicting claim. Each cell is successful / eligible pools.

| Method | Complete sufficient set @3 | Supporting + refuting pair @3 |
|---|---:|---:|
| BGE CPU | 288/352 | 64/64 |
| D3-lite + BGE tie-break | 288/352 | 64/64 |
| JeV 1.14.0 + BGE tie-break | 288/352 | 64/64 |
| JeV 1.14.0 classes alone | 287/352 | 64/64 |
| D3-lite classes alone | 281/352 | 60/64 |
| Input order | 248/352 | 32/64 |
| Reverse input order | 248/352 | 32/64 |

Ranking, evidence retention, and categorical decision accuracy are different
measures. This pilot does not evaluate initial document retrieval or final answer
generation. BGE's CPU binary is identified by hash; its exact source revision
was not established. D3-lite used CPU BF16 backbone weights with an FP32 readout.
JeV 1.14.0 is a remote API observation, distinct from JeV 1.13.0 in the historical
context-choice and timing campaigns.

Sources: [balanced D3/BGE report](evidence/passage-order-control-20261015/report.md)
and [JSON](evidence/passage-order-control-20261015/analysis.json);
[JeV report](evidence/passage-jev-20261015/report.md)
and [JSON](evidence/passage-jev-20261015/analysis.json).

### Passage latency and memory

All times below are seconds per four-passage pool, median / p95, with **512 pool
observations or projections per row**. The measurement boundary is explicit.

| Operation | Median s | p95 s | Observation boundary |
|---|---:|---:|---|
| BGE CPU ranking | 0.236 | 0.908 | Actual native CPU call per pool |
| D3-lite, four relevance choices | 4.411 | 8.446 | Projection from existing measured calls; no new D3 calls for rotations |
| D3-lite + BGE tie-break | 4.654 | 9.354 | Sequential sum projection; no integrated pipeline measured |
| JeV 1.14.0, four relevance choices | 1.058 | 1.187 | Replayed client-time projection; no new HTTP calls for rotations |
| JeV 1.14.0 + BGE tie-break | 1.303 | 1.957 | Sequential sum projection; no integrated pipeline measured |

JeV HTTP time includes network and server time; server inference time and RAM were
unobserved. D3's initial worker sampled maximum RSS was **2,267.473 MiB**; BGE's
process and container peaks have different scopes and remain separate in the
[initial JSON](evidence/passage-cpu-20261015/analysis.json). These observations
do not establish a single memory requirement for the combined pipeline.

For support and answerability, the initial D3 report reconstructs median / p95
costs of **8.330 / 9.605 s** and **1.476 / 5.203 s**, respectively, across 128 pools.
These are additional operations, not included in ranking latency above.

### Longer contexts

The length campaign uses **378 planned variants from nine independent families**:
seven length targets, documentary/mathematics/chemistry contexts, French/English,
and three evidence positions. Targets count **Julia reference tokens**, not a
shared native token budget. They do not establish the maximum supported context
length of each model.

| Candidate | Correct / scored / planned | Scored coverage | Unsupported | Errors | Main unscored causes |
|---|---:|---:|---:|---:|---|
| JeV API | 305/354/378 | 93.7% | 24 | 0 | 24 unattainable targets |
| Julia CPU | 114/300/378 | 79.4% | 24 | 54 | 24 unattainable targets; 54 memory-guard errors |
| Indecis CPU | 81/300/378 | 79.4% | 78 | 0 | 24 unattainable targets; 54 native overflows |
| GLiNER CPU | 72/192/378 | 50.8% | 24 | 162 | 24 unattainable targets; 162 memory-guard errors |

There were no `timeout`, `missing`, or `abstain` outcomes in this campaign.
Unscored variants remain visible; a guard or unsupported length is not a semantic
model error. Each cell below is **correct / scored / planned**.

| Target reference tokens | Julia | GLiNER | JeV | Indecis |
|---:|---:|---:|---:|---:|
| 100 | 13/30/54 | 12/30/54 | 30/30/54 | 14/30/54 |
| 250 | 23/54/54 | 21/54/54 | 46/54/54 | 15/54/54 |
| 500 | 17/54/54 | 18/54/54 | 44/54/54 | 14/54/54 |
| 1,000 | 17/54/54 | 21/54/54 | 47/54/54 | 13/54/54 |
| 2,000 | 22/54/54 | 0/0/54 | 48/54/54 | 16/54/54 |
| 4,000 | 22/54/54 | 0/0/54 | 46/54/54 | 9/54/54 |
| 8,000 | 0/0/54 | 0/0/54 | 44/54/54 | 0/0/54 |

An entry such as `0/0/54` means no scored observation, not measured 0% accuracy.

| Candidate | Adapter median / p95 ms for OK calls (n) | Worker maximum RSS MiB (n) |
|---|---:|---:|
| Julia CPU | 676.7 / 5,965.3 (300) | 1,765.3 (300) |
| GLiNER CPU | 1,183.1 / 5,979.5 (192) | 2,885.5 (192) |
| JeV API | 300.9 / 375.4 (354) | Unobserved (0) |
| Indecis CPU | 257.6 / 978.0 (300) | 1,241.2 (354) |

The RSS observation count can differ from the OK-call count. EOS, Noma, and Laya
were not measured in these length archives. See the
[full length report](evidence/length-comparison-20261004/report.md) for all
domain, language, and evidence-position intersections, and its
[JSON](evidence/length-comparison-20261004/analysis.json) for runtime provenance
and status-specific timing distributions.

### Repeated timing and stability

These smaller archives separate initialization, cold, warmup, and measured calls.
The table shows measured **adapter** time, not interchangeable GPU/kernel time.
Repeated calls do not increase the number of independent case families.

Context choice: **18 cases, nine families, three launches, three measured passes
per launch**. Each candidate has 162 measured calls; all 162 returned OK outputs.

| Candidate | Correct / scored calls | Correct per 18-case pass | Cases with variable choice | Adapter median / p95 ms | Worker max RSS MiB |
|---|---:|---:|---:|---:|---:|
| JeV 1.13.0 API | 157/162 | 17–18/18 | 3/18 | 290.563 / 332.005 | Unobserved |
| Julia CPU | 54/162 | 6/18 | 0/18 | 64.273 / 89.093 | 1,015.707 |
| GLiNER CPU | 54/162 | 6/18 | 0/18 | 194.885 / 251.455 | 2,885.773 |
| Indecis CPU | 54/162 | 6/18 | 0/18 | 34.125 / 44.321 | 960.746 |

Documentary routing: **14 cases, seven families, three launches, ten measured
passes per launch**. Each candidate has 420 measured calls; all returned OK.

| Candidate | Correct / scored calls | Correct per 14-case pass | Cases with variable choice | Adapter median / p95 ms | Worker max RSS MiB |
|---|---:|---:|---:|---:|---:|
| Julia CPU | 300/420 | 10/14 | 0/14 | 82.958 / 112.824 | 999.895 |
| MCPs documentary function | 420/420 | 14/14 | 0/14 | 9.645 / 11.975 | Unobserved |

MCPs is a deterministic application function, not a competing language model;
its execution boundary differs from Julia's. None of these observations qualifies
the full application. EOS, Noma, and Laya were not measured in these archives.
Initialization, cold/warmup counts, model revisions, runtime versions, and separate
decision/inference/HTTP timings are in the
[repeated timing report](evidence/timing-comparison-20261004/report.md)
and [JSON](evidence/timing-comparison-20261004/analysis.json).

### Initial documentary routing pilot

The earlier [14-case pilot](JULIA_RESULTS.md) observed MCPs **14/14**, Julia
**10/14**, and Julia with reversed option order **9/14**, each fully scored.
Reversing the options changed **5/14** Julia decisions. These are seven correlated
French/English families and inherited train/calibration/test labels, not a balanced
held-out leaderboard. Its source traces and all later repeated measurements remain
separate historical observations.

## Every task and downloadable data

- [Model summary CSV](leaderboard/models.csv): all 40 context observations, model sizes, runtimes, quality, latency, and separate resource measurements.
- [Coverage CSV](leaderboard/coverage.csv) and [coverage JSON](leaderboard/coverage.json): every observation × task cell, explicit execution and review status, protocol denominator, source, and unobserved fields.
- [Campaign summary CSV](leaderboard/campaigns.csv): independent capability, physics and passage rankings, coverage, test scores, class macro scores and measured resource scopes.
- [Task breakdown CSV](leaderboard/task-breakdown.csv): exported context task types/subtypes, domains, languages, splits and difficulty; tool-choice subgroups; plus capability, physics and passage groups, with task-specific denominators.
- [Full structured results](leaderboard/results.json): identities, revisions, model/runtime settings, counts, statuses, all groups, source seals, and input-file SHA-256 hashes.
- [Other benchmark results](leaderboard/other-benchmarks.md): full passage, support, answerability, length, repeated timing, and legacy pilot tables. These use different corpora/metrics and are not merged into one accuracy score.

In the task CSV, `numerator` is correct choices or provisional agreement as named by `metric`.
`scored_or_valid` and `total` retain coverage; blank subgroup status cells mean the source did not export those statuses.
FR/EN pairs, passage-order variants, and repeated measurements remain correlated rather than independent evidence.

## Provenance and reproduction

The join reads only explicitly tracked public sources, validates the frozen historical composer and its hashes,
checks duplicated observations and denominators, and binds separate memory observations to model identities/seals.
It does not verify unavailable raw archives or confer human reference approval. Original campaign exports remain unchanged.

```bash
python3 scripts/build-full-results.py --check
# After an intentional, reviewed public evidence/metadata update:
python3 scripts/build-full-results.py --write
```

See the [protocol](PROTOCOL.md), [historical campaign archive](RESULTS_INDEX.md), and
[planned intent, MCP-tool, and model-routing experiment](INTENT_AND_MODEL_ROUTING.md).
