# D3 Flash Q8: passage relevance, support and answerability

**29 October 2026 — complete isolated Metal observation on 128 test pools.**
D3 Flash Q8 scored **252/512 relevance decisions**, **460/768 support
decisions** and **122/128 answerability decisions**. All were valid and scored.
References and translations are synthetic, agent-authored and pending human
review. These separate tasks do not qualify final answers or application quality.

[Aggregate, confusion matrices and groups](evidence/passage-flash-20261029/analysis.json) ·
[Frozen protocol](PASSAGE_FLASH_PROTOCOL_20261029.md) ·
[Frozen plan](../plans/passage-flash-v1.json) · [Roadmap status](CAMPAIGN_STATUS.md)

## Coverage and matching-input historical comparison

Selection: eight held-out families, eight language directions, both `full` and
`head_384`, rotation 0 only. This is the same dataset hash and declared pool
selection as the initial D3-lite CPU observation. It is not the later
four-rotation ranking experiment. Translations, views and repeated inputs are
correlated; 128 pools do not represent 128 independent facts.

The shared projection deduplicated 1,408 logical decisions into **728 distinct
physical calls**. Every planned physical call completed `ok`. Missing,
unsupported, error, timeout and abstain are zero for every axis. Semantic
insufficiency remains a valid choice, not a technical abstention. No task
denominator drops failures or combines the three axes into one accuracy.

| Task | Flash correct / scored / all | Historical D3-lite correct / all | Flash macro class accuracy | D3-lite macro |
|---|---:|---:|---:|---:|
| Relevance grades 0–3 | 252/512/512 | 229/512 | 59.06% | 49.60% |
| Claim support | 460/768/768 | 443/768 | 79.79% | 80.92% |
| Answerability | 122/128/128 | 88/128 | 97.73% | 80.81% |

The historical source is the [initial public D3-lite aggregate](evidence/passage-cpu-20261015/analysis.json).
No D3-lite inference or rescore was performed. The dataset and selection match;
exact historical request-byte identity is not independently attested by that
public aggregate. Different weights, runtime and device also prevent a causal
attribution to model size or a controlled speed ranking. Jev's historical
partial support and unmeasured answerability remain unchanged.

A separate fresh context anchor reached **124/132, test 61/66**, all scored.
The 12-call calibration canary had four fixed calls per axis and **12/12 valid
outputs**, zero quality cases scored and no accuracy gate. Neither canary nor
anchor enters the passage denominators. Three prepared-input warm-ups and
session auth/overflow controls are also excluded.

## Support: limited aggregate gain, important false decisions

| Authored support label | Flash correct / all | Historical D3-lite |
|---|---:|---:|
| supports | 94/104 | 102/104 |
| refutes | 80/80 | 80/80 |
| insufficient | 286/584 | 261/584 |

The total improves by 17 decisions, but macro class accuracy decreases.
Flash gains 25 correct insufficiency decisions while losing eight correct
support decisions. This is not a uniform improvement in evidence assessment.

Of **584 insufficient** reference judgments, Flash predicts **refutes for
235** and **supports for 63**. Of 104 supporting judgments it predicts refutes
for nine and insufficient for one. All 80 authored refutations are recognized.
With these references, absence of sufficient evidence is frequently treated
as a contradiction, and some unsupported claims are affirmed. This precludes
treating the measured model as a qualified factual verifier.

| View | Relevance correct / all | Support correct / all | Answerability correct / all |
|---|---:|---:|---:|
| full | 118/256 | 239/384 | 61/64 |
| head_384 | 134/256 | 221/384 | 61/64 |

The shorter view changes both visible evidence and its reference. Its higher
relevance score is not proof that truncating documents improves retrieval.
Cross-language support is **41/96** in each FR→EN and EN→FR direction; the six
monolingual directions range from 58/96 to 67/96. Every direction, view,
scenario, family and expected-class denominator is retained in the aggregate.

## Answerability and relevance limitations

Flash recognizes **82/88 answerable**, **24/24 insufficient** and **16/16
conflicting** pools. Its six errors are false conflict decisions on answerable
negation/exception cases, in ES, IT and PT, across both views. They belong to
one scenario family; they are not six independent failures of generalization.
No insufficient or conflicting pool was accepted as answerable in this run.
That finite observation is not a production false-acceptance guarantee.

For graded relevance, Flash recognizes **102/104 grade-3**, **16/32 grade-2**,
**0/224 grade-1** and **134/152 grade-0** judgments. Thematic-only passages are
assigned other grades throughout. The exact four-grade classification remains
weak despite strong answerability. No new ranking, nDCG, retained evidence set,
reranker composition, threshold or final answer was evaluated here.

## Actual runtime, timing and memory

Pinned upstream llama.cpp ran D3 Flash Q8 with **33/33 layers offloaded to
Metal**, decision type `vllm-d3`, on Apple M5 Pro / 64 GiB unified memory.
Each phase owned a fresh loopback listener and process group. Context, batch
and microbatch were 4096, with one slot/request/question, 30-second calls,
no retry, context shifting, fitting or model/backend fallback. No paid model
API or new model download was used.

| Task | Distinct physical calls | Adapter median ms | Adapter p95 ms |
|---|---:|---:|---:|
| Relevance | 264 | 200.0 | 294.1 |
| Support | 392 | 200.8 | 293.7 |
| Answerability | 72 | 278.2 | 748.7 |
| All physical calls | 728 | 200.9 | 295.2 |

Durations cover the passage observer's actual adapter calls, after a separate
excluded warm-up. They exclude loading/startup and do not invent a timing for
each reused logical decision. Median uses the central-pair midpoint and p95
nearest rank, over one ordered pass. Cold-start and stable-tail performance
are unqualified; no cross-device speed comparison is claimed.

The passage session's sampled process-group RSS peak was **9.45 GiB**; its
minimum available-memory estimate was **21.03 GiB**. The fixed envelope was
18 GiB RSS plus an 8 GiB reserve, sampled every 250 ms, with a 1,200-second
session ceiling. No guard stopped any phase. RSS includes startup, controls and
warm-up; it is not per-call RSS, a memory floor or total unified GPU allocation.
GPU allocation remains separately unreported. The macOS available-memory
estimate is not Linux `MemAvailable`. All owned sessions were stopped before
their outer seals were written.

## Preparation, integrity and validation

Before predictions, **872 distinct inputs** prepared successfully: 728 test
calls, 12 calibration calls and 132 context-anchor inputs. Native token counts
were **128–1,026**, below 4096; a separate oversized synthetic input was
rejected. The vocabulary-only helper used no tensors, inference context or
forward. Its sampled RSS peak was 165.64 MiB under the separate
2 GiB/8 GiB/600-second envelope.

All **728/728 passage responses** matched exact prepared request-body hashes
and native input counts. The archive verifier reconstructed every logical
prediction from its sealed physical response and reproduced the saved scores
with the shared scorer. Task-specific contexts/questions/options alone reached
the native endpoint. Annotations, golds, spans, splits and descriptive case IDs
were absent. Native truncation and physical-forward receipts remain unknown;
count agreement does not compare live token IDs.

| Identity | Revision or SHA-256 |
|---|---|
| Passage dataset | `35a8b8982d12959985218b5bc6e10e932ba30970bd7ab9a81c6f10d17a7fe476` |
| D3 Flash GGUF revision | `3d53d13778bf8035e6e1e534ce489ed052ee5663` |
| Q8_0 model | `7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b` |
| llama.cpp revision | `efe3626b119ff81033e309c3ba07a770bef2c546` |
| Native binary | `d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1` |
| Preparation helper | `42ea3604621a346818bbc27a55488ad411fbb508326d178226305638f3d4e97b` |
| Public benchmark base | `501f0963077a787dfea6168330dde9754affd3e7` plus recorded local changes |

The plan/protocol, source, helper dependencies, runtime and weights were checked
before inference. Dataset and scorer sources stayed unchanged. Original seals,
projection hashes, raw/score hashes and the historical public aggregate hash
are retained in the new public aggregate. This establishes recorded byte
integrity, not human semantic approval or independent certification. Raw
outputs, local paths, sources and resource samples remain in ignored archives.

Offline validation ran **71 tests: 70 passed, one optional check skipped**,
including negative scorer controls and supervised native three/four-choice
projections. The corpus regenerated byte for byte. These checks are distinct
from the real model campaign; a skip is not successful qualification. The
known full macOS suite failures were not rerun for reporting changes.

## Roadmap implication

The stronger candidate substantially improves answerability on this pack but
does not resolve support classification or graded relevance. The next useful
comparison is Clef Flash on these same pools under a separately frozen native
protocol. Review insufficient-versus-refuted semantics with human annotators
before proposing any reference revision. Preserve v1 and these results; do not
relabel observed errors to improve a score. Executable tool episodes and
end-to-end retrieval-to-answer evaluation remain separate future work.
