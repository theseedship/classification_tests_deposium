# Campaign status and next steps

**Checkpoint: 30 October 2026.** This is the current work-order page; the
[public issue roadmap](https://github.com/theseedship/classification_tests_deposium/issues/19)
tracks contributions. Use [Results and coverage](RESULTS.md#coverage-overview)
for measured outcomes and untested cells, and the [protocol](PROTOCOL.md) for
method. Dated campaign plans/reports remain evidence for their own revisions.

References and translations are agent-authored, **pending human review**.
Offline checks, runtime preparation, real inference, application integration
and end-to-end quality are distinct qualifications.

## Work order and exit criteria

The documentation/coverage consolidation and contributor guide were delivered
by merged [PR #24](https://github.com/theseedship/classification_tests_deposium/pull/24).
The initial #9 contract has a recorded offline fixture, ready as a foundation
for #10/#11; no real model output path is qualified. Merged
[PR #25](https://github.com/theseedship/classification_tests_deposium/pull/25)
prepared the human-review packet, with **zero actual human judgments** so far.
See [who fills the forms and when](REFERENCE_REVIEW_PILOT.md#first-review-who-does-what-and-when).
Human assessment remains #8 and can proceed independently of the next offline
engineering work. There is no need to rerun the historical leaderboard first.
Model grading itself is automatic: the [reference-grid check](PROTOCOL.md#automatic-grading-and-reference-checks)
and bounded agent reviews strengthen the checks without assigning expert forms
to the maintainer. Human review stays a separate, explicitly pending audit.
The initial #10 [discovery/selection fixture](../datasets/tool-discovery-v1/README.md)
was delivered by merged PR #29. The initial #11
[argument-execution fixture](../datasets/tool-arguments-v1/README.md) was delivered
by merged PR #30: four training cases with actual lookup/sum receipts. The #12
[episode fixture](../datasets/tool-episodes-v1/README.md) adds 14 training controls
with actual feedback, including four successful task results and ten justified
stops/clarifications. These remain synthetic harness checks with zero real-model
results. Next, qualify one candidate's output path and a small bounded canary
before broader comparisons; freeze fresh held-out families before a campaign.

The [local generated-JSON path](LOCAL_TOOL_POLICY_V1.md) and
[fixed supervisor](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md) are now
prepared with a frozen ten-case TRAIN canary. Offline parser, lifecycle and
execution controls are implemented; actual Qwen runtime/model qualification
remains `not_run` with zero real-model cases. The historical 27B remains
deferred. No model loading, downloading or paid API is implied by this checkpoint.

| Work | Prerequisite and next action | Exit criterion |
|---|---|---|
| [#7 — Contributor entry point](https://github.com/theseedship/classification_tests_deposium/issues/7) **delivered** | Use the [offline quickstart](../CONTRIBUTING.md), merged with #24; no weights, APIs or application required. | Copyable commands, expected signals, platform/skip limits and staged-public-content checks are documented. |
| [#8 — Human reference review](https://github.com/theseedship/classification_tests_deposium/issues/8) **packet ready; humans pending** | Use the [prepared pilot](REFERENCE_REVIEW_PILOT.md) and agree a small assignment with a human reviewer. Physics laws/units, FR/EN, evidence labels/conflicts and both passage views are available for incremental review. No reviewer is assigned by this repository. | Real human annotations, disagreements and adjudication remain outstanding; record actual scope and exposure. Preparation alone is not completed human review. |
| [#9 — New contract and fresh scenarios](https://github.com/theseedship/classification_tests_deposium/issues/9) **initial contribution delivered** | The [bounded proposal contract](TOOL_PLAN_CONTRACT_V1.md), runtime output audit and [12-family proposal](../datasets/tool-plan-pilot-v1/README.md) provide the initial offline slice. Only one train family is materialized (two FR/EN cases); no held-out cases or model campaigns. | Recorded shared-engine success and empty/wrong/malformed/overcalling/premature-success controls are implemented. v1 choice datasets remain unchanged. Review and freeze any expansion before inference; a recorded control is not a model result. |
| [#10 — Discovery and tool selection](https://github.com/theseedship/classification_tests_deposium/issues/10) **initial fixture delivered** | The [contract/metrics](TOOL_DISCOVERY_CONTRACT_V1.md) and 12-case FR/EN pack are merged. Distinguish plugin, capability and tool IDs, shortlist recall and final sufficient/minimal sets. | Recorded controls cover alternatives and semantic nonselection. No real model output path or tool execution is qualified. |
| [#11 — Arguments and artifact dependencies](https://github.com/theseedship/classification_tests_deposium/issues/11) **initial execution fixture delivered** | Use the [four-case training fixture](../datasets/tool-arguments-v1/README.md) and [bounded contract](TOOL_ARGUMENTS_CONTRACT_V1.md), which bind a proposal to an actual lookup artifact before running a guarded sum. | Actual receipts, independent argument/scope/unit/binding guards and separate stage metrics are implemented; zero real model or live application qualification. |
| [#12 — Bounded tool episodes](https://github.com/theseedship/classification_tests_deposium/issues/12) **initial execution fixture delivered** | Use the [14-case training pack](../datasets/tool-episodes-v1/README.md) and [contract](TOOL_EPISODES_CONTRACT_V1.md): actual observations, bounded retry/step/call/time checks and sealed traces. | Separate selection, arguments, dependencies, execution, result and stopping metrics. Scripted positive handling is 14/14; successful task results are 4/14 overall, 4/4 eligible. No real-model or live application qualification. |
| [#13 — Passage order and evidence retention](https://github.com/theseedship/classification_tests_deposium/issues/13) **offline extension delivered** | Use the [frozen plan and analyzer](PASSAGE_ORDER_RETENTION_V1.md): four existing rotations, both views, exact physical-call reuse and sealed-source lineage checks. | Shared order/retention metrics retain all failure denominators: 5,632 logical test decisions / 920 distinct inputs. Rotation-zero alone leaves 192 additional inputs unobserved. A future model campaign needs separately calibrated resource/time budgets; no new inference is established. |
| [#14 — Remaining frozen-cohort runtimes](https://github.com/theseedship/classification_tests_deposium/issues/14) **27B offline readiness; execution deferred** | Use the [candidate-bound 27B protocol](D3_27B_CAPABILITY_PROTOCOL_20261030.md) and unchanged [cohort order](CAPABILITY_CAMPAIGN_PLAN.md). Actual preparation and a sealed twelve-call canary must precede any full phase. | Explicit 24 GiB RSS / 8 GiB reserve, exact all-input preparation and measured frozen time budgets; zero cases scored so far. Model work remains deferred, and no remaining-cohort runtime is qualified by the offline controls. |
| [#15 — Clef 27B envelope](https://github.com/theseedship/classification_tests_deposium/issues/15) | Prepare a dedicated native identity and resource envelope; the Flash launcher is not a generic large-model override. | Offline refusal controls and actual supported native choices; 24 GiB RSS plus 8 GiB reserve admission guard before any inference. Clef 27B and historical D3 27B remain distinct. |
| [#21 — Jev 1.14 full-suite qualification](https://github.com/theseedship/classification_tests_deposium/issues/21) | Prepare coverage plan, current provider identity/limits/terms/price, call bounds and strict fake-transport controls. Paid phases require explicit maintainer authorization. | Every applicable current task has a declared outcome, failure/unsupported coverage and consolidated public exports; historical Jev 1.13 and partial Jev 1.14 evidence are not reused as full-suite results. |
| [#22 — D3 Ultra full-suite qualification](https://github.com/theseedship/classification_tests_deposium/issues/22) | Prepare actual checkpoint, output support, native helper and resource admission before large assets. Pair applicable inputs with #21; do not infer local feasibility from a nominal model size. | Qualified runtime and task-specific archives/exports, with quantizations kept as separate identities; historical D3 27B is not relabelled as Ultra. |
| [#16 — Empirical small/large allocation](https://github.com/theseedship/classification_tests_deposium/issues/16) **later** | Design can start; measured allocation needs fresh held-out paired outcomes from qualified small/large candidates. | Both-success, large-only, neither and small-only outcomes plus always-small/always-large cost controls; authored difficulty/confidence is not ground truth. |
| [#17 — Pinned application replay](https://github.com/theseedship/classification_tests_deposium/issues/17) **later** | Design can start; implementation requires a maintainer-supplied real harness. Record pinned source/runtime and deterministic guard boundaries. | Actual invocation receipts and public synthetic fixtures; copied routing or a registry alone cannot qualify integration. |
| [#18 — Answers and citations](https://github.com/theseedship/classification_tests_deposium/issues/18) **later** | Needs reviewed facts/acceptable answers; #8, #12 and #17 support the later product evaluation. | Separate retrieval availability, factual correctness, claim/source support and abstention; negative controls include irrelevant citations, wrong numbers, contradictions and absent evidence. |

**Dependency path:** #9 → #10/#11 → #12. Reference review (#8) and passage
robustness (#13) can proceed alongside it. Runtime and full-suite preparation
(#14/#15/#21/#22) is independent; qualified current v1 tasks can run without
waiting for all future tool-harness issues. None of these campaigns may claim
open-ended tool execution before its contract and evaluator exist. Added
candidates do not silently reorder the original seven-candidate cohort.

## Measured checkpoint and remaining gaps

The [generated coverage matrix](RESULTS.md#coverage-overview) is the canonical
model/task inventory. D3 Flash and Clef Flash have context, capability, physics
and matched passage-evidence observations; the capability pack reaches a
four-proposal ceiling. Their newer passage support/answerability observations
cover rotation zero, while historical ranking includes different order controls.
Those are separate evaluations, rather than proof of evidence-order robustness.

Six original-cohort candidates remain unrun on the capability pack: historical
D3 27B Q4, GLiClass 9B, D3 Mini, Nano, Lite and Vela 2.0 0.3B. Clef 27B, D3 Ultra
and the hosted Turbo path remain unexecuted here. A publisher score, runtime
installation or successful canary is not a benchmark result.

The [harness coverage table](RESULTS.md#harness-coverage) separates existing
closed-choice model observations from scripted discovery, executable arguments
and bounded feedback fixtures. Real-model output generation on those new
contracts, application replay, allocation and end-to-end answer quality remain
unqualified; more closed-choice runs alone cannot qualify them.

## Validation matrix

The rows below record the **existing checkpoint**, not a fresh certification of
every subsequent commit. New changes must report their own checks in their PR.
No model inference or paid API was part of the offline checks.

| Scope | Recorded result | Interpretation |
|---|---|---|
| Linux / Python 3.12, prepared local JSON policy and the shared core | 1039 tests: 1008 passed, 31 optional skips, no failures or errors. Executed without network in the local validation image, with a read-only source mount and temporary results storage. | Current offline implementation check; skipped optional integrations remain unqualified. It is not model inference or human review. |
| Historical frozen campaign code, 29 October 2026 | 817 tests: 786 passed, 31 optional skips, no failures. | Historical code checkpoint only; **not the current checkout's global PASS**. |
| macOS / Python 3.13, core checks | Registry, context/physics cases, capability/passage corpora and generated result views validated at the prior checkpoint. | Data/contract/export checks, not inference or human review. |
| macOS / Python 3.13, targeted native/campaign/scoring suite | 182 tests: 180 passed, two optional skips. | Targeted implementation verification only. |
| macOS / Python 3.13, full suite | 858 tests: 62 failures, six errors, 75 skips. Compared public base `8b164b8`: 828 tests, same 62 failure/six error identifiers, 74 skips. | Known baseline limitations; **not a full macOS PASS**, and skipped integrations remain unqualified. |

Use [Contributing](../CONTRIBUTING.md) for reproducible core commands and public
content checks. A zero scored count, empty assertion or skipped dependency
never establishes a passing evaluation.

## Resume a campaign

Read the relevant dataset card, [protocol](PROTOCOL.md), frozen plan and dated
campaign report. Recheck actual model, tokenizer, binary/helper revisions,
hashes, input limits and resource admission. Historical WSL/CPU locks do not
qualify a new macOS runtime; campaign guards are not universal RAM requirements.

Preserve completed observations and their original pre-inference plans,
including the [Clef Flash plan](../plans/clef-native-v1.json). New dataset/runtime
pairs need new archives and fresh anchors under their declared protocol. Keep
partial runs; a rescore is derived work and creates neither inference nor timing.
New references/scenarios require a separately reviewed version with fresh
families, rather than rewriting exposed v1 cases after seeing errors.

Weights, installations, budgets and raw private archives stay outside Git.
A public clone contains source, synthetic fixtures, protocols and aggregates;
it does not restore private local assets. The
[dated priorities](BENCHMARK_PRIORITIES_20261029.md) explain the completed
checkpoint, and the [campaign archive](RESULTS_INDEX.md) preserves its evidence.
