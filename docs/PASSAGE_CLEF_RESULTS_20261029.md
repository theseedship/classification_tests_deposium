# Clef Flash Q8: matched passage comparison with D3 Flash

**29 October 2026 — complete isolated Clef Flash Q8/Metal observation.**
Clef scored **261/512 relevance**, **446/768 support** and **109/128
answerability** decisions, all valid and scored. References and translations
remain synthetic, agent-authored and pending human review. These are separate
tasks, not a single score or a qualification of factual or product quality.

[Aggregate, paired outcomes and confusion matrices](evidence/passage-clef-flash-20261029/analysis.json) ·
[Frozen Clef protocol](PASSAGE_CLEF_PROTOCOL_20261029.md) ·
[Frozen plan](../plans/passage-clef-flash-v1.json) ·
[D3 Flash observation](PASSAGE_FLASH_RESULTS_20261029.md) · [Roadmap status](CAMPAIGN_STATUS.md)

## Scores, coverage and comparison boundary

The task inputs are exactly those of the completed D3 Flash observation:
128 test pools, eight families, eight language directions, `full` and
`head_384`, rotation 0. Logical and physical request-plan bytes match. Candidate
aliases and model-specific native renderings differ. The dataset, projections,
option order, scorer and resource envelope were unchanged; no D3 error selected
or relabeled a Clef test case.

| Task | Clef correct / scored / all | D3 Flash correct / all | Historical D3-lite correct / all |
|---|---:|---:|---:|
| Relevance grades 0–3 | 261/512/512 | 252/512 | 229/512 |
| Claim support | 446/768/768 | 460/768 | 443/768 |
| Answerability | 109/128/128 | 122/128 | 88/128 |

All **728/728 distinct physical calls** completed `ok`, expanding to 1,408
logical decisions. Every axis has zero missing, unsupported, error, timeout
and abstain outcomes. Reuse does not add independent evidence. Semantic
insufficiency is a valid choice, distinct from technical abstention.

A separate fresh Clef context anchor scored **110/132, test 59/66**, matching
the earlier Clef totals without establishing bitwise reproduction. The fixed
calibration canary had **12/12 valid calls**, zero quality cases scored and no
accuracy gate. Canary, anchor, three prepared-input warm-ups and synthetic
session controls are excluded from passage scores.

The native D3 comparison uses verified original seals and the same task-input
bytes. Its saved scores were reconstructed with the unchanged shared scorer
as an integrity check; no new D3 inference or archive modification occurred.
The historical D3-lite aggregate matches the dataset and pool selection but
does not independently attest exact historical request bytes. It used different
weights, runtime and device. Jev's partial historical results remain unchanged.

| Macro class accuracy | Clef Flash | D3 Flash | Historical D3-lite |
|---|---:|---:|---:|
| Relevance | 60.40% | 59.06% | 49.60% |
| Support | 81.09% | 79.79% | 80.92% |
| Answerability | 68.31% | 97.73% | 80.81% |

Macro averages weight expected classes equally; totals reflect the actual
class distribution. Clef's higher answerability total than D3-lite therefore
coexists with a lower macro score. No single aggregate establishes a general
winner. Correlated translations/views and eight families do not justify a
population confidence interval or independent-sample significance test.

## Answerability: missed contradictions dominate

| Authored pool label | Clef correct / all | D3 Flash correct / all |
|---|---:|---:|
| answerable | 85/88 | 82/88 |
| insufficient_visible_evidence | 20/24 | 24/24 |
| conflicting_visible_evidence | 4/16 | 16/16 |

Clef accepts **12/16 conflicting pools** and **4/24 insufficient pools** as
answerable. Its other three errors label answerable pools insufficient. D3
Flash's six errors instead label answerable negation/exception pools as
conflicting; it accepted no insufficient/conflicting pool in this run.
These finite, agent-referenced observations do not establish production
acceptance guarantees or semantic truth.

Clef gets all 16 negation/exception pools correct, including the six missed by
D3. It misses cases in conflict, absent evidence, distributed proof and the
prefix-cut scenario. The complete scenario/language breakdown remains in the
aggregate; no observed error changed a reference or budget.

## Support and graded relevance remain weak

| Authored support label | Clef correct / all | D3 Flash correct / all |
|---|---:|---:|
| supports | 102/104 | 94/104 |
| refutes | 80/80 | 80/80 |
| insufficient | 264/584 | 286/584 |

Clef gains eight supporting judgments but loses 22 insufficiency judgments,
for 14 fewer correct decisions overall. Of the 584 insufficient judgments it
predicts **refutes for 237** and **supports for 83**, versus 235 and 63 for D3
Flash. Its higher support macro score does not resolve those confusions.
Neither observation qualifies the model as a factual verifier.

Clef recognizes relevance grades **3: 102/104**, **2: 18/32**, **1: 26/224**
and **0: 115/152**. The grade-1 result exceeds D3's 0/224, but most thematic-only
judgments remain wrong, and Clef loses 19 correct grade-0 decisions. The total
gain of nine relevance judgments is not evidence of better ranking or retrieval.

| View | Clef relevance | Clef support | Clef answerability |
|---|---:|---:|---:|
| full | 126/256 | 229/384 | 54/64 |
| head_384 | 135/256 | 217/384 | 55/64 |

`head_384` changes visible evidence and its reference. It is a 384-character
prefix, not native token truncation, and a higher relevance score does not
establish that cutting documents improves retrieval. All eight language
directions and family/scenario/class denominators are retained in the aggregate.

## Paired correctness on identical tasks

| Axis | Both correct | D3 only correct | Clef only correct | Both incorrect | All logical decisions |
|---|---:|---:|---:|---:|---:|
| Relevance | 231 | 21 | 30 | 230 | 512 |
| Support | 394 | 66 | 52 | 256 | 768 |
| Answerability | 103 | 19 | 6 | 0 | 128 |

Choice agreement is separately **427/512**, **642/768** and **103/128**.
Agreement is not correctness. The absence of a shared incorrect answerability
case here does not supply a rule to choose the correct model on disagreements.
An oracle using the exposed references is not an executable ensemble or a
qualified cascade; fresh held-out families would be required for such work.

## Native execution, speed and resources

Clef Flash Q8 ran through the real pinned upstream native listener, with
**33/33 layers on Metal**, decision type `clef`, Apple M5 Pro / 64 GiB unified
memory. Each phase owned a new loopback listener/process group. Context, batch
and microbatch were 4096; one slot/request/question, 30-second calls, no retry,
fitting, context shifting or model/backend fallback. No paid model API or new
download was used. No application routing or service was modified.

| Axis | Distinct physical calls | Adapter median ms | Adapter p95 ms |
|---|---:|---:|---:|
| Relevance | 264 | 202.1 | 376.2 |
| Support | 392 | 201.2 | 374.1 |
| Answerability | 72 | 282.3 | 864.7 |
| All physical calls | 728 | 202.0 | 376.2 |

These are passage-observer adapter-call durations after an excluded warm-up,
not a timing for every reused logical decision. Loading/startup is excluded.
Median uses the central-pair midpoint and p95 nearest rank. This sequential
single-pass comparison is not a controlled speed ranking, cold-start measure
or stable-tail guarantee.

Sampled process-group RSS peaked at **10.40 GiB**, with minimum available-memory
estimate **20.89 GiB**. The unchanged envelope was 18 GiB RSS plus 8 GiB reserve,
250 ms sampling and 1,200 seconds for the test session. No resource guard
stopped a phase. RSS includes startup, controls and warm-up; it is not per-call
RSS, a memory requirement or total unified GPU allocation. GPU allocation is
separately unknown; the macOS estimate is not Linux `MemAvailable`. All owned
sessions were stopped before outer seals were written.

## Joint preparation, identity and verification

The native helper prepared **872 distinct ordinary inputs**, from **183 to
1,068 tokens**, and rejected a synthetic overflow control. It selected the real
Clef `fill_task_joint` path and checked token/decision-order hashes and native
score counts. Its sampled RSS peak was 164.81 MiB under the separate
2 GiB/8 GiB/600-second envelope, without weight tensors, inference context or
forward. All 50 recorded helper dependency files were verified.

All **728/728 test responses** matched prepared request-body hashes and native
input counts. The campaign includes actual **264 four-option and 464 three-option
test requests**, following live technical admission. Only task-specific allowed
inputs reached the model. Golds, spans, annotations, split/family labels and
descriptive case IDs were absent. Live token IDs and joint head order were not
independently compared; truncation and physical-forward receipts remain unknown.

| Identity | Revision or SHA-256 |
|---|---|
| Passage dataset | `35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476` |
| Clef Flash GGUF revision | `6e2a164d70aae2af7fce86005da3f91805565b1d` |
| Q8_0 model | `25f801e2a27610b0ccc0cb1558d7eda3d7a304e34e2c4a04e3079357ff7d906e` |
| llama.cpp revision | `efe3626b119ff81033e309c3ba07a770bef2c546` |
| Native binary | `d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1` |
| Preparation helper | `42ea3604621a346818bbc27a55488ad411fbb508326d178226305638f3d4e97b` |
| Public benchmark base | `501f0963077a787dfea6168330dde9754affd3e7` plus recorded local changes |

Weights, model-specific preparation, sources, plan/protocol and runtime were
verified before prediction. The verifier checked original seals and reconstructed
physical-to-logical predictions and scores for both native observations. The
public aggregate retains safe model/source/plan, raw/score and comparison
fingerprints. These are byte-integrity records, not independent certification
or human semantic approval. Raw outputs, local paths, sources and samples stay
in ignored archives. The exact Cloudflare revision converted to GGUF is not
attested; BF16/PyTorch, CUDA, vision, generation and Clef 27B remain unqualified.

Five targeted native-launcher tests passed before this campaign. The unchanged
shared passage/scoring/supervision tests had passed before D3 (70 passed, one
optional skip). Reporting changes do not claim a new full macOS suite PASS;
its known failures remain documented in the checkpoint.

## Roadmap implication

This matching-input lot is complete for both Flash models. D3 Flash is the
stronger observed answerability candidate on this pack; the modest relevance
differences and mixed class tradeoffs do not qualify either as a general
evidence verifier. Human review of class boundaries and new independently
held-out scenarios have more value than repeating these same cases to tune a
winner. Preserve v1, every prediction and the frozen original capability cohort.
Executable arguments/tool episodes and full retrieval-to-answer quality remain
separate future work; no new reranker, nDCG or composed evidence gate was tested.
