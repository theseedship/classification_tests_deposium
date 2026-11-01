# Passage relevance v2: results

**1 November 2026 — D3 lite, nano and mini as Q8 on Apple Metal and Vela 2.0
0.3B on the macOS CPU runtime, on all 512 cases of the realigned relevance
pack.** Every answer `ok`. [Design and diagnosis](PASSAGE_RELEVANCE_V2_DESIGN_20261101.md) ·
[Pack](../datasets/passage-relevance-v2/README.md) ·
[Aggregate](evidence/review-packs-20261101/passage-relevance-v2.json) ·
[All results](RESULTS.md#passage-relevance-v2-three-levels)

| Model / runtime | Correct / 512 | TEST / 256 | Direct /112 | Partial /16 | No usable evidence /384 | Macro accuracy | v1 relevance /512 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D3 mini · Q8 Metal | 406 | 200 | 112 | 16 | 278 | 90.8% | 266 |
| D3 nano · Q8 Metal | 371 | 181 | 97 | 16 | 258 | 84.6% | 252 |
| D3 lite · Q8 Metal | 338 | 168 | 100 | 5 | 233 | 60.4% | 231 |
| Vela 2.0 0.3B · CPU | 113 | 59 | 55 | 3 | 55 | 27.4% | 112 |
| *Constant "no usable evidence"* | 384 | 192 | 0 | 0 | 384 | 33.3% | |

The v1 column is the four-grade projection on the full rotation-0 test pools
(512 logical decisions, duplicates included); it is shown for orientation,
not as a paired comparison.

## Reading

- With the undecidable 0/1 boundary removed, the D3 models separate clearly:
  D3 mini identifies every direct and every partial passage and classifies
  278/384 decoys and unrelated passages correctly (macro 90.8%).
- What remains is the intended difficulty: decoys that read like an answer.
  D3 mini still takes a near-identical entity ("Caldrin" for "Caldrin R"), a
  different rule for the same zone, or the same number for another subject
  for direct evidence; D3 lite misses partial evidence (5/16).
- The constant answer scores 384/512 but 33.3% macro: on this imbalanced pack
  only macro accuracy ranks the rows. Vela 2.0 0.3B is below the constant on
  both.
- The support and answerability projections were reviewed and kept; this
  pack only realigns relevance.

References are agent-authored and pending human review. Correlated languages
and views within families do not support a confidence interval.
