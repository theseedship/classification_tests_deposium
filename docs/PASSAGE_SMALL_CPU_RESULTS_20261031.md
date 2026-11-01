# Small CPU classifiers on passage evidence (rotation 0)

**1 November 2026 — four complete macOS CPU observations ([#52](https://github.com/theseedship/classification_tests_deposium/issues/52)).**
D3 lite, Vela 2.0 0.3B, D3 nano and D3 mini each answered the same 728
physical passage calls (1,408 logical decisions over 128 test pools) that D3
Flash Q8 and Clef Flash Q8 answered on Metal. Every call returned `ok`: zero
missing, error, timeout, abstain or worker restart. References and
translations remain synthetic, agent-authored and pending human review.

[Frozen protocol and amendments](PASSAGE_SMALL_CPU_PROTOCOL_20261031.md) ·
Aggregates: [D3 lite](evidence/passage-small-cpu-20261031/d3-lite.json),
[Vela 2.0 0.3B](evidence/passage-small-cpu-20261031/vela2-03.json),
[D3 nano](evidence/passage-small-cpu-20261031/d3-nano.json),
[D3 mini](evidence/passage-small-cpu-20261031/d3-mini.json) ·
[D3 Flash](PASSAGE_FLASH_RESULTS_20261029.md) · [Clef Flash](PASSAGE_CLEF_RESULTS_20261029.md) ·
[Historical D3-lite](PASSAGE_CPU_RESULTS_20261015.md) · [Roadmap status](CAMPAIGN_STATUS.md)

## Scores

Correct / all decisions. Each axis is a separate task; there is no combined score.

| Model · runtime | Relevance 0–3 | Claim support | Answerability |
|---|---:|---:|---:|
| **D3 mini · macOS CPU** | **266/512** | **527/768** | 104/128 |
| D3 nano · macOS CPU | 252/512 | 366/768 | 93/128 |
| D3 lite · macOS CPU (attempt 002) | 229/512 | 439/768 | 88/128 |
| Vela 2.0 0.3B · macOS CPU | 112/512 | 151/768 | 93/128 |
| *D3 Flash Q8 · Metal* | 252/512 | 460/768 | **122/128** |
| *Clef Flash Q8 · Metal* | 261/512 | 446/768 | 109/128 |
| *Historical D3-lite · Linux CPU* | 229/512 | 443/768 | 88/128 |
| *Constant majority class* | 224/512 (grade 1) | 584/768 (`insufficient`) | 88/128 (`answerable`) |

The classes are imbalanced: always answering `insufficient` on support would
score 584/768, more than every model's total. Totals alone therefore do not
rank these rows. Macro class accuracy weights each expected class equally
(a constant answer scores 25% on relevance and 33.3% on support and
answerability):

| Macro class accuracy | Relevance | Support | Answerability |
|---|---:|---:|---:|
| **D3 mini · macOS CPU** | 60.56% | **84.14%** | 80.68% |
| D3 nano · macOS CPU | **62.84%** | 76.79% | 86.74% |
| D3 lite · macOS CPU | 49.60% | 80.69% | 80.81% |
| Vela 2.0 0.3B · macOS CPU | 32.46% | 41.63% | 46.72% |
| *D3 Flash Q8 · Metal* | 59.06% | 79.79% | **97.73%** |
| *Clef Flash Q8 · Metal* | 60.40% | 81.09% | 68.31% |
| *Historical D3-lite · Linux CPU* | 49.60% | 80.92% | 80.81% |

Reading:

- **D3 mini** has the best relevance and support totals of the complete
  rotation-0 rows, including both Flash Q8 rows, and the best support macro
  score. Jev 1.14 is not in these tables: its relevance is published only as
  a four-rotation replay (1260/2048, 61.5%, a different protocol) and its
  rotation-0 support and answerability are partial. It does not match D3 Flash on answerability (104 vs 122/128): it
  misses 6 of 16 contradictions (`conflicting_visible_evidence` 62.5%).
- **D3 nano** has the best relevance macro score and a strong answerability
  macro (it catches every contradiction and every insufficient pool), but on
  support it answers `refutes` 387 times for 80 actual refutations and
  recognizes only 31% of `insufficient` claims.
- **D3 lite on macOS** reproduces the historical Linux D3-lite row almost
  exactly (relevance and answerability identical, support 439 vs 443).
- **Vela 2.0 0.3B** is close to chance on relevance and support: it labels
  674 of 768 claims `supports`, recognizes 6% of `insufficient` ones and never
  predicts relevance grade 1. Its answerability total is the majority-class
  baseline plus five.
- Every row, GPU or CPU, fails relevance grade 1 (partially relevant, 224
  decisions): 0–12% correct. This is a shared weakness of the projection or
  of the references, not of one model.

Correlated translations, two views (`full`, `head_384`) and eight families do
not justify a population confidence interval or significance test.

## Cost on the host

One run at a time on the same macOS CPU runtime lock; latency is per physical
call, RSS is the worker peak over the whole session.

| Model | Model phase | Median call | p95 | Max | Worker RSS peak |
|---|---:|---:|---:|---:|---:|
| Vela 2.0 0.3B | 2.3 min | 0.17 s | 0.21 s | 0.49 s | 1,233 MiB |
| D3 lite | 51 min | 3.7 s | 6.9 s | 19.5 s | 1,822 MiB |
| D3 nano | 1.95 h | 8.6 s | 15.9 s | 42.9 s | 3,511 MiB |
| D3 mini | 4.69 h | 20.2 s | 39.2 s | 111.2 s | 8,020 MiB |

D3 mini's slowest call (111 s) stayed under its 120 s per-call timeout. At
its median it costs about 2.5 minutes for a 7-passage pool with its claims,
which rules it out for interactive passage grading on this CPU.

## Attempts and boundaries

- **D3 lite attempt 001** completed 728/728 `ok` calls but is sealed as
  `incomplete` with stop reason `bench_source_changed`: the protocol
  amendment that raised D3 mini's wall budget changed one constant of the
  engine one minute after that run started. It stays unranked. Attempt 002 ran
  unchanged after D3 mini, with no engine change, and is the published row;
  its scores are identical to attempt 001's.
- Vela, nano and mini started after that amendment and ran to completion
  within their fixed budgets (1 h, 3 h, 6 h).
- Each macOS row is a separate runtime identity from the Linux historical
  row and from the Metal rows; same pools and request plans, different weights
  formats, runtimes and devices. Nothing is pooled.
- Only rotation 0 was run; the four-rotation relevance replay and the ranking
  projection remain historical D3-lite and Jev rows.
