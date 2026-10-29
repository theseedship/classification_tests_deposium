# Full results

[README](../README.md) · [Quality](#model-quality) · [Language and task complexity](#language-and-task-complexity) ·
[Updated task rankings](#updated-task-rankings) · [New capability tests](#complementary-capability-campaign-29-october-2026) · [Speed and memory](#speed-and-memory) · [Passages and other campaigns](leaderboard/other-benchmarks.md) ·
[Other evaluated protocols](#other-evaluated-protocols) · [Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)

**30 context model/runtime observations through 29 October 2026**: 28 historical observations plus Clef Flash Q8 and the direct upstream D3 Flash Q8 runtime.
Rows identify observations, not independent model families. Gateway-backed and direct native binaries remain distinct. Repeated exports of the same sealed run are deduplicated;
quantizations and devices remain separate. Rendering this page does not rerun or rescore models.

**Exploratory evidence:** synthetic, agent-authored references and translations await human review.
The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.
FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.

## What was actually tested?

| Task | Common input and denominator | Status |
|---|---|---|
| Documentary text and choices | 76 context-dependent choices | Scored exploratory decisions |
| Mathematics / chemistry | 28 / 28 constrained choices | Scored synthetic probes, not expert scientific qualification |
| Clef Flash Q8 context, capabilities and physics | Separate 132-, 192- and 48-case packs | Included in the context table and updated task rankings below; [report](CLEF_FLASH_RESULTS_20261029.md) |
| First tool proposal | 24 search / statistics / fallback choices | Provisional agreement only; no tool execution; **0 semantically qualified cases** |
| Physics | [48 synthetic choices](../datasets/physics-choice-v1/README.md), 24 FR/EN families | [Flash Q8/direct Metal: 39/48, test 32/36](PHYSICS_FLASH_RESULTS_20261029.md); reported separately, human review pending |
| Passage ranking, relevance, support, answerability | Separate fixed-passage campaigns | [Full tables and coverage](leaderboard/other-benchmarks.md); [D3 Flash evidence observation](PASSAGE_FLASH_RESULTS_20261029.md) and [matched Clef comparison](PASSAGE_CLEF_RESULTS_20261029.md), reported separately |
| Capability/tool-set, argument and fixed-observation choices | [192-case complementary pack](../datasets/capability-choice-v1/README.md) | [First D3 Flash Q8/Metal campaign and fresh context anchor](CAPABILITY_FLASH_RESULTS_20261029.md), reported separately from the 28 historical rows; no tool execution or product qualification |
| Free-form plugin/MCP selection, complete execution loop, difficulty prediction, adaptive model routing | Future harness stages | **Not run**; [experiment design](INTENT_AND_MODEL_ROUTING.md) |
| End-to-end RAG and generated-answer quality | No campaign qualified here | **Not run** |

## Updated task rankings

These tables include the published D3/Clef campaigns through 29 October 2026. Each task has its own ranking and denominator; there is no pooled cross-task score. Ranks use correct/all among completely scored observations on the same task/denominator. Partial and unrun campaigns remain visible but unranked. Ties share competition ranks. Canaries and repeated context anchors do not add quality cases.

### Capability choices

| Rank all | Rank test | Model / execution path | Correct / all | Scored / all | Test correct / all | Source |
|---:|---:|---|---:|---:|---:|---|
| 1 | 1 | Clef Flash Q8 · direct Metal | 192/192 | 192/192 | 96/96 | [Report](CLEF_FLASH_RESULTS_20261029.md) |
| 1 | 1 | D3 Flash Q8 · gateway Metal | 192/192 | 192/192 | 96/96 | [Report](CAPABILITY_FLASH_RESULTS_20261029.md) |

Both candidates reach the ceiling on these supplied proposals; this does not qualify executable tools. D3 uses the earlier gateway-backed runtime; Clef uses the direct native listener.

| Model | Track | Correct / all | Test correct / all |
|---|---|---:|---:|
| Clef Flash Q8 · direct Metal | Capability selection | 64/64 | 32/32 |
| Clef Flash Q8 · direct Metal | Arguments and dependencies | 64/64 | 32/32 |
| Clef Flash Q8 · direct Metal | Next step after fixed observations | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Capability selection | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Arguments and dependencies | 64/64 | 32/32 |
| D3 Flash Q8 · gateway Metal | Next step after fixed observations | 64/64 | 32/32 |

### Physics choices

| Rank all | Rank test | Model / execution path | Correct / all | Scored / all | Test correct / all | Source |
|---:|---:|---|---:|---:|---:|---|
| 1 | 2 | Clef Flash Q8 · direct Metal | 41/48 | 48/48 | 31/36 | [Report](CLEF_FLASH_RESULTS_20261029.md) |
| 2 | 1 | D3 Flash Q8 · direct Metal | 39/48 | 48/48 | 32/36 | [Report](PHYSICS_FLASH_RESULTS_20261029.md) |

Clef has the higher full total; D3 has the higher held-out test score. Calibration and test are therefore shown separately; neither result establishes general physics expertise.

### Passage relevance

Rotation 0: 128 pools, eight families, eight language directions, two correlated views.

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | Clef Flash Q8 · direct Metal | 261/512 | 512/512 | 60.40% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 2 | D3 Flash Q8 · direct Metal | 252/512 | 512/512 | 59.06% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 3 | D3-lite · CPU | 229/512 | 512/512 | 49.60% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |

### Claim support

Rotation 0: 128 pools, eight families, eight language directions, two correlated views.

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | D3 Flash Q8 · direct Metal | 460/768 | 768/768 | 79.79% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 2 | Clef Flash Q8 · direct Metal | 446/768 | 768/768 | 81.09% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 3 | D3-lite · CPU | 443/768 | 768/768 | 80.92% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |
| — | Jev 1.14 · API | 394/768 | 514/768 | 90.05% | partial; [report](PASSAGE_JEV_RESULTS_20261015.md) |

### Answerability

Rotation 0: 128 pools, eight families, eight language directions, two correlated views.

| Rank | Model / runtime | Correct / all | Scored / all | Macro class accuracy | Observation |
|---:|---|---:|---:|---:|---|
| 1 | D3 Flash Q8 · direct Metal | 122/128 | 128/128 | 97.73% | complete; [report](PASSAGE_FLASH_RESULTS_20261029.md) |
| 2 | Clef Flash Q8 · direct Metal | 109/128 | 128/128 | 68.31% | complete; [report](PASSAGE_CLEF_RESULTS_20261029.md) |
| 3 | D3-lite · CPU | 88/128 | 128/128 | 80.81% | complete; [report](PASSAGE_CPU_RESULTS_20261015.md) |
| — | Jev 1.14 · API | Not run | 0/128 | NR | not_run; [report](PASSAGE_JEV_RESULTS_20261015.md) |

Class macro accuracy averages the scored class accuracies. Jev's partial support macro is conditional on its observed subset and is not a complete-coverage comparison; unobserved decisions remain missing in the totals.

Jev's published relevance export is **1260/2048**, scored 2048/2048, over four rotations. It is retained in the downloads as `passage_relevance_four_rotations`, outside the 512-decision relevance ranking. Replayed rotations are not extra independent model calls.

Support insufficiency/refutation remains weak for both Flash candidates. Clef accepts 12/16 pools annotated as conflicting as answerable; D3 accepts none in this finite run. See [paired outcomes and confusion matrices](PASSAGE_CLEF_RESULTS_20261029.md). This is not factual-verifier or end-to-end qualification.

### Campaign latency and memory

Physical-call timings are kept separate from reused logical decisions; session RSS scopes differ from the historical context + tool sessions. NR means unreported. No controlled speed ranking is inferred.

| Model / runtime | Task | Timed calls | Median ms | p95 ms | Session RSS GiB |
|---|---|---:|---:|---:|---:|
| Clef Flash Q8 · direct Metal | capability | 192 | 616.9 | 953.5 | 10.60 |
| D3 Flash Q8 · gateway Metal | capability | 192 | 576.9 | 985.8 | 9.48 |
| D3 Flash Q8 · direct Metal | passage_answerability | 72 | 278.2 | 748.7 | 9.45 |
| Clef Flash Q8 · direct Metal | passage_answerability | 72 | 282.3 | 864.7 | 10.40 |
| Clef Flash Q8 · direct Metal | passage_relevance | 264 | 202.1 | 376.2 | 10.40 |
| D3 Flash Q8 · direct Metal | passage_relevance | 264 | 200.0 | 294.1 | 9.45 |
| D3 Flash Q8 · direct Metal | passage_support | 392 | 200.8 | 293.7 | 9.45 |
| Clef Flash Q8 · direct Metal | passage_support | 392 | 201.2 | 374.1 | 10.40 |
| Clef Flash Q8 · direct Metal | physics | 48 | 196.7 | 211.7 | 9.55 |
| D3 Flash Q8 · direct Metal | physics | 48 | 193.7 | 202.1 | 9.36 |

[Campaign summary CSV](leaderboard/campaigns.csv) and [task breakdown CSV](leaderboard/task-breakdown.csv) contain denominators, statuses and all exported groups. Ranking/nDCG, longer contexts and repeated timing retain their separate protocols in [other campaigns](leaderboard/other-benchmarks.md). Clef 27B and the six remaining original cohort candidates remain unrun on the new packs.

## Complementary capability campaign: 29 October 2026

**D3 Flash Q8**, nominal 9B class, llama.cpp / Metal. The two full packs have separate denominators; canary calls are excluded.
References remain agent-authored and pending human review. A perfect closed-choice score does not qualify tool execution or product behavior.

| Pack / track | Correct / all | Scored / all | Test correct / all |
|---|---:|---:|---:|
| Fresh context anchor | 124/132 | 132/132 | 61/66 |
| Capability pack | 192/192 | 192/192 | 96/96 |
| Capability selection | 64/64 | 64/64 | 32/32 |
| Arguments and dependencies | 64/64 | 64/64 | 32/32 |
| Next step after fixed observations | 64/64 | 64/64 | 32/32 |

The three track rows partition the 192-case pack; they are not additional cases. The fresh anchor has 66 FR/EN families. The new pack's 192 language/catalogue variants belong to 48 families, including 24 test families.

| Pack | French correct / all | English correct / all | 8-card correct / all | 32-card correct / all |
|---|---:|---:|---:|---:|
| Fresh context anchor | 62/66 | 62/66 | Not applicable | Not applicable |
| Capability pack | 96/96 | 96/96 | 96/96 | 96/96 |

| Pack | Timed successful calls / all | Adapter median ms | Adapter p95 ms | Session group RSS GiB |
|---|---:|---:|---:|---:|
| Fresh context anchor | 132/132 | 196.3 | 204.3 | 9.38 |
| Capability pack | 192/192 | 576.9 | 985.8 | 9.48 |

Timings follow each session's synthetic warm-up and describe one pass; loading/startup is excluded. RSS is the sampled owned process-group peak over startup, smoke and that pack, not per-case RSS or total unified GPU memory. GPU allocation was unreported. Catalogue variants are correlated.
[Full campaign report](CAPABILITY_FLASH_RESULTS_20261029.md) · [Groups, pairs and source evidence](evidence/capability-flash-20261029/analysis.json). Historical source exports remain unchanged; the consolidated context ranks below include the new observations.

## Model quality

Each score is **correct / all cases** in its column, retaining failures in the denominator.
Tool is **agreement / 24 provisional proposals**, not routing accuracy. Full scored/valid counts and separate
`missing`, `unsupported`, `error`, `timeout`, and `abstain` counts are in the downloads.
Equal all-case totals share a competition rank; row order within a tie is alphabetical by observation ID.

| Rank all | Rank test | Model observation | Size¹ | Runtime² | All /132 | Test /66 | Text /76 | Math /28 | Chem /28 | Tool /24 |
|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 1 | D3 historical · Q4 Metal | 27B class | Metal | 128 | 65 | 73 | 28 | 27 | 24 |
| 2 | 4 | D3 flash · Q8 Metal | 9B class | Metal | 124 | 61 | 72 | 26 | 26 | 20 |
| 2 | 4 | D3 flash · Q8 direct Metal | 9B class | Metal-U | 124 | 61 | 72 | 26 | 26 | Not run |
| 2 | 4 | D3 flash · CPU | 8.393B backbone | CPU-H | 124 | 61 | 72 | 26 | 26 | 20 |
| 5 | 3 | Jev 1.13 · HTTP API | NR | API | 123 | 62 | 67 | 28 | 28 | 20 |
| 6 | 9 | D3 flash · Q4 Metal | 9B class | Metal | 122 | 59 | 71 | 24 | 27 | 21 |
| 7 | 8 | D3 mini · CPU | 4.539B backbone | CPU-H | 119 | 60 | 71 | 24 | 24 | 20 |
| 8 | 4 | D3 nano · CPU | 2.213B backbone | CPU-H | 117 | 61 | 68 | 26 | 23 | 18 |
| 8 | 2 | GLiClass v4 9B · BF16 MPS | 9B class | MPS | 117 | 63 | 70 | 24 | 23 | 20 |
| 10 | 9 | Clef Flash · Q8 direct Metal | 9B class | Metal-U | 110 | 59 | 63 | 25 | 22 | Not run |
| 11 | 11 | Vela 2.0 4B · CPU | 4.211B | CPU-H | 106 | 56 | 64 | 20 | 22 | 18 |
| 12 | 12 | Decision 2.0 Nox 4B · CPU | 4.208B | CPU-H | 103 | 55 | 54 | 25 | 24 | 18 |
| 13 | 12 | Liquid d1-3B · CPU | 3.123B | CPU-H | 101 | 55 | 60 | 21 | 20 | 16 |
| 14 | 14 | Noma · CPU | ~2.67B declared | CPU-H | 98 | 51 | 53 | 25 | 20 | 18 |
| 15 | 15 | D3 lite · CPU | 0.853B backbone | CPU-H | 95 | 50 | 64 | 15 | 16 | 19 |
| 16 | 16 | Decision 2.0 Sol 2B · CPU | 2B class | CPU-H | 93 | 47 | 62 | 19 | 12 | 19 |
| 17 | 17 | Vela 2.0 0.8B · CPU | 0.755B declared | CPU-H | 79 | 45 | 56 | 11 | 12 | 14 |
| 18 | 18 | Decision 2.0 Eos 0.8B · CPU | 0.8B class | CPU-H | 77 | 40 | 55 | 12 | 10 | 19 |
| 18 | 18 | Decision 2.0 Eos 0.8B · Q8 Metal | 0.8B class | Metal | 77 | 40 | 55 | 12 | 10 | 19 |
| 20 | 21 | D3 edge · CPU | 0.594B backbone | CPU-H | 74 | 37 | 48 | 12 | 14 | 18 |
| 21 | 23 | Decision 2.0 Kai 0.6B · CPU | 0.6B class | CPU-H | 70 | 36 | 56 | 7 | 7 | 16 |
| 22 | 21 | Vela 2.0 0.3B · CPU | 0.309B declared | CPU-H | 65 | 37 | 52 | 4 | 9 | 18 |
| 23 | 20 | GLiNER2.5-multi-Decide · CPU | NR | CPU-H | 59 | 38 | 41 | 5 | 13 | 12 |
| 24 | 25 | Vela 3.0 fast · decision only · CPU | 0.380B decision backbone | CPU-N | 57 | 28 | 43 | 9 | 5 | 18 |
| 25 | 24 | Laya multilingual · CPU | 322M declared | CPU-H | 56 | 30 | 42 | 8 | 6 | 10 |
| 26 | 26 | Julia-1 · CPU | NR | CPU-H | 52 | 26 | 32 | 8 | 12 | 11 |
| 27 | 26 | Liquid d1-omni-600M · CPU | 600M class | CPU-H | 51 | 26 | 39 | 4 | 8 | 16 |
| 28 | 29 | Indecis · untrained open mode · CPU | NR | CPU-H | 44 | 22 | 32 | 2 | 10 | 11 |
| 29 | 28 | ModernJEV-Decide-Preview · CPU | NR | CPU-H | 42 | 23 | 23 | 13 | 6 | 8 |
| 30 | 30 | Muose-50M-Decision · CPU | 50M class | CPU-H | 41 | 21 | 30 | 6 | 5 | 10 |

¹ Sizes describe the observed checkpoint: exact tensor counts, nominal classes, and publisher declarations
are distinguished in [metadata](leaderboard/model-metadata.json). A backbone count may exclude a separate readout;
some counts include vision weights. **NR** means not reported in the selected public evidence, not zero.
The historical 27B D3 is neither an Ultra nor a Turbo observation; neither variant was evaluated here.

² CPU-H: historical Linux/WSL CPU runs (processor not identified here); API: remote service with unknown server hardware;
Metal: native llama.cpp on Apple M5 Pro; MPS: official PyTorch pipeline on Apple M5 Pro;
CPU-N: newer macOS CPU run; Metal-U: direct upstream native listener, separate from gateway-backed historical runs. Runtime, readout, serializer, precision, and input lengths differ.
Not run in the tool column means no 24-case first-tool observation was published for that runtime; it is not zero accuracy. Later passage anchors reproduce the published D3 124/132 (test 61/66) and Clef 110/132 (test 59/66) totals; those repeated checks are not additional leaderboard models.

## Language and task complexity

D1/D2/D3 are authored context-task strata, **not predictions of difficulty or evidence that escalation helps**.
A correct choice also does not prove that a plugin was executed or a useful answer generated.

| Model observation | FR /66 | EN /66 | D1 /40 | D2 /40 | D3 /52 | Scored /132 | Tool valid /24 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D3 historical · Q4 Metal | 64 | 64 | 40 | 38 | 50 | 132 | 24 |
| D3 flash · Q8 Metal | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| D3 flash · Q8 direct Metal | 62 | 62 | 39 | 37 | 48 | 132 | Not run |
| D3 flash · CPU | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| Jev 1.13 · HTTP API | 62 | 61 | 36 | 38 | 49 | 132 | 24 |
| D3 flash · Q4 Metal | 62 | 60 | 39 | 37 | 46 | 132 | 24 |
| D3 mini · CPU | 60 | 59 | 40 | 38 | 41 | 132 | 24 |
| D3 nano · CPU | 58 | 59 | 37 | 38 | 42 | 132 | 24 |
| GLiClass v4 9B · BF16 MPS | 58 | 59 | 39 | 35 | 43 | 132 | 24 |
| Clef Flash · Q8 direct Metal | 55 | 55 | 36 | 36 | 38 | 132 | Not run |
| Vela 2.0 4B · CPU | 52 | 54 | 38 | 33 | 35 | 132 | 24 |
| Decision 2.0 Nox 4B · CPU | 50 | 53 | 32 | 31 | 40 | 132 | 24 |
| Liquid d1-3B · CPU | 50 | 51 | 29 | 30 | 42 | 132 | 24 |
| Noma · CPU | 46 | 52 | 35 | 26 | 37 | 132 | 24 |
| D3 lite · CPU | 45 | 50 | 32 | 31 | 32 | 132 | 24 |
| Decision 2.0 Sol 2B · CPU | 46 | 47 | 32 | 28 | 33 | 132 | 24 |
| Vela 2.0 0.8B · CPU | 38 | 41 | 29 | 25 | 25 | 132 | 24 |
| Decision 2.0 Eos 0.8B · CPU | 39 | 38 | 30 | 22 | 25 | 132 | 24 |
| Decision 2.0 Eos 0.8B · Q8 Metal | 39 | 38 | 30 | 22 | 25 | 132 | 24 |
| D3 edge · CPU | 34 | 40 | 24 | 21 | 29 | 132 | 24 |
| Decision 2.0 Kai 0.6B · CPU | 34 | 36 | 27 | 17 | 26 | 132 | 24 |
| Vela 2.0 0.3B · CPU | 33 | 32 | 21 | 19 | 25 | 132 | 24 |
| GLiNER2.5-multi-Decide · CPU | 28 | 31 | 17 | 19 | 23 | 132 | 24 |
| Vela 3.0 fast · decision only · CPU | 25 | 32 | 20 | 14 | 23 | 132 | 24 |
| Laya multilingual · CPU | 32 | 24 | 17 | 13 | 26 | 132 | 24 |
| Julia-1 · CPU | 25 | 27 | 18 | 11 | 23 | 132 | 24 |
| Liquid d1-omni-600M · CPU | 19 | 32 | 13 | 15 | 23 | 132 | 24 |
| Indecis · untrained open mode · CPU | 21 | 23 | 12 | 11 | 21 | 132 | 24 |
| ModernJEV-Decide-Preview · CPU | 24 | 18 | 14 | 15 | 13 | 132 | 24 |
| Muose-50M-Decision · CPU | 19 | 22 | 14 | 13 | 14 | 132 | 24 |

## Speed and memory

These are **context-choice adapter observations**, not controlled cross-hardware speed rankings.
Latency includes the adapter's recorded boundary and successful calls only; cold initialization is separate.
Remote latency includes its network/API path; server memory is unknown. One-pass p95 is descriptive, not a tail guarantee.
[Repeated timing and stability](leaderboard/other-benchmarks.md#repeated-timing-and-stability) use separate campaigns.

**RSS and GPU allocations are different measurements: never add them.** Neither establishes total unified-memory use.
RSS below is worker peak for the context phase unless marked **S**, which is a sampled process-group peak over
the session specified in the CSV (historical context + tool, or a fresh context-only session). An allocation or peak is not a minimum-memory requirement; allow runtime/OS headroom.
Metal/MPS observations used a 64 GiB Apple M5 Pro. CPU-H observations are not assumed to share controlled hardware.

| Model observation | Runtime | Median ms | p95 ms | Timed /132 | Init ms | RSS GiB³ | GPU alloc GiB |
|---|---|---:|---:|---:|---:|---:|---:|
| D3 historical · Q4 Metal | Metal | 613.7 | 629.7 | 132 | NR | 18.81 S | NR |
| D3 flash · Q8 Metal | Metal | 194.3 | 200.4 | 132 | NR | 9.39 S | NR |
| D3 flash · Q8 direct Metal | Metal-U | 194.6 | 200.6 | 132 | NR | 9.36 S | NR |
| D3 flash · CPU | CPU-H | 10,080.2 | 15,009.8 | 132 | 24,467.3 | 13.75 | NR |
| Jev 1.13 · HTTP API | API | 280.5 | 323.3 | 132 | NR | NR | NR |
| D3 flash · Q4 Metal | Metal | 197.9 | 203.8 | 132 | NR | 6.66 S | NR |
| D3 mini · CPU | CPU-H | 5,971.7 | 8,291.9 | 132 | 16,466.7 | 7.55 | NR |
| D3 nano · CPU | CPU-H | 2,083.7 | 2,453.4 | 132 | 12,354.2 | 3.39 | NR |
| GLiClass v4 9B · BF16 MPS | MPS | 326.5 | 615.5 | 132 | 13,465.5 | 1.14 | 16.75 |
| Clef Flash · Q8 direct Metal | Metal-U | 196.8 | 219.8 | 132 | NR | 9.56 S | NR |
| Vela 2.0 4B · CPU | CPU-H | 7,948.5 | 9,042.8 | 132 | 24,298.6 | 17.99 | NR |
| Decision 2.0 Nox 4B · CPU | CPU-H | 5,919.6 | 7,373.8 | 132 | 25,886.0 | 20.66 | NR |
| Liquid d1-3B · CPU | CPU-H | 8,079.9 | 10,717.1 | 132 | 12,649.6 | 17.80 | NR |
| Noma · CPU | CPU-H | 4,206.3 | 5,157.5 | 132 | 12,309.9 | 4.82 | NR |
| D3 lite · CPU | CPU-H | 1,002.3 | 1,349.6 | 132 | 11,239.6 | 1.80 | NR |
| Decision 2.0 Sol 2B · CPU | CPU-H | 3,471.9 | 6,403.8 | 132 | 28,703.3 | 8.32 | NR |
| Vela 2.0 0.8B · CPU | CPU-H | 1,573.4 | 1,849.3 | 132 | 11,398.0 | 5.13 | NR |
| Decision 2.0 Eos 0.8B · CPU | CPU-H | 1,122.6 | 1,379.7 | 132 | 13,056.8 | 3.44 | NR |
| Decision 2.0 Eos 0.8B · Q8 Metal | Metal | 28.5 | 37.1 | 132 | NR | 1.37 S | NR |
| D3 edge · CPU | CPU-H | 438.4 | 564.7 | 132 | 8,443.2 | 1.32 | NR |
| Decision 2.0 Kai 0.6B · CPU | CPU-H | 1,220.8 | 2,227.8 | 132 | 19,524.6 | 3.01 | NR |
| Vela 2.0 0.3B · CPU | CPU-H | 171.2 | 252.0 | 132 | 12,767.4 | 1.17 | NR |
| GLiNER2.5-multi-Decide · CPU | CPU-H | 234.9 | 401.0 | 132 | 13,096.7 | 2.82 | NR |
| Vela 3.0 fast · decision only · CPU | CPU-N | 80.5 | 116.4 | 132 | 8,339.1 | 3.16 | NR |
| Laya multilingual · CPU | CPU-H | 168.9 | 219.7 | 132 | 11,186.0 | 2.27 | NR |
| Julia-1 · CPU | CPU-H | 59.0 | 83.2 | 132 | 14,164.9 | 0.97 | NR |
| Liquid d1-omni-600M · CPU | CPU-H | 438.4 | 648.0 | 132 | 9,523.5 | 1.67 | NR |
| Indecis · untrained open mode · CPU | CPU-H | 34.8 | 43.0 | 132 | 1,160.5 | 1.10 | NR |
| ModernJEV-Decide-Preview · CPU | CPU-H | 668.1 | 1,142.4 | 132 | 8,849.6 | 0.86 | NR |
| Muose-50M-Decision · CPU | CPU-H | 308.0 | 748.1 | 132 | 3,113.4 | 0.61 | NR |

³ Worker RSS reporting coverage and the exact measurement scope are retained in the CSV/JSON.
NR means unreported; GPU NR must not be read as zero. Sizes, weight-file sizes, RSS, and GPU allocation are different quantities.

## Other evaluated protocols

The historical tables below are included from the tracked [other-campaign guide](leaderboard/other-benchmarks.md). Their original denominators, failure counts and timing scopes are preserved. They are not combined with the context or rotation-zero evidence rankings. Structured summary metrics and source hashes are also included under `other_campaigns` in the JSON download; detailed cross-groups, rotations and per-case rows remain in the source exports.

### Passage ranking and evidence

The evaluated test subset of the
[passage dataset](../datasets/passage-evidence-v1/README.md) contains eight
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

Sources: [balanced D3/BGE report](evidence/passage-order-control-20261015/report.md)
and [JSON](evidence/passage-order-control-20261015/analysis.json);
[JeV report](evidence/passage-jev-20261015/report.md)
and [JSON](evidence/passage-jev-20261015/analysis.json).

### Passage latency and memory

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
[initial JSON](evidence/passage-cpu-20261015/analysis.json). These observations
do not establish a single memory requirement for the combined pipeline.

For support and answerability, the initial D3 report reconstructs median / p95
costs of **8.330 / 9.605 s** and **1.476 / 5.203 s**, respectively, across 128 pools.
These are additional operations, not included in ranking latency above.

### Longer contexts

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
[full length report](evidence/length-comparison-20261004/report.md) for all
domain, language, and evidence-position intersections, and its
[JSON](evidence/length-comparison-20261004/analysis.json) for runtime provenance
and status-specific timing distributions.

### Repeated timing and stability

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
[repeated timing report](evidence/timing-comparison-20261004/report.md)
and [JSON](evidence/timing-comparison-20261004/analysis.json).

### Initial documentary routing pilot

The earlier [14-case pilot](JULIA_RESULTS.md) observed MCPs **14/14**, Julia
**10/14**, and Julia with reversed option order **9/14**, each fully scored.
Reversing the options changed **5/14** Julia decisions. These are seven correlated
French/English families and inherited train/calibration/test labels, not a balanced
held-out leaderboard. Its source traces and all later repeated measurements remain
separate historical observations.

## Every task and downloadable data

- [Model summary CSV](leaderboard/models.csv): all 30 context observations, model sizes, runtimes, quality, latency, and separate resource measurements.
- [Campaign summary CSV](leaderboard/campaigns.csv): independent capability, physics and passage rankings, coverage, test scores, class macro scores and measured resource scopes.
- [Task breakdown CSV](leaderboard/task-breakdown.csv): exported context task types/subtypes, domains, languages, splits and difficulty; tool-choice subgroups; plus capability, physics and passage groups, with task-specific denominators.
- [Full structured results](leaderboard/results.json): identities, revisions, model/runtime settings, counts, statuses, all groups, source seals, and input-file SHA-256 hashes.
- [Other benchmark results](leaderboard/other-benchmarks.md): full passage, support, answerability, length, repeated timing, and legacy pilot tables. These use different corpora/metrics and are not merged into one accuracy score.

In the task CSV, `numerator` is correct choices or provisional agreement as named by `metric`.
`scored_or_valid` and `total` retain coverage; blank subgroup status cells mean the source did not export those statuses.
FR/EN pairs, passage-order variants, and repeated measurements remain correlated rather than independent evidence.

## Provenance and reproduction

The join reads only explicitly tracked public sources, validates the frozen historical composer and its hashes,
checks duplicated observations and denominators, and binds separate memory observations to model identities/seals.
It does not verify unavailable raw archives or confer human reference approval. Original campaign exports remain unchanged.

```bash
python3 scripts/build-full-results.py --check
# After an intentional, reviewed public evidence/metadata update:
python3 scripts/build-full-results.py --write
```

See the [protocol](PROTOCOL.md), [historical campaign archive](RESULTS_INDEX.md), and
[planned intent, MCP-tool, and model-routing experiment](INTENT_AND_MODEL_ROUTING.md).
