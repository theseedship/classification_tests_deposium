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
they do not label the useful model size. The corpus is validated, with no real
model campaign run yet.

For a complementary or global series, retain a new archive for every dataset
and model/runtime pair. Keep the historical 132-case results separate, report
test-only scores and coverage, and preserve task/use-case/catalogue breakdowns.
Never append cases to an old archive or present old predictions as results for
the new tasks. Source and scorer fingerprints include the capability corpus
code and its four source files; older archives may require an explicit derived
rescore under a changed scorer. A rescore does not create new inference or timing.

### Retrieved passages and evidence

The [passage-evidence pack](../datasets/passage-evidence-v1/README.md) contains
1,536 cases derived from 24 synthetic families. It covers six languages, eight
question/passage language directions, four passage orders, and two visible views.
Those variants do not constitute 1,536 independent facts.

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
