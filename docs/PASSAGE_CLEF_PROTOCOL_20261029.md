# Clef Flash Q8: matching-input native passage protocol

**Frozen before Clef passage predictions, 29 October 2026.** This is a
separate candidate observation on the same passage inputs as the completed
[D3 Flash campaign](PASSAGE_FLASH_RESULTS_20261029.md). References, projections,
selection, option order, scorers and resource limits remain unchanged.
Synthetic references and translations are agent-authored, pending human review.
No result from D3 selects, relabels or removes a Clef test case.

## Fixed task selection and comparison

Use the [D3 passage protocol](PASSAGE_FLASH_PROTOCOL_20261029.md) selection:
`passage-evidence-v1`, SHA-256
`35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`,
test split, rotation 0, eight families, eight language directions and both
`full` and `head_384` views, for **128 pools**. The prefix is 384 Unicode
characters, not a model token window. Translations, views and input reuse are
correlated; they do not create independent facts.

| Axis | Logical decisions | Distinct physical calls | Output |
|---|---:|---:|---|
| Relevance | 512 | 264 | Four grades 0–3 |
| Support | 768 | 392 | supports / refutes / insufficient |
| Answerability | 128 | 72 | answerable / insufficient_visible_evidence / conflicting_visible_evidence |

The shared `select_pilot`, `export_requests`, `choice_plan`, `candidate_row`,
`observe_choice` and `score_choices` supply the plan, projection and scoring.
Deduplication uses exact contract/input bytes, never labels. Compare **728
physical calls / 1,408 logical decisions** to the sealed D3 observation without
rerunning or rewriting it. Freeze identical logical/physical request-plan hashes
and calibration call IDs in the [Clef plan](../plans/passage-clef-flash-v1.json).
Candidate aliases and native tokenization differ; task inputs must match.

Only context, question and option descriptions reach the model, with neutral
choice keys. The candidate claim is allowed support-task input. Exclude golds,
annotations, spans, split/family labels and descriptive case IDs. Preserve
missing, unsupported, error, timeout and abstain separately in every denominator.
Semantic insufficiency remains a valid choice, not technical abstention.

## Clef identity and joint preparation

Use existing local `ggml-org/Clef-Flash-GGUF` Q8_0 weights, revision
`6e2a164d70aae2af7fce86005da3f91805565b1d`, SHA-256
`25f801e2a27610b0ccc0cb1558d7eda3d7a304e34e2c4a04e3079357ff7d906e`,
pinned by `profiles/clef-flash-q8-assets.json`. The exact upstream Cloudflare
revision converted into this GGUF is not attested. This experiment does not
qualify BF16/PyTorch, CUDA, visual or generation features, or Clef 27B.

Use clean upstream llama.cpp revision `efe3626b119ff81033e309c3ba07a770bef2c546`,
native binary SHA-256
`d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1`,
and the separately fingerprinted vocabulary-only helper. Explicitly select
`--decision-type clef` and the actual native `fill_task_joint`; D3 preparation
cannot qualify Clef. Verify token and joint decision-order hashes, native score
count and three/four-option head layouts. Test inputs include 264 four-option
and 464 three-option physical requests. Three-choice inference requires live
technical admission; the earlier three-choice preparation control is insufficient.

Prepare **872 distinct ordinary inputs**: 728 passage test inputs, the same
12 calibration controls and a fresh 132-case context anchor. Add a synthetic
overflow control. Bound preparation to 2 GiB group RSS, 8 GiB host reserve and
600 seconds, without weight tensors, inference context or forward. Require all
ordinary complete inputs within 4096 tokens. Do not shorten or pad options,
change references or replace projections to fit the model.

## Phases and fixed guards

| Phase | Dataset calls | Session ceiling | Technical requirement |
|---|---:|---:|---|
| Passage calibration | 12, four per axis | 600 s | Valid outputs, Clef identity, joint preparation/count match and live supervision; no accuracy gate |
| Fresh context anchor | 132 | 1,200 s | Collect full/132 and test/66 separately; no accuracy gate |
| Passage test | 728 | 1,200 s | Complete the fixed plan, retaining all unsuccessful statuses |

Calibration uses the same four lexicographically smallest physical call IDs
per axis as D3. No test output changes the phase order or budget. Technical
failure may stop progression; valid wrong choices cannot. Retain partial
attempts, with no retry or model/backend fallback.

Use the existing supervised upstream launcher with a new owned loopback
listener/process group per phase. Require actual Clef type and full-layer
Metal offload, context/batch/microbatch 4096, one slot/request/question,
30-second calls, no fitting or context shifting. Admit at **26 GiB available**
before weight hashing/loading; enforce **18 GiB group RSS + 8 GiB reserve**,
sampled every 250 ms. Do not stop unrelated workloads or lower a guard.
One prepared-input warm-up and auth/overflow controls per session are excluded
from dataset scores. The passage warm-up is the same fixed calibration input.
No new download or paid API is required.

The shared adapter rejects unprepared wire bytes before HTTP and a native
input-count mismatch after response. Physical-forward and truncation receipts
remain unknown when absent; count agreement does not compare live token IDs
or joint head order. Preserve original archives and stop owned sessions before
writing outer seals.

## Analysis and release boundary

Verify seals, hashes, score reconstruction and physical-to-logical expansion.
Report correct/scored/all, coverage, statuses, class confusion, macro class
accuracy, directions, views, scenarios and families for each task separately.
Pair outcomes with the sealed D3 Flash observations on matching identities;
do not tune a cascade from the exposed test cases or claim independent-sample
significance from correlated variants.

Report measured physical-call latency after excluded warm-up, session RSS
scope and unobserved GPU allocation. Do not invent extra timing/forwards for
reused logical decisions. A single sequential run is not a controlled speed
ranking or stable tail guarantee. No new ranking/nDCG, composition threshold,
retrieval, tool execution, final answer or product quality is evaluated.

Freeze plan/protocol, benchmark, helper, model and runtime bytes before any
prediction. Keep raw outputs, path-bearing receipts, sources and resource
samples in ignored local archives. Export only reviewed synthetic aggregates
and hashes. Human semantic review and any justified new reference version
remain separate; preserve v1 and never relabel it to improve a score.
