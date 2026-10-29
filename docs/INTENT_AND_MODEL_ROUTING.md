# Intent, tool sets, and model routing: proposed experiment

**Status: staged experiment, not an implemented product router or a measured
campaign.** The [first complementary pack](../datasets/capability-choice-v1/README.md)
now provides 192 runnable closed choices in 48 synthetic FR/EN scenario families,
using the existing engine and adapters. It covers capability/tool-set proposals,
arguments/dependencies and next steps after fixed observations, with 8/32-card
catalogues. No real model has run on this pack. Free-form discovery/selection,
full execution loops and empirical small/large model allocation remain future
harness stages. Choosing a model is a separate axis from choosing tools.

## What the existing results establish

| Public evidence | Actual task | Missing evidence for this feature |
|---|---|---|
| [Context choice](../datasets/context-choice-v1/README.md) | 132 closed choices, including 76 documentary cases distinguishing inventory, stored summaries, retrieved answers, or insufficient information | Open-ended intent detection, a difficulty predictor, and execution of a selected workflow |
| [First tool choice](../datasets/mastra-read-pilot-v0/README.md) | 24 synthetic search / statistics / fallback proposals; provisional agreement only | Plugin discovery, argument resolution, tool execution, and validated routing accuracy |
| [Tool-selection review](../datasets/tool-selection-review-v0/README.md) | 16 review cases, including two blocked contract gaps; no runner or scorer | A runnable plugin-selection benchmark or an evaluated application integration |
| [Capability choices v1](../datasets/capability-choice-v1/README.md) | 192 frozen closed choices, 48 families; compact/expanded synthetic catalogues | Real model results, free-form plans, executable arguments and a complete feedback loop |

The context pack's D1/D2/D3 values are authored annotations: explicit requests,
combined constraints, and dependencies or contextual references, fixed before inference.
They are not predictions of model difficulty or proof that a small model needs escalation.
Short requests can require dependent operations; long requests can contain one simple lookup.

## Separate capability selection, execution, and model choice

Use a generic capability taxonomy, with separate outputs and metrics:

1. **Discovery:** find relevant capabilities among many irrelevant or similarly
   named options; record shortlist recall separately from the final selection.
2. **Selection and plan:** choose one tool or an allowed set, validate argument
   schemas, and express dependencies. Accept reviewed alternative valid plans.
3. **Execution loop:** execute a bounded step, inspect its actual observation,
   re-evaluate, then choose another tool, clarify, stop, or report failure.
   A retry needs a declared policy and remaining call/time/cost budget.
4. **Difficulty and model assignment:** estimate whether a specified small model
   meets quality/budget criteria, then choose small, large, or fallback under
   deterministic admission checks. Keep this independent of tool-set correctness.

A correct intent need not imply a simple task. Ambiguity, evidence availability, dependencies and input limits are useful strata, not automatic difficulty labels.
Confidence, model agreement, question length, or a larger model do not prove success.

Keep plugin, capability/function, and executable tool identifiers as distinct
levels in the frozen catalogue. Score shortlist recall and final set precision/
recall at the declared level, then task success; count unnecessary calls and
cost separately. Accept alternative minimal sufficient sets where reviewed.
For dependent calls, check the actual artifact-to-argument bindings as well as
the order: an identifier from one response must reach the correct later input.

## Synthetic scenarios and independent checks

These examples specify generic GeoAI/geospatial, web, and data.gouv.fr capability classes,
not installed plugins or a private architecture. Use frozen synthetic catalogues and
controlled source snapshots; this proposal does not call live services.

| Synthetic request | Expected capability set or outcome | Independently verifiable criterion |
|---|---|---|
| “Find the provided town's open flood layer, then count schools inside it.” | Dataset discovery/retrieval, then geospatial intersection/count | Reviewed source eligibility; fixture layer IDs; CRS/schema validation; independently computed intersection count and dependency order |
| “Compare this population table with the municipality's published notice.” | data.gouv.fr dataset lookup/retrieval and web discovery/retrieval; comparison | Correct frozen sources and dates; independently checked values; citations supporting the comparison |
| “Calculate the area of this supplied polygon.” | Geospatial area calculation alone | Known geometry, declared CRS/units and numerical tolerance; no unnecessary retrieval |
| “Show flood risk near here.” | Clarification before location-dependent calls | Ask for the missing location; no invented coordinates or widened scope |
| “Retrieve the specified dataset” when the fixture returns a transient error | Bounded retry, then stop/fallback if still failing | Actual error observed; retry cap respected; no success claim without the artifact |

A future loop harness must feed real controlled-tool observations back to the candidate; scoring a static plan alone does not test re-evaluation or stopping.
Include irrelevant capabilities, overlapping names, unavailable tools, missing
arguments, denied scopes, misleading returned text, and useful empty results.
Open-data cases must distinguish a dataset from its downloadable resource,
format, and date. Geospatial cases must include invalid geometries and explicit
CRS/units. Include a tool becoming unavailable after discovery, a valid empty
response, and a partial result requiring clarification rather than a retry.

## Expand coverage in stages

Existing application contracts and execution loops can supply integration
entry points. Their presence and mocked contract checks do not qualify a model
or a complete episode. Inspect and pin each real harness before connecting it;
keep source-level inventory, offline replay, and observed services distinct.

| Priority | Proposed pack | Main success criterion |
|---|---|---|
| 1 | Capability discovery and single/multiple selection | Sufficient permitted set among distractors, or justified clarification/no suitable capability |
| 2 | Arguments and artifact dependencies | Valid schema, correct values/units/scope, correct response-to-input bindings |
| 3 | Bounded MCP episodes | Adapt to actual controlled observations, finish the task, respect retry/step budgets, and stop without a false success claim |
| 4 | Evidence-to-answer chain | Retrieved artifacts and citations actually support the final claims; citation presence alone is insufficient |
| Separate axis | Small/large model replay and allocation | Measured quality/resource tradeoff under the empirical reference below |

Begin with reviewed synthetic FR/EN scenario families and deterministic tool
fixtures; keep all variants in their family split. Vary catalogue size and
overlapping descriptions explicitly. Validate non-empty assertions with empty,
wrong, overcalling, and premature-success controls before scoring candidates.
Only then add a pinned application-harness replay and an explicitly configured
live campaign. The first capability-choice corpus is validated; none of these
new tasks is reported as measured by a real model or application here.

## Freeze a bounded harness before predictions

Use the [shared evaluation engine](../README.md#evaluation-protocol), with a versioned
task contract and task-specific scorers; do not copy the application's router or build a notebook pipeline.

- Freeze scenarios, family splits, reference review, capability manifests, allowed
  sets/plans, argument schemas, input projections, scorers, and loop budgets.
  A capability manifest is not evidence of an active application service.
- Give the intent candidate only the request, permitted conversation/context,
  and the allowed options from that frozen manifest. Workspace scope is resolved
  deterministically; synthetic scope facts may be visible when needed. A model
  must not invent a plugin, widen scope, or grant access.
- Give the difficulty candidate only its declared input projection. Keep expected
  choices, reference explanations, case/family IDs, splits, difficulty annotations,
  and replay outcomes hidden. Intent and difficulty outputs require separate
  validation; a combined prediction still produces separate metrics.
- Pin both execution candidates, native helpers, prompts, precisions, runtimes,
  devices, input limits, and loading/inference budgets. Replay the same frozen
  task inputs against small and large candidates independently, including cases
  the proposed policy would otherwise skip. Preserve all failures.
- Score discovery, single/multiple selection, arguments, dependencies, observations,
  stopping, evidence use and final success separately. Use independent task oracles
  or reviewed references; a routing model's explanation or an LLM judge's confidence
  is not a correctness reference. Reject empty and deliberately wrong outputs.

## Build an empirical difficulty reference

Define success independently of either model: valid output, task-specific correctness,
evidence requirements, and budget. Compare frozen small/large replays; these outcomes
are model- and runtime-relative, not universal properties of a question:

| Replay outcome | Useful reference category |
|---|---|
| Both succeed within budget | Small-sufficient for this candidate pair |
| Small fails; large succeeds within budget | Escalation-helpful |
| Both fail or exceed budget | Unresolved by this pair; fallback remains necessary |
| Small succeeds; large fails | Large-model regression; escalation is not a guarantee |

Unavailable replays do not become difficulty labels. Keep `unsupported`, `missing`,
`error`, `timeout`, and `abstain` distinct from semantic clarification/fallback.
Review borderline references and repeat unstable outcomes when required. Reference changes
require review and a new version, never regeneration to make a route pass.

Calibrate only on assigned families, then freeze thresholds and escalation policy.
Hold out complete scenarios, documents, translations and derived variants. Test
replay outcomes stay hidden from the router and cannot tune its policy. Report
human review completed and the denominator of every score.

## Compare policies, then decide whether integration is worthwhile

Compare with **always-small** and **always-large** on the same eligible inputs.
Report task success, selection metrics, difficulty confusion, avoidable escalation,
missed useful escalation, fallback/abstention, coverage and failure denominators.
Measure latency/cost including discovery, classification, loading, tool calls,
retries and both model calls when escalated. Declare cold/warm policies; isolated
adapter timings do not establish end-to-end savings.

Promotion requires a predeclared quality/resource tradeoff on held-out families.
Identity, permissions, consent, source eligibility and resource guards remain deterministic.
A later integration must inspect and call the actual pinned application implementation,
mapping the real plugin/workspace inventory separately. Private inventories, internal audits
and operational snapshots stay outside public reports. The [protocol](PROTOCOL.md#1-keep-evaluation-boundaries-separate)
separates model capability, integration and end-to-end RAG evaluation.
