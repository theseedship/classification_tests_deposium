# RAG decision and evidence evaluation protocol

This benchmark studies decisions inside retrieval-augmented generation (RAG):
understanding a request, proposing a tool, ranking retrieved passages, and
assessing whether visible evidence supports an answer. It is exploratory.
References and translations are agent-authored and pending human review.

The [README](../README.md) gives the entry points and selected observations.
Dataset cards and individual campaign protocols define the exact inputs,
revisions, budgets, metrics, and qualifications of each experiment.

## 1. Keep evaluation boundaries separate

| Level | Input and output | What it can establish |
|---|---|---|
| Model capability | A fixed task input produces a choice, ranking, or evidence label | Behavior of that candidate on the declared dataset and runtime |
| Application integration | A candidate proposal passes through real application guards and handlers | Behavior of the specified integration revision and configuration |
| End-to-end RAG | A user request triggers retrieval, generation, citations, and delivery | Quality of the observed complete journey, with its services and data |

A model choosing `search` does not prove that a useful document was retrieved.
A relevant passage does not prove that the generated answer used it correctly.
A valid citation identifier does not prove that the cited text supports a claim.
The current model comparisons do not qualify end-to-end RAG or product behavior.

Identity, access, source eligibility, consent, and resource controls remain
deterministic. A model proposal does not authorize a tool or grant data access.
Application integrations must call the actual pinned implementation; the benchmark
must not copy application routing rules into a second implementation.

## 2. Use a task-specific dataset and metric

### Automatic grading and reference checks

Exploratory model comparisons do not require a person to fill the human-review
forms. The candidate receives only its allowed input; a frozen reference and
the shared task scorer grade its recorded output automatically. No tested
model supplies its own expected answer or changes the grading rule. The main
context, physics, capability and tool-plan packs contain FR/EN cases. Passage
evidence additionally covers DE/ES/IT/PT and declared cross-language directions.
Documentation is in English; that does not make the benchmark English-only.

Keep the following checks distinct:

| Check | What it establishes | Remaining limit |
|---|---|---|
| Executable numerical or structural oracle | Exact rational calculations, finite algebra/chemistry rules, advertised types and constraints match the frozen synthetic fixture. | A supplied physical law, assumption, translation or natural-language interpretation may still need review. |
| Shared scorer controls | Declared correct outputs pass and deliberately wrong/empty outputs fail; failure states and denominators are retained. | Passing the reference through its own scorer does not independently prove the reference correct. |
| Additional agent review | An assistant can independently derive a response from the visible input, record reasoning, then compare with the reference and flag ambiguities. | Agents can share errors; agreement or majority vote is not proof of semantic truth or human review. |
| Optional human review | A person can examine meaning, wording and scientific assumptions under the [review pilot](REFERENCE_REVIEW_PILOT.md). | Record actual expertise/scope and disagreements; no form is mandatory for continuing offline engineering or exploratory campaigns. |

Run the bounded automatic reference/grid audit with Python 3.11+:

```bash
python3 scripts/check-reference-grids.py
```

This standard-library command reuses the existing validators and scorers. Its
report separates source/oracle consistency and scripted scorer controls,
states actual denominators and keeps semantic/human review qualifications
explicit. It performs no candidate inference, model download or paid API call.
The [dated command output](evidence/reference-grid-check-20261029.json) records
the exact source hashes, Python version and tested control scopes before the
discovery extension. The current command also checks the new discovery pack;
the earlier report remains unchanged as historical evidence. The
[dated agent-review evidence](evidence/agent-reference-review-20261029.json)
separately records eight physics cases and sixteen passage pools: 184 label
comparisons, all matching the authored references in this sample. This is an
agent consistency assessment, not a new candidate model score or a review of
every corpus variant.

For a fair comparison, freeze the same dataset version, permitted inputs,
reference alternatives and scorer for each candidate, then retain every
incorrect, missing, unsupported, errored or timed-out result. Report language,
task, split and runtime separately. If a reference is disputed, preserve old
data/results and propose a reviewed new version; never repair a reference
merely to agree with a tested model. Free-form answers need their own qualified
rubric and judge path; existing exact-choice scores do not establish that path.

### Context-dependent choices

The [context-choice pack](../datasets/context-choice-v1/README.md) contains
132 synthetic cases in 66 FR/EN families. Documentary cases distinguish inventory,
stored summaries, retrieved answers, and insufficient information. Mathematics
and chemistry provide controlled probes of context use, constraints, and reasoning;
they are not demonstrations of scientific expertise or full RAG performance.

The candidate receives the context, question, and ordered option descriptions.
The scorer checks the selected option against the versioned reference. An explicit
information-insufficient option is a semantic answer, not a runtime failure.

There are 36 train, 30 calibration, and 66 test cases. Reports showing 132-case
totals include all three splits and must identify that fact. Keep test-only
results separate from the full exploratory total.

### Elementary physics choices

The separate [physics pack](../datasets/physics-choice-v1/README.md) contains
48 FR/EN choices in 24 families, with 12 calibration and 36 test cases. Each
input supplies the law and assumptions. Exact rational oracles check the
authored alternatives; scientific and linguistic human review remains pending.
It measures finite rule application, not general physics expertise. Physics
length variants are not implemented.

The shared engine, projection and scorer apply. Keep physics/48 and test/36
separate from the context and capability packs; label analysis groups
`physics-choice-v1`. The [first direct Flash campaign](PHYSICS_FLASH_RESULTS_20261029.md)
scored 39/48, including 32/36 test, on 29 October 2026. The original prepared
gateway-backed protocol and optional hosted Turbo adapter are separate
inference paths; neither was executed by that campaign.

### First tool proposals

The [24-case tool proposal pack](../datasets/mastra-read-pilot-v0/README.md)
contains 12 FR/EN families with three options: search, statistics, or fallback.
The model observation measures agreement with provisional proposals. It does not
execute tools, validate their arguments, or assess a business result.

There are no human-approved references and no semantically qualified cases in
this pack. Report agreement counts with this qualification; do not present them
as validated routing accuracy. Separate search, statistics, and fallback results,
since a good total can hide failures on fallback.

### Complementary capability and workflow choices

The [capability-choice pack](../datasets/capability-choice-v1/README.md) adds
192 cases in 48 synthetic FR/EN families: capability/tool-set proposals,
arguments and dependencies, and next steps after fixed tool observations.
Every family has compact (eight cards) and expanded (32 cards) catalogue views.
These variants share a split and reference; they are correlated observations.
There are 48 train, 48 calibration and 96 test cases. Choice positions are
balanced within split, language and catalogue view.

It uses the shared context-choice engine and exact scorer. The candidate
chooses among four proposals, with authored references pending human review.
A correct proposal does not establish open-set discovery recall, executable
arguments, valid access, tool execution or task success. A fixed observation
does not test an adaptive multi-turn loop. D1/D2/D3 remain authored strata;
they do not label the useful model size. The first
[D3 Flash Q8/Metal campaign](CAPABILITY_FLASH_RESULTS_20261029.md) reached
192/192 (test 96/96) on 29 October 2026. The references still await human review;
reaching the ceiling on this closed-choice pack does not qualify tool execution
or product behavior.

For a complementary or global series, retain a new archive for every dataset
and model/runtime pair. Keep the historical 132-case results separate, report
test-only scores and coverage, and preserve task/use-case/catalogue breakdowns.
Never append cases to an old archive or present old predictions as results for
the new tasks. Source and scorer fingerprints include the capability corpus
code and its four source files; older archives may require an explicit derived
rescore under a changed scorer. A rescore does not create new inference or timing.

### Experimental bounded tool proposals

The [tool-plan contract](TOOL_PLAN_CONTRACT_V1.md) introduces a structured
proposal through the same case, adapter, campaign and typed exact scoring
engine. Its [initial fixture](../datasets/tool-plan-pilot-v1/README.md) contains
one new synthetic FR/EN family: two training cases and zero held-out cases.
Complete alternative plans bind canonical proposed artifact IDs, while empty,
wrong, malformed, extra-call and premature-success controls must fail.

Only a recorded `harness_control` profile is currently admitted. No model
output path is qualified and no tools or numeric computation are executed.
The 12-family expansion is a proposal, not a materialized test set. Keep this
fixture outside model rankings; executable argument values and adaptive
episodes require the later contracts and actual execution evidence.

### Catalogue discovery and tool-set selection

The [tool-discovery pack](../datasets/tool-discovery-v1/README.md) adds six
synthetic FR/EN families (12 cases), with two families assigned to each split.
The input exposes a bounded catalogue, a request and a shortlist limit; plugin,
capability and tool IDs are distinct. Eligibility and availability are fixed
fixture facts and deterministic guards, independent of the candidate's choice.

The output separates a shortlist of **tool IDs** from a final unordered tool
set and the semantic decision `select`, `clarify` or `no_suitable`. A correct
nonselection can contain no tools; an empty output or empty `select` cannot
pass. Alternative minimal sufficient sets remain hidden in the reference.

Report shortlist recall/precision at the declared tool level and limit,
separately from final-set sufficiency, exact minimal-set success and unnecessary
selections. Match the best valid alternative; do not require the union of all
equivalent solutions. A final superset can be sufficient while failing minimal
success. Missing and failed outputs stay in the eligible denominators;
inapplicable metrics are null rather than a fabricated perfect score. The
[versioned contract](TOOL_DISCOVERY_CONTRACT_V1.md) defines the exact formulas.

The [dated offline evidence](evidence/tool-discovery-offline-20261029.json)
records 12/12 passing scripted cases and a separate expected failing superset
control (11/12, with all cases scored). Both controls retain six sufficient
select sets, while the excessive control has only five minimal sets and one
unnecessary tool. These receipts qualify the harness and accounting only;
they add no real-model observation to the ranking.

This slice uses the shared case/adapter/campaign/scoring path and a recorded
`harness_control` profile. Real model profiles cannot advertise the contract
until their output path is qualified. No arguments or tools execute, and
selecting a dependent pair checks its membership, not execution order or
artifact values. Those are covered by the separate argument and episode fixtures below. Existing v1 packs and model results
are preserved; the new scorer fingerprint identifies the additive task code.

### Executable arguments and actual artifact bindings

The [tool-arguments pack](../datasets/tool-arguments-v1/README.md) contains four
FR/EN training cases in two synthetic table families, with no held-out cases.
An explicit `fixture_arguments` control profile actually runs a bounded lookup,
passes its actual observation through a whitelisted candidate projection, and
executes one guarded sum proposal. Literal artifact IDs, column, unit and scope
must match; the harness does not fill an artifact placeholder for the candidate.

Candidate recordings contain proposals only. The execution adapter constructs
the receipts, projected input/hash and trace. Ordinary recorded and real-model
profiles cannot advertise this execution contract. Keep tool selection, argument
validity, artifact binding, execution and result metrics separate, with failed
and unobserved cases retained in the declared denominators. Missing receipts
do not establish zero execution. The [contract](TOOL_ARGUMENTS_CONTRACT_V1.md)
defines bounds, source-closure hashes and strict provenance.

The reference-grid command validates this pack without calling either tool.
Its explicit shared-CLI control executes the two local functions. Rescore
validates retained receipts without executing tools or the policy again.
The [dated execution evidence](evidence/tool-arguments-offline-20261030.json)
records four passing cases with eight actual tool calls. A separate wrong-unit
control retains all four scored cases, passes three and observes seven calls:
the invalid second operation is blocked after its actual lookup.
The first lookup is fixed, followed by one proposed call; retries, adaptive
observations and stopping are covered by the separate episode contract below.
No real model, live MCP or product integration is qualified by these controls.

### Bounded episodes driven by actual observations

The [tool-episodes pack](../datasets/tool-episodes-v1/README.md) contains seven
synthetic families as 14 FR/EN training cases, with no calibration or test cases.
The dedicated `fixture_episode` control adapter invokes a policy after each
actual bounded lookup/sum observation. The candidate sees only the declared
request, known parameters, tool interfaces/availability, history and remaining
budgets; source fault schedules and references stay outside that projection.
Recordings contain actions only, never supplied execution receipts.

Normal and transient-error scenarios can produce a verified sum. Persistent
failure, empty data, partial data, missing input and unavailable tools require
an evidence-based stop or clarification. Report procedure correctness over all
14 cases separately from successful task results over four eligible cases.
Selection, arguments and execution have 12 eligible cases; binding and result
have four; stopping and budgets have 14. Retain failed or missing cases in each
eligible denominator. Actual call/step counts are diagnostics, not exact-path
gold answers: another legal path within the same bounds may pass.

The [contract](TOOL_EPISODES_CONTRACT_V1.md) defines independent step, call,
lookup-retry and monotonic elapsed-time guards. Time is checked around the
synchronous fixture invocations; this is not hard interruption of arbitrary
model or service execution. Success requires a retained actual sum
receipt and cannot pass from a correct-looking value alone. Invalid proposals
remain failures even if followed by a valid finish. Each policy input/hash,
proposal, guard, receipt, timing and counter is archived. Rescore validates the
retained transcript without invoking tools, the policy or a clock again.

The reference-grid audit only validates this pack's structure, frozen oracle
and control hashes; actual tool execution requires the explicit shared-CLI
profile. The [dated offline evidence](evidence/tool-episodes-offline-20261030.json)
records controlled execution and negative controls. Scripted controls establish
harness behavior, not real-model adaptation, held-out quality or live MCP/RAG
qualification. Ordinary recorded and real-model adapters cannot claim this
execution contract until a separate output path is qualified.

The positive control handles 14/14 cases in 34 policy decisions and 20 actual
tool calls (14 successful receipts and six controlled errors). Only four cases
produce successful task results. Replacing one normal policy with a premature
correct-looking answer yields 13/14, 18 actual calls and three task results;
all 14 cases remain scored. The altered case executes no tool and fails its
procedure and result checks.

### Generated JSON proposals: prepared local qualification path

The [local tool-policy adapter](LOCAL_TOOL_POLICY_V1.md) provides a separate
`llama_cpp_json` path with an owned loopback session, strict generated-JSON
parsing, source/model/template bindings and retained raw response bytes.
Discovery proposes a native shortlist/selection. Argument evaluation reuses
the actual fixed lookup and guarded sum. Episodes inject the model policy
into the same runtime after each actual observation. No authored complete-plan
choice or symbolic argument substitution replaces generation.

The [canary](../datasets/tool-policy-canary-v1/README.md) freezes ten TRAIN
cases in five FR/EN families, with no held-out cases. Its new episode input/v2
permits a declared maximum 60,000 ms; input/v1 stays bounded at 1,000 ms and
all original references remain unchanged. Actual model and tool time count
toward the episode deadline. Retained call, policy, episode and case timings
must be mutually consistent. Parsing, execution guards and source-scope checks
remain independent of native grammar enforcement and candidate predictions.

Raw generations, proposal/request hashes, statuses and execution receipts are
bound and checked on pure rescore. Invalid JSON, incomplete, explicitly truncated
or credential-bearing responses cannot become scored proposals; wrong but
valid JSON still reaches the task's independent correctness checks. No rescore
invokes a model, tool, clock, old service or credential.

The [fixed native protocol](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md)
requires the pinned Qwen3 4B Q8 asset, one process/slot, actual Metal offload,
8 GiB RSS plus 8 GiB reserve, a 600-second session and 20-second HTTP calls.
The known single-model native alias behavior is recorded separately from the
fixed client alias and owned-model identity. A requested schema is not proof
that every grammar constraint or semantic field was enforced.

This is **offline preparation only**: zero real-model cases, no downloaded
weights, no native generation or successful model canary are established by
unit controls. The added generative candidate does not replace or reorder the
frozen classifier cohort. Actual qualification and any later evaluation need
fresh admission and sealed execution evidence.

### Retrieved passages and evidence

The [passage-evidence pack](../datasets/passage-evidence-v1/README.md) contains
1,536 cases derived from 24 synthetic families. It covers six languages, eight
question/passage language directions, four passage orders, and two visible views.
Those variants do not constitute 1,536 independent facts.

The [order/retention extension](PASSAGE_ORDER_RETENTION_V1.md) freezes the
existing four rotations and both views without changing their references.
Its test selection has 512 pools, 5,632 logical decisions and 920 distinct
physical requests under the shared candidate projection. Single-passage
relevance/support inputs are invariant across pool rotations; reusing their
outputs is not evidence of model robustness to order. Whole-pool answerability
does expose passage order. Rotation-zero observations leave 192 additional
unique answerability inputs missing. The offline analyzer verifies sealed
source identity and rescores actual observations without creating a candidate.

Evidence retention uses only the existing replacement composition: predicted
relevance descending, input order for ties. At fixed cutoffs 1/3/4, report
complete minimal evidence-set capture for answerable pools and same-claim
support/refutation-pair capture for conflicting pools. Missing or failed
eligible rankings contribute zero to the full eligible denominator; inapplicable
metrics remain null. This is retained synthetic evidence, not generated-answer
correctness. The [plan](../plans/passage-order-retention-v1.json) permits zero
model/network calls; future inference requires a separately frozen calibrated
candidate envelope. Historical datasets, references and observations stay intact.

Evaluate these tasks separately:

- **Ranking:** order a fixed pool of visible passages; report the declared nDCG
  and related ranking measures with their cutoff and eligible denominator.
- **Relevance:** distinguish direct, partial, thematic, and irrelevant material.
  A passage refuting the requested fact can still be highly relevant.
- **Claim support:** classify each visible passage as supporting, refuting, or
  insufficient for the supplied claim. Shared words or numbers are not proof.
- **Answerability:** determine whether the visible pool provides sufficient,
  insufficient, or conflicting evidence. Missing evidence in that pool does not
  establish absence from an entire document collection.

Compare the same passage pools and visible views. The `head_384` view is a prefix
of 384 Unicode characters, not a token limit or an application's window selector.
Its references concern only the visible prefix. Evidence split across passages
may require multiple passages; do not assume that one passage supports a whole
compound claim. Report unsupported groups or undefined ranking measures explicitly.

The other dataset cards identify legacy projections, typed contract controls,
and review-only templates. A template with unresolved references is not a scored
dataset. The 14 document-task cases are a projection of the 36 typed-decision
cases, not another independent sample.

## 3. Freeze the experiment before predictions

Record the dataset version and hash, selected task projection, reference review
status, scorer, candidate profile, and resource budget. Pin the model revision,
tokenizer, native helper, runtime, dtype or quantization, device, prompt, maximum
input length, and overflow policy. A repository name or parameter count alone
does not identify the model that ran.

Keep documents, scenarios, translations, and derived variants in their family's
assigned split. Set thresholds and composition rules on train/calibration data;
do not tune on test cases. Reference changes require an explanation and review,
not regeneration in response to an inconvenient model score.

All published references remain subject to human and linguistic review. The
restricted mathematical and chemical oracles check properties of their synthetic
fixtures; they are not general symbolic solvers or expert validation.

## 4. Audit the input and inference path

Only the task-specific allowed input projection is sent to the candidate.
Expected answers, reference explanations, reference spans, split labels, family
labels, and descriptive case identifiers stay outside model inputs. Candidate
claims and passages may be inputs to a support task; their annotations are not.

Use the model's actual native helper for rendering, tokenization, readout, and
calibration. Record the observed device and precision. Model-specific adapters
can audit native token IDs, masks, and actual forward inputs; reports must state
which checks were observed rather than assuming all adapters provide the same
instrumentation. Refuse unsupported lengths before inference where the declared
protocol requires complete inputs. Do not silently truncate evidence or substitute
a different device, model, checkpoint, or backend.

Use one loaded candidate and a declared request concurrency. Keep initialization
and inference limits, timeouts, and memory admission explicit. An ordinary import,
unit test, dataset export, or notebook opening must not download weights, call a
paid API, or modify an application service. Real campaigns are explicit actions.

## 5. Preserve outcomes, coverage, and denominators

`ok` means structurally valid output, not a correct answer. Keep `unsupported`,
`missing`, `error`, `timeout`, and `abstain` distinct. A semantic insufficient-
evidence answer is different from technical abstention or an omitted result.
Do not discard unsuccessful states from a denominator or replace them with a
successful cached answer. Empty responses, missing corpora, empty assertions,
and zero scored cases cannot establish a passing evaluation.

Report the eligible total, valid outputs, scored cases, successful cases, and
counts of every unsuccessful state. Separate tasks, languages, domains, splits,
and relevant family groups. Do not merge closed-choice accuracy, ranking scores,
claim support, and provisional routing agreement into one unexplained score.
Translations, passage rotations, and repeated variants remain correlated; any
uncertainty estimate must respect their grouping rather than counting each as
an independent sample.

## 6. Interpret resource measurements narrowly

State the hardware, runtime revision, requested and observed device, precision,
input lengths, concurrency, and warmup/repetition policy. Separate model loading,
first call, and subsequent calls. A single pass provides descriptive latency,
not a production tail guarantee. Synchronize accelerated work when measuring it.

File size does not predict resident memory. Process RSS, device allocations,
and host available-memory estimates measure different things; do not add them
as if they were disjoint parts of unified memory. A result on CPU, MPS, Metal,
or CUDA does not qualify another backend. Unit tests under Linux do not establish
that a model's forward pass has run under WSL or on a particular GPU.

## 7. Retain evidence and state reproduction limits

The CLI and notebook use the same engine, datasets, adapters, and scorers.
Each campaign writes a new archive with its inputs, profile, provenance, raw
outputs, summary, and integrity hashes. A resume or rescore retains the original
and creates a derived archive. Keep failed attempts and partial coverage.
Hashes establish byte integrity; they are not independent authentication of
the producer or proof that an annotation is true.

The repository distributes source, synthetic datasets, profiles, and selected
aggregate reports. It does not distribute model weights, installed environments,
private documents, or every historical raw archive. Validation is reproducible
without models or application services. Rescoring a historical campaign requires
its raw archive; a new inference also requires its exact assets and runtime.
Remote APIs can change even with a fixed seed, so bitwise reproduction is not
assumed. Public reports must retain these distinctions.

When reporting or citing a result, include the task, dataset version, split,
denominator, reference-review status, model revision, runtime/precision, and report
date or producer identity. Publish only data and outputs cleared for release;
secrets, personal paths, private document contents, and internal source audits
are not benchmark inputs to distribute.
