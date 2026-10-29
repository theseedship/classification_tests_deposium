# D3 Flash Q8: native passage evidence protocol

**Frozen before passage predictions, 29 October 2026.** Compare relevance,
claim support and answerability on the unchanged synthetic passage pack.
References and translations are agent-authored, pending human review. This
isolated model campaign does not qualify retrieval, executed tools, generated
answers or an application integration. Preserve all earlier archives and labels.

## Inputs and eligible denominators

Use `passage-evidence-v1` SHA-256
`35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476`.
The shared `select_pilot(test)` selects rotation 0, eight held-out families,
eight language directions and both `full`/`head_384` views: **128 pools**.
Directions are FR/EN/DE/ES/IT/PT monolingual plus FR→EN and EN→FR.
The prefix is 384 Unicode characters, not native token truncation.

Use the existing `export_requests`, `choice_plan`, `candidate_row`,
`observe_choice` and `score_choices`. Candidate-visible inputs contain only the
task's context, question and option descriptions, remapped to neutral keys.
Support exposes the candidate claim as required input. Do not send annotations,
gold labels, spans, family/split labels or descriptive identities.

| Axis | Logical decisions | Distinct physical calls | Output |
|---|---:|---:|---|
| Relevance | 512 | 264 | Four grades 0–3 |
| Support | 768 | 392 | supports / refutes / insufficient |
| Answerability | 128 | 72 | answerable / insufficient_visible_evidence / conflicting_visible_evidence |

Deduplicate only exact contract/input bytes, never a gold label. There are
**728 physical calls for 1,408 logical decisions**; reuse is not additional
independent evidence. Keep all missing, unsupported, error, timeout and abstain
outcomes in the original logical and physical denominators. Semantic
insufficiency is a valid choice, distinct from a technical abstention.

The primary comparison is the historical rotation-0 D3-lite observation on
these same pools. Jev's partial observation remains partial. Four-rotation
ranking results have different denominators and are not a matching-input
support baseline. No new reranker, composition threshold or ranking result is
claimed by this campaign.

## Model, runtime and preparation

Use existing local D3 Flash Q8 assets pinned by
`profiles/d3-flash-q8-assets.json`: repository `ggml-org/vllm-d3-flash-GGUF`,
revision `3d53d13778bf8035e6e1e534ce489ed052ee5663`, model SHA-256
`7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b`.
Native llama.cpp revision is `efe3626b119ff81033e309c3ba07a770bef2c546`;
binary SHA-256 is `d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1`.
Require a clean native source and actual full-layer Metal offload and D3 type.
Use the current separately fingerprinted preparation helper with explicit
`--decision-type d3`; Clef preparation does not qualify D3.

Audit all 728 test inputs, the 12 calibration canary inputs and a fresh
132-case context anchor, deduplicating identical wire bodies. Add a separate
synthetic overflow control. The vocabulary-only helper must load no tensors,
create no inference context and execute no forward. Require every ordinary
complete input within 4096 tokens, with exact body/token hashes. Bound
preparation to 2 GiB group RSS + 8 GiB host reserve and 600 seconds.
Do not shorten inputs, change options or reference labels to fit a limit.

## Fixed phases and guards

| Phase | Dataset calls | Session ceiling | Admission |
|---|---:|---:|---|
| Technical passage calibration | 12, four per axis | 600 s | Valid format, identity, prepared count and live supervision; no accuracy gate |
| Fresh context anchor | 132 | 1,200 s | Collect full/132 and test/66 separately; no accuracy gate |
| Passage test | 728 | 1,200 s | Complete fixed plan, including all unsuccessful statuses |

Canary selection is the four lexicographically smallest physical call IDs for
each axis in calibration; exact IDs and request-plan hashes are in the
[machine-readable plan](../plans/passage-flash-v1.json). No test prediction
selects a canary or changes a phase. A technical failure may stop progression;
a valid wrong choice cannot. Partial attempts remain archived without retry.

Each phase owns a new loopback listener and process group via
`scripts/run-upstream-native-pilot.py`. Use context/batch/microbatch 4096,
one slot/request/question, 30-second calls, no retries, fitting, context shifting
or model/backend fallback. Bound group RSS to **18 GiB**, host reserve to
**8 GiB**, admission to **26 GiB available** before weight hashing/loading,
and sample at 250 ms. Do not stop unrelated workloads or lower guards.
One prepared-input warm-up and auth/overflow controls per session are excluded
from dataset denominators; the passage warm-up is fixed calibration input.

The shared adapter rejects unprepared requests before HTTP and input-count
mismatch after a response. Native truncation and physical-forward receipts
remain unknown when absent. Count agreement does not compare live token IDs.
No paid API or new model download is required.

## Analysis and publication

Verify original seals, plan/input identities and physical-to-logical expansion.
Report correct/scored/all, coverage and statuses for each axis, class confusion,
macro class accuracy, language direction, view, scenario and family. Report
`full` and `head_384` separately. Correlated translations, views and repeated
inputs are not independent samples; eight test families do not justify a
population ranking or a calibrated cascade.

Record physical-call adapter/HTTP latency separately from logical decisions.
Per-pool composed costs, if derived, must state their reuse/accounting rule;
do not invent extra measured forwards. Session RSS includes startup, controls
and warm-up; it is not per-call RSS or total unified GPU allocation. Cold-start
timing, final-answer quality and live retrieval remain unqualified.

Freeze benchmark/helper/runtime bytes and the plan before prediction. Keep raw
outputs, sources, local paths and resource samples in new ignored archives.
Only reviewed synthetic aggregates, hashes and reports are eligible for the
public tree. A reference change needs explanation/review and a new dataset;
do not rewrite this protocol or plan in response to scores.
