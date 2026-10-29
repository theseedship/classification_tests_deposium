# Passage, length, and repeated timing results

[Back to full results](../RESULTS.md)

These tables consolidate published observations from October 2026. They cover
different protocols and must be read separately from the 132-case context-choice
leaderboard. This consolidation does not run new inference. References and
translations are synthetic and agent-authored, with human review still pending.

## Passage ranking and evidence

The evaluated test subset of the
[passage dataset](../../datasets/passage-evidence-v1/README.md) contains eight
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

Sources: [balanced D3/BGE report](../evidence/passage-order-control-20261015/report.md)
and [JSON](../evidence/passage-order-control-20261015/analysis.json);
[JeV report](../evidence/passage-jev-20261015/report.md)
and [JSON](../evidence/passage-jev-20261015/analysis.json).

## Support and answerability decisions

These decisions use only the **initial 128 passage cases**, not the four rotated
pools. Support classifies whether a passage supports, refutes, or is insufficient
for a claim. Answerability classifies whether the visible evidence permits an
answer, is insufficient, or conflicts.

| Candidate | Task | Correct / planned choices | OK coverage | Error / missing | Interpretation |
|---|---|---:|---:|---:|---|
| D3-lite CPU | Support | 443/768 | 768/768 | 0/0 | Complete observation |
| D3-lite CPU | Answerability | 88/128 | 128/128 | 0/0 | Complete observation |
| D3 Flash Q8/Metal | Support | 460/768 | 768/768 | 0/0 | Complete separate observation, 29 October 2026 |
| D3 Flash Q8/Metal | Answerability | 122/128 | 128/128 | 0/0 | Complete separate observation, 29 October 2026 |
| Clef Flash Q8/Metal | Support | 446/768 | 768/768 | 0/0 | Complete matched observation, 29 October 2026 |
| Clef Flash Q8/Metal | Answerability | 109/128 | 128/128 | 0/0 | Complete matched observation, 29 October 2026 |
| JeV 1.14.0 API | Support | 394/768 | 514/768 | 2/252 | Partial; missing/errors retained in denominator |
| JeV 1.14.0 API | Answerability | Unmeasured | 0/128 | 0/128 | No quality score; not run |

No `unsupported`, `timeout`, or `abstain` outcomes were recorded in these
rows. JeV's campaign stopped after 522/728 planned distinct HTTP attempts;
relevance observations were sufficient for ranking, but support was partial and
answerability remained unmeasured. The initial D3 campaign made 728 physical calls
for 1,408 logical choices; input reuse is not extra independent evidence.

Sources: [initial D3 report](../evidence/passage-cpu-20261015/report.md)
and [JSON](../evidence/passage-cpu-20261015/analysis.json);
[D3 Flash results and confusion matrices](../PASSAGE_FLASH_RESULTS_20261029.md)
and [aggregate](../evidence/passage-flash-20261029/analysis.json);
[matched Clef comparison](../PASSAGE_CLEF_RESULTS_20261029.md)
and [aggregate](../evidence/passage-clef-flash-20261029/analysis.json);
[JeV partial campaign](../evidence/passage-jev-20261015/report.md).

D3 Flash's four-grade relevance accuracy is separately 252/512; this does not
constitute a new ranking/nDCG result. Support improves only modestly in total
over D3-lite and macro class accuracy decreases: Flash mislabels 235/584
insufficient judgments as refutations and 63/584 as support. The answerability
gain does not qualify it as a factual verifier. Its separately measured timings
and resources are in the linked report; the historical CPU tables below remain
unchanged.

Clef's relevance classification is 261/512, not a new ranking/nDCG result.
Its answerability total masks 12/16 conflicting pools accepted as answerable;
class macro accuracy is 68.31%, versus D3 Flash's 97.73%. Paired outcomes and
both confusion matrices are in the matched comparison. Correlated views and
translations do not qualify an ensemble from the exposed test disagreements.

## Passage latency and memory

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
[initial JSON](../evidence/passage-cpu-20261015/analysis.json). These observations
do not establish a single memory requirement for the combined pipeline.

For support and answerability, the initial D3 report reconstructs median / p95
costs of **8.330 / 9.605 s** and **1.476 / 5.203 s**, respectively, across 128 pools.
These are additional operations, not included in ranking latency above.

## Longer contexts

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
[full length report](../evidence/length-comparison-20261004/report.md) for all
domain, language, and evidence-position intersections, and its
[JSON](../evidence/length-comparison-20261004/analysis.json) for runtime provenance
and status-specific timing distributions.

## Repeated timing and stability

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
[repeated timing report](../evidence/timing-comparison-20261004/report.md)
and [JSON](../evidence/timing-comparison-20261004/analysis.json).

## Initial documentary routing pilot

The earlier [14-case pilot](../JULIA_RESULTS.md) observed MCPs **14/14**, Julia
**10/14**, and Julia with reversed option order **9/14**, each fully scored.
Reversing the options changed **5/14** Julia decisions. These are seven correlated
French/English families and inherited train/calibration/test labels, not a balanced
held-out leaderboard. Its source traces and all later repeated measurements remain
separate historical observations.
