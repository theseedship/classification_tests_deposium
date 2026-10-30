# Passage order and evidence retention v1

This is the bounded **offline implementation slice** for
[#13](https://github.com/theseedship/classification_tests_deposium/issues/13),
frozen on 30 October 2026 before any new candidate predictions. It plans the
existing four passage rotations, scores retained choices, and evaluates the
evidence kept by the existing relevance-to-ranking composition. It launches
no candidate, downloads no weights and contacts no service.

The [machine-readable plan](../plans/passage-order-retention-v1.json) and
[shared implementation](../deposium_bench/passage_order_retention.py) preserve
`passage-evidence-v1` and every historical observation. Sources, translations,
minimal evidence sets and support labels remain agent-authored, pending human
review. These controls test the implementation, not the truth of all references.

## Frozen scope and physical calls

The default selection contains all **512 test pools**, eight families, eight
language directions, `full` and `head_384` views, and rotations 0–3. The same
24-family corpus also has complete train/calibration selections. Families,
queries, passage identities/text, references and splits must remain the same
across their four rotations. Reference arrays may follow passage order; their
meaning is compared by identity without modifying the frozen data.

The plan uses the existing `export_requests` and `choice_plan`. Physical-call
identity is the shared SHA-256 of canonical serialized **contract and permitted
candidate input**. Labels, split/family metadata and descriptive case IDs do not
participate in the model input or determine reuse.

| Axis | Logical decisions | Distinct physical calls | What the rotation changes |
|---|---:|---:|---|
| Relevance | 2,048 | 264 | Nothing in the single-passage candidate projection. |
| Claim support | 3,072 | 392 | Nothing in the single-passage candidate projection. |
| Answerability | 512 | 264 | The visible passage order in the whole-pool input. |
| Total | **5,632** | **920** | Correlated variants, not independent facts. |

Rotation zero alone has 728 distinct calls. A complete matching rotation-zero
archive can supply the same 264 relevance and 392 support calls, plus 72
answerability calls. The full plan has **192 additional unique answerability
inputs**. They remain unobserved when only that old archive is available.
Identical complete/head views and identical visible text can also share inputs;
do not assume four times the physical cost or four independent samples.

Reusing one single-passage result across rotations establishes **projection
invariance**, not observed model robustness to pool order. Answerability exposes
order. A relevance-derived ranking can still change with pool order because its
declared tie rule uses that order; this is composition behavior, not a changed
relevance prediction. There is no fresh held-out reasoning-family claim.

## Evidence retention means retained reference evidence

The rule is fixed, has no fitted threshold, and is not selected from model
errors. Use only the existing `compose_rankings` **replacement** path: sort all
four passages by predicted relevance grade descending and preserve the input
passage order for equal grades. No baseline reranker, additive composition or
answerability gate is applied in this slice. An external ranking requires a
separately declared source and analysis extension; it is not silently treated
as observed here.

Evaluate the fixed cutoffs **k = 1, 3, 4**:

| Metric | Eligible pools | Success at cutoff k |
|---|---|---|
| `sufficient_set@k` | `answerable` only | The first k ranked IDs contain at least one complete frozen `minimal_evidence_sets` entry. One member of a distributed set is insufficient. |
| `conflict_pair@k` | `conflicting_visible_evidence` only | The retained IDs include a `supports` passage and a `refutes` passage for the **same** frozen claim. Opposite labels for different claims do not qualify. |

These two populations are distinct. An insufficient-evidence pool has neither
metric applicable: its result is `null`, not a perfect retention score. It still
participates in the separate answerability task. Retaining a conflict is not a
correct generated answer, and retaining one sufficient set does not establish
retrieval recall outside the four supplied passages.

The shared `score_rankings` validates exact full-pool permutations and supplies
nDCG, MRR and recall with its existing definitions. Zero ideal gain leaves nDCG
undefined; no relevant passage leaves MRR/recall undefined. Those metrics are
reported only for the replacement rankings actually constructed by this code,
never for an unexecuted reranker or product journey.

## Failure and order denominators

Choices are graded with the shared `score_choices`; their status, coverage,
class metrics and all-decision denominators remain separate by axis. Empty,
invalid, unknown and duplicate outputs fail validation. Missing, unsupported,
error, timeout and technical abstention remain distinct from semantic
insufficiency or conflict choices.

A replacement ranking needs all four valid relevance decisions. A missing or
failed decision prevents a valid ranking; the existing composition propagates
its declared failure precedence. On an eligible retention pool, such failures
contribute zero to `mean_over_eligible_missing_zero` and remain absent from the
conditional observed mean. Report eligible/defined/total counts alongside both
means. Zero eligible pools has a `null` rate; zero valid predictions cannot
produce a passing evaluation. The command emits no global PASS verdict.

For each axis, match the four rotations by family, language direction and view,
plus passage/claim identity for the single-passage projections. Report complete
valid groups, label disagreements and correctness changes among complete groups,
status changes among all groups, and all-four-correct counts over **all** groups.
A failed or missing rotation is not agreement. Reports also retain the shared
scores by rotation, view, language direction and family. Families are the
independent grouping unit for any later uncertainty analysis; this module
performs no significance test.

## Archive validation and reproducible commands

The analysis accepts one existing sealed passage-choice archive containing
either the complete selected rotations or its complete rotation-zero case set.
It verifies the shared seal, frozen corpus/case identities, exact reconstructed
logical and physical request bytes, their manifest hashes, physical response
identities/order, strict output envelopes, physical status/coverage summary,
and reconstruction of stored logical predictions from the physical trace.
Stored scores are not used as a substitute for rescoring the retained outputs.
The retained dataset manifest must match the frozen release exactly. Source
profile, original profile-byte fingerprint, benchmark source-file fingerprints,
adapter-initial provenance and summary initial/final identity are required and
cross-checked. Explicit recorded controls also retain their recordings and
rehashed recorded identity; they remain `harness_control` sources.

Native sources must retain model, runtime, gateway, harness, runtime-pin,
settings and session/supervision links. D3 sources must retain worker, assets,
runtime pins, precision and runtime hashes. Model/runtime identities must remain
stable between initial and final provenance. Original profile bytes and the
normalized archived profile legitimately have different hashes. Likewise, native
adapter identity hashing preserves original session key order, which the sorted
archive serialization does not retain universally: the analysis preserves that
declared digest and checks its profile/session/code links and stability, without
claiming a universal native identity rehash or checking a live runtime.

Only observed physical responses whose contract and candidate input match
exactly can be reused. A recorded error stays an error; an unseen input stays
missing. No synthetic answerability observation, extra forward, latency or
successful cached substitute is invented. A partial source remains partial.
The derived report retains the source's **declared** qualification and seal
hash, observed/unobserved physical counts, current analysis-source hashes and
its own seal. Seals establish byte integrity, not external producer authenticity.
The source seal is bound to the validated bytes and checked again before writing;
symlinks and special seal entries are rejected before their payload is read.
An offline rescore does not itself qualify a model or authenticate its source.

From a fresh public clone, with Python 3.11+:

```bash
python3 -m deposium_bench.passage_order_retention plan
python3 -m unittest tests.test_passage_order_retention -v
```

Given an independently available raw source archive, create a **new** ignored
derived archive (the source is never overwritten):

```bash
python3 -m deposium_bench.passage_order_retention analyze \
  --choice-archive results/your-existing-passage-choice-archive \
  --output results/passage-order-retention-derived-001
```

The source archives are not restored by cloning the public repository. The
focused tests author explicitly labeled transport controls locally and patch
network, subprocess and adapter/inference entry points to raise during actual
analysis. They exercise real shared projections/scorers/archive validation,
not a second inference pipeline.

## Execution budget and remaining qualification

The present plan admits **zero model calls, zero network calls and zero
candidate adapters**. A future 920-call test campaign is not authorized or
resource-qualified by this offline plan. Before its first prediction, a separate
candidate-specific protocol must pin the model/runtime/input preparation and
freeze numeric time, memory, per-call and physical-request budgets after an
appropriate calibration canary. Existing rotation-zero archives do not remove
that requirement for new calls; no retry or backend fallback is assumed.

The current shared observer remains a rotation-zero observer. This change does
not replace it with another runner or claim that it can already execute the
full new plan. A future all-rotation collection must extend that shared path,
retain its lifecycle guards and write compatible sealed traces. Human reference
review, true candidate order observations, retrieval, final answers/citations
and application integration remain separate qualifications.
