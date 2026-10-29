# Full results

[README](../README.md) · [Quality](#model-quality) · [Language and task complexity](#language-and-task-complexity) ·
[New capability tests](#complementary-capability-campaign-29-october-2026) · [Speed and memory](#speed-and-memory) · [Passages and other campaigns](leaderboard/other-benchmarks.md) ·
[Proposed tool and model routing](INTENT_AND_MODEL_ROUTING.md)

**28 historical model/runtime observations**, consolidated from the public frozen exports through 28 October 2026.
Rows identify observations, not 28 independent model families. Repeated exports of the same sealed run are deduplicated;
quantizations and devices remain separate. Rendering this page does not rerun or rescore models.

**Exploratory evidence:** synthetic, agent-authored references and translations await human review.
The ranking uses all 132 cases (train + calibration + test); the separate test column uses 66 cases.
FR/EN translations form 66 families. Differences of a few answers do not establish a general model ranking.

## What was actually tested?

| Task | Common input and denominator | Status |
|---|---|---|
| Documentary text and choices | 76 context-dependent choices | Scored exploratory decisions |
| Mathematics / chemistry | 28 / 28 constrained choices | Scored synthetic probes, not expert scientific qualification |
| First tool proposal | 24 search / statistics / fallback choices | Provisional agreement only; no tool execution; **0 semantically qualified cases** |
| Physics | [48 synthetic choices](../datasets/physics-choice-v1/README.md), 24 FR/EN families | [Flash Q8/direct Metal: 39/48, test 32/36](PHYSICS_FLASH_RESULTS_20261029.md); reported separately, human review pending |
| Passage ranking, relevance, support, answerability | Separate fixed-passage campaigns | [Full tables and coverage](leaderboard/other-benchmarks.md) |
| Capability/tool-set, argument and fixed-observation choices | [192-case complementary pack](../datasets/capability-choice-v1/README.md) | [First D3 Flash Q8/Metal campaign and fresh context anchor](CAPABILITY_FLASH_RESULTS_20261029.md), reported separately from the 28 historical rows; no tool execution or product qualification |
| Free-form plugin/MCP selection, complete execution loop, difficulty prediction, adaptive model routing | Future harness stages | **Not run**; [experiment design](INTENT_AND_MODEL_ROUTING.md) |
| End-to-end RAG and generated-answer quality | No campaign qualified here | **Not run** |

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
[Full campaign report](CAPABILITY_FLASH_RESULTS_20261029.md) · [Groups, pairs and source evidence](evidence/capability-flash-20261029/analysis.json). The 28 historical observations below retain their original rows and ranks.

## Model quality

Each score is **correct / all cases** in its column, retaining failures in the denominator.
Tool is **agreement / 24 provisional proposals**, not routing accuracy. Full scored/valid counts and separate
`missing`, `unsupported`, `error`, `timeout`, and `abstain` counts are in the downloads.
Equal all-case totals share a competition rank; row order within a tie is alphabetical by observation ID.

| Rank | Model observation | Size¹ | Runtime² | All /132 | Test /66 | Text /76 | Math /28 | Chem /28 | Tool /24 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | D3 historical · Q4 Metal | 27B class | Metal | 128 | 65 | 73 | 28 | 27 | 24 |
| 2 | D3 flash · Q8 Metal | 9B class | Metal | 124 | 61 | 72 | 26 | 26 | 20 |
| 2 | D3 flash · CPU | 8.393B backbone | CPU-H | 124 | 61 | 72 | 26 | 26 | 20 |
| 4 | Jev 1.13 · HTTP API | NR | API | 123 | 62 | 67 | 28 | 28 | 20 |
| 5 | D3 flash · Q4 Metal | 9B class | Metal | 122 | 59 | 71 | 24 | 27 | 21 |
| 6 | D3 mini · CPU | 4.539B backbone | CPU-H | 119 | 60 | 71 | 24 | 24 | 20 |
| 7 | D3 nano · CPU | 2.213B backbone | CPU-H | 117 | 61 | 68 | 26 | 23 | 18 |
| 7 | GLiClass v4 9B · BF16 MPS | 9B class | MPS | 117 | 63 | 70 | 24 | 23 | 20 |
| 9 | Vela 2.0 4B · CPU | 4.211B | CPU-H | 106 | 56 | 64 | 20 | 22 | 18 |
| 10 | Decision 2.0 Nox 4B · CPU | 4.208B | CPU-H | 103 | 55 | 54 | 25 | 24 | 18 |
| 11 | Liquid d1-3B · CPU | 3.123B | CPU-H | 101 | 55 | 60 | 21 | 20 | 16 |
| 12 | Noma · CPU | ~2.67B declared | CPU-H | 98 | 51 | 53 | 25 | 20 | 18 |
| 13 | D3 lite · CPU | 0.853B backbone | CPU-H | 95 | 50 | 64 | 15 | 16 | 19 |
| 14 | Decision 2.0 Sol 2B · CPU | 2B class | CPU-H | 93 | 47 | 62 | 19 | 12 | 19 |
| 15 | Vela 2.0 0.8B · CPU | 0.755B declared | CPU-H | 79 | 45 | 56 | 11 | 12 | 14 |
| 16 | Decision 2.0 Eos 0.8B · CPU | 0.8B class | CPU-H | 77 | 40 | 55 | 12 | 10 | 19 |
| 16 | Decision 2.0 Eos 0.8B · Q8 Metal | 0.8B class | Metal | 77 | 40 | 55 | 12 | 10 | 19 |
| 18 | D3 edge · CPU | 0.594B backbone | CPU-H | 74 | 37 | 48 | 12 | 14 | 18 |
| 19 | Decision 2.0 Kai 0.6B · CPU | 0.6B class | CPU-H | 70 | 36 | 56 | 7 | 7 | 16 |
| 20 | Vela 2.0 0.3B · CPU | 0.309B declared | CPU-H | 65 | 37 | 52 | 4 | 9 | 18 |
| 21 | GLiNER2.5-multi-Decide · CPU | NR | CPU-H | 59 | 38 | 41 | 5 | 13 | 12 |
| 22 | Vela 3.0 fast · decision only · CPU | 0.380B decision backbone | CPU-N | 57 | 28 | 43 | 9 | 5 | 18 |
| 23 | Laya multilingual · CPU | 322M declared | CPU-H | 56 | 30 | 42 | 8 | 6 | 10 |
| 24 | Julia-1 · CPU | NR | CPU-H | 52 | 26 | 32 | 8 | 12 | 11 |
| 25 | Liquid d1-omni-600M · CPU | 600M class | CPU-H | 51 | 26 | 39 | 4 | 8 | 16 |
| 26 | Indecis · untrained open mode · CPU | NR | CPU-H | 44 | 22 | 32 | 2 | 10 | 11 |
| 27 | ModernJEV-Decide-Preview · CPU | NR | CPU-H | 42 | 23 | 23 | 13 | 6 | 8 |
| 28 | Muose-50M-Decision · CPU | 50M class | CPU-H | 41 | 21 | 30 | 6 | 5 | 10 |

¹ Sizes describe the observed checkpoint: exact tensor counts, nominal classes, and publisher declarations
are distinguished in [metadata](leaderboard/model-metadata.json). A backbone count may exclude a separate readout;
some counts include vision weights. **NR** means not reported in the selected public evidence, not zero.
The historical 27B D3 is neither an Ultra nor a Turbo observation; neither variant was evaluated here.

² CPU-H: historical Linux/WSL CPU runs (processor not identified here); API: remote service with unknown server hardware;
Metal: native llama.cpp on Apple M5 Pro; MPS: official PyTorch pipeline on Apple M5 Pro;
CPU-N: newer macOS CPU run. Runtime, readout, serializer, precision, and input lengths differ.

## Language and task complexity

D1/D2/D3 are authored context-task strata, **not predictions of difficulty or evidence that escalation helps**.
A correct choice also does not prove that a plugin was executed or a useful answer generated.

| Model observation | FR /66 | EN /66 | D1 /40 | D2 /40 | D3 /52 | Scored /132 | Tool valid /24 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D3 historical · Q4 Metal | 64 | 64 | 40 | 38 | 50 | 132 | 24 |
| D3 flash · Q8 Metal | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| D3 flash · CPU | 62 | 62 | 39 | 37 | 48 | 132 | 24 |
| Jev 1.13 · HTTP API | 62 | 61 | 36 | 38 | 49 | 132 | 24 |
| D3 flash · Q4 Metal | 62 | 60 | 39 | 37 | 46 | 132 | 24 |
| D3 mini · CPU | 60 | 59 | 40 | 38 | 41 | 132 | 24 |
| D3 nano · CPU | 58 | 59 | 37 | 38 | 42 | 132 | 24 |
| GLiClass v4 9B · BF16 MPS | 58 | 59 | 39 | 35 | 43 | 132 | 24 |
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
the native context + tool session. An allocation or peak is not a minimum-memory requirement; allow runtime/OS headroom.
Metal/MPS observations used a 64 GiB Apple M5 Pro. CPU-H observations are not assumed to share controlled hardware.

| Model observation | Runtime | Median ms | p95 ms | Timed /132 | Init ms | RSS GiB³ | GPU alloc GiB |
|---|---|---:|---:|---:|---:|---:|---:|
| D3 historical · Q4 Metal | Metal | 613.7 | 629.7 | 132 | NR | 18.81 S | NR |
| D3 flash · Q8 Metal | Metal | 194.3 | 200.4 | 132 | NR | 9.39 S | NR |
| D3 flash · CPU | CPU-H | 10,080.2 | 15,009.8 | 132 | 24,467.3 | 13.75 | NR |
| Jev 1.13 · HTTP API | API | 280.5 | 323.3 | 132 | NR | NR | NR |
| D3 flash · Q4 Metal | Metal | 197.9 | 203.8 | 132 | NR | 6.66 S | NR |
| D3 mini · CPU | CPU-H | 5,971.7 | 8,291.9 | 132 | 16,466.7 | 7.55 | NR |
| D3 nano · CPU | CPU-H | 2,083.7 | 2,453.4 | 132 | 12,354.2 | 3.39 | NR |
| GLiClass v4 9B · BF16 MPS | MPS | 326.5 | 615.5 | 132 | 13,465.5 | 1.14 | 16.75 |
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

## Every task and downloadable data

- [Model summary CSV](leaderboard/models.csv): all 28 observations, model sizes, runtimes, quality, latency, and separate resource measurements.
- [Task breakdown CSV](leaderboard/task-breakdown.csv): every exported context task type and documentary subtype, domain, language, split, difficulty stratum, domain × language/split, plus tool-choice subgroups.
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
