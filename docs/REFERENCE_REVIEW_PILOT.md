# Human reference-review pilot: physics and passage evidence

**Preparation only: `not_started`, zero human judgments.** This protocol prepares
[issue #8](https://github.com/theseedship/classification_tests_deposium/issues/8).
The references and translations remain agent-authored. Validation, packet
generation, unit tests, and an agent checking this implementation are not human
scientific or linguistic review.

## Scope and limits

Review the meaning and wording of a bounded sample of the existing public,
synthetic [physics](../datasets/physics-choice-v1/README.md) and
[passage-evidence](../datasets/passage-evidence-v1/README.md) packs. The sample
uses **48 inputs from 16 families**, with **368 atomic assessment slots**:

| Work unit | Inputs | Families | Atomic judgments |
|---|---:|---:|---:|
| Physics choice | 16 | 8 FR/EN pairs | 16 choices |
| Passage relevance | The same 32 passage pools | 8 | 128 passage grades |
| Claim support | The same 32 passage pools | 8 | 192 passage/claim labels |
| Pool answerability | The same 32 passage pools | 8 | 32 pool labels |

There are 24 French and 24 English inputs. Passage pools use monolingual FR→FR
and EN→EN, rotation zero, with 16 `full` and 16 `head_384` views. The prefix is
384 Unicode characters, not tokens. Correlated translations and views are not
independent facts. Some full/prefix inputs are identical; keep their separate
identities and do not describe them as fresh examples.

This is a **diagnostic review of exposed v1 data**, including 8 train, 14
calibration, and 26 test variants. It creates no fresh held-out data, new split,
model result, validated difficulty scale, application integration, or end-to-end
RAG claim. It does not qualify unsampled families or DE/ES/IT/PT translations,
cross-language directions, passage rotations 1–3, or other benchmark datasets.
There is no general model ranking in this review.

## Reproduce the selection without inference

The [fixed manifest](../plans/reference-review-pilot-v1.json) records source-file
SHA-256 hashes and all selected IDs. Selection never reads a campaign archive,
model prediction, confidence, accuracy, or model disagreement:

1. Take FR and EN for eight declared physics families: uniform distance,
   kinetic energy, parallel resistance, wave speed, thin lens, thermal mixing,
   hydrostatic pressure, and missing mass. These sample supplied laws,
   assumptions, units, D1/D2/D3 authored strata, and underdetermination.
2. For each of the eight passage scenario types, take the lexicographically
   first existing family ID. Retain both monolingual FR/EN versions, both
   views, rotation zero, and each family's original split.
3. Keep all relevance, claim-support and answerability judgments for each
   selected pool. The strata include thematic material, unit/condition
   confusion, negation, distributed evidence, missing evidence, conflicts,
   and truncation. Human disagreements may affect a later dataset version,
   never the deterministic selection of this pilot.

Python 3.11+ and the standard library suffice; run from the repository root:

```bash
python3 -B scripts/reference_review.py check
python3 -B scripts/reference_review.py export \
  --output results/reference-review-pilot-001
python3 -B -m unittest discover -s tests -p 'test_reference_review.py' -v
```

The export refuses an existing destination and requires a new ignored
`results/` subdirectory. It makes `reviewer/inputs.jsonl`, blank
`reviewer/assessments.jsonl`, these instructions, and a separate
`coordinator/` folder with the authored references and source identities.
Keep coordinator files away from the initial reviewer. Nothing calls a model,
downloads weights, connects to an API, edits v1, or changes the model scorers.

## Stage A: independent human assessment

A coordinator gives only `reviewer/` to a person who can assess the selected
language and subject. Contributors may take a single law, language pair, or
evidence boundary; incomplete coverage stays explicitly pending. Agree the
assignment before review. Keep a separate unchanged blank packet for a second
independent reviewer where available; do not merge two people's rows by silently
overwriting one. This pilot does not require every contributor to review all
368 slots.

Use the visible text alone. Do not open authored references or model results
until the initial judgments have been saved. The packet removes source IDs,
family/split labels, expected answers, reference explanations/spans, relevance
roles, and model predictions. Claims, physics laws, alternatives, queries, and
passage text are legitimate task inputs. Opaque `V…`, `p…`, and `c…` IDs connect
the inputs and forms without semantic scenario names.

This is **limited procedural blinding**, not secret data: the public corpus,
manifest, and published campaign reports remain accessible, and a person may
recognize a scenario. Record `prior_exposure` as `none_declared`,
`dataset_or_references`, `model_results`, or `unknown`. Report unavoidable
exposure rather than claiming that all reviewers were blind. Do not substitute
an agent's or model's opinion for a person's assessment.

For each completed row, preserve `judgment_id` and fill:

- `status`: `completed`; `actor_type`: `human`; an opaque `reviewer_alias` such
  as `reviewer-A01` (no name, email, employer, or contact information).
- `judgment`: the appropriate value below; `explanation`: a substantive
  calculation or semantic explanation in the reviewer's own words.
- `wording_status`: `acceptable`, `issue`, or `unable_to_assess`;
  `wording_notes`: explain any linguistic or translation issue separately from
  the scientific/evidence judgment. A monolingual judgment does not establish
  translation equivalence; compare the paired FR/EN inputs explicitly if qualified.
- `prior_exposure`: one of the declared exposure values above.
- `evidence_quotes`: exact substrings of the visible passage for support or
  refutation. Leave the list empty when no passage quote applies. Explain
  missing evidence without inventing a quotation.

Keep unassessed rows exactly blank with `status: not_started`, as in the
[blank template](../templates/reference-review-assessment.json). The exporter
adds each task's `judgment_id` to that template. Never mark a placeholder,
copied authored answer, or agent response as completed human work.

### Task rubric and row IDs

| Row suffix | Allowed judgment | Decision rule |
|---|---|---|
| `.choice` | The supplied physics option ID (`a`–`d`) | Independently apply the supplied law and assumptions; check units and whether the facts uniquely determine an answer. Explain ambiguity rather than silently rewriting the problem. |
| `.relevance.pN` | Integer `3`, `2`, `1`, or `0` | `3`: directly establishes **or refutes** the requested fact; `2`: supplies part of the needed evidence; `1`: shares the topic without deciding it; `0`: no useful evidence. |
| `.support.cN.pN` | `supports`, `refutes`, `insufficient` | Judge this entire claim from this single visible passage. Different numbers, units, conditions, subjects, negation, and scope matter. A related fact is not automatically a refutation. A conjunction can require more than one passage. |
| `.answerability` | `answerable`, `insufficient_visible_evidence`, `conflicting_visible_evidence` | Judge only the visible pool. An unresolved conflict differs from missing evidence. Missing retrieved evidence does not prove absence from a complete collection. |

Support/refutation requires at least one exact visible quote. The form does not
ask for a model prediction, model ranking, or personal reviewer data. If no
physics option is defensible or the evidence label set is ambiguous, explain
the issue, leave that atomic row pending, and send the issue to the coordinator;
do not force a choice to obtain completion.

## Stage B: comparison and adjudication

After saving the independent assessment, the coordinator may reveal the separate
authored-reference file. Preserve the original human forms unchanged. Record
each substantive or translation disagreement with the opaque review/judgment
ID, original authored label, human label or ambiguity, explanation, exposure,
and proposed next step. Where practical, ask another qualified person to assess
disputed material before discussing the expected answer.

Classify issues as scientific/semantic, linguistic/translation, rubric ambiguity,
or implementation. An agreement is not automatic scientific approval. Record
unresolved disagreement explicitly; the pilot supplies no automatic adjudicator.
The offline audit checks declarations and required fields; it cannot verify
that an actor is human, assess expertise, or judge the quality of an explanation.
The coordinator remains responsible for confirming the real review process.

```bash
python3 -B scripts/reference_review.py audit \
  --assessments results/reference-review-pilot-001/reviewer/assessments.jsonl
```

Blank, missing, or partial forms produce `not_started`/`in_progress` and exit 1;
malformed rows exit 2. Exit 0 means all 368 slots have structurally valid
**declared human assessments**, including disagreements. It does not mean the
references were approved. The fixed manifest records preparation status only;
the audit reports progress from the supplied forms without changing it.

## Reporting and reference changes

A later public report must state the actual human count and expertise in broad
terms, assigned/assessed/pending denominators by task, language, family and view,
review method and exposure, unresolved disagreements, and the exact source
hashes. Separate human findings from agent checks. Until real people contribute,
report **zero human judgments and `not_started`**.

Publish only reviewed synthetic examples and consented anonymous findings.
Generated packets and assessment files remain ignored; do not force-add them.
Do not publish personal details or private Deposium material. If a reference
needs correction, discuss the reasoning, obtain review, and create a separately
versioned change while retaining v1 data and historical campaign archives.
Neither this pilot nor its exporter modifies references to improve model scores.
