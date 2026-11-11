# GLiClass v4 2B and 9B on the closed-choice packs: results

**11 November 2026. GLiClass v4 2B scores about like D3 nano and below D3
mini, and does not pass the reading rule fixed in the
[protocol](GLICLASS_V4_2B_PROTOCOL_20261111.md) before any prediction**: it
matches or beats D3 nano on the held-out test split of 4 packs out of 9 (five
were required), and its summed test score is 595/754 against 600 for D3 nano
and 659 for D3 mini. The answer for our use is therefore no, whatever the
publisher's benchmarks. References are synthetic and agent-authored, pending
human review; this is an exploratory reading, not a product decision.

**The 9B does not pass its rule either** (fixed in the protocol amendment
before any 9B prediction): it matches or beats D3 Flash Q4 direct Metal on
the test split of 4 packs out of 9, and totals 631/754 against 649 for D3
Flash Q4 and 659 for D3 mini, while needing 16.7 GiB of MPS memory in BF16.
See [the 9B section](#gliclass-v4-9b).

## Scores

One sealed archive per pack, `python3 -m deposium_bench run`, attempt 001
each. All 1,336 cases returned `ok`: no `unsupported`, `error`, `timeout`,
`missing` or `abstain`, and no input reached the 4,096-token limit (largest:
1,124 tokens on capability). D3 counts are the published Q8 Metal rows on the
same pack bytes and scorers.

| Pack | GLiClass 2B, all | GLiClass 2B, test | D3 nano, test | D3 mini, test |
| --- | ---: | ---: | ---: | ---: |
| context-choice-v1 | 103/132 | 57/66 | 61/66 | 60/66 |
| capability-choice-v1 | 186/192 | **95/96** | 91/96 | 96/96 |
| physics-choice-v1 | 28/48 | 20/36 | 21/36 | 32/36 |
| facade-routing-v1 | 76/80 | **44/48** | 44/48 | 47/48 |
| facade-routing-advanced-v1 | 85/96 | 55/64 | 59/64 | 62/64 |
| facade-routing-complex-v1 | 86/96 | **56/64** | 49/64 | 60/64 |
| passage-relevance-v2 | 359/512 | **181/256** | 181/256 | 200/256 |
| facade-routing-hitl-v1 (explicit option) | 51/90 | 33/62 | 39/62 | 47/62 |
| facade-routing-hitl-8opt-v1 | 78/90 | 54/62 | 55/62 | 55/62 |
| **Test total** | | **595/754** | **600/754** | **659/754** |

Bold: packs where the 2B matches or beats D3 nano on test.

Where the D3 nano archives are still on this host (macOS CPU rows, whose
answers are close to but not identical with the Q8 Metal rows), answers were
paired case by case over all cases:

| Pack | Both right | GLiClass only | D3 nano only | Neither |
| --- | ---: | ---: | ---: | ---: |
| context-choice-v1 | 99 | 4 | 18 | 11 |
| capability-choice-v1 | 182 | 4 | 6 | 0 |
| physics-choice-v1 | 18 | 10 | 10 | 10 |
| facade-routing-v1 | 74 | 2 | 2 | 2 |

On passage relevance v2 the 2B never answers *partial* (0/16 on all cases), so
its macro accuracy is 51.2% against 84.6% for D3 nano at the same test count.
Rows for both models are in [RESULTS.md](RESULTS.md).

Language: 422/540 French and 448/540 English cases over the packs that
carry those two labels; the publisher also states that quality is lower
outside English. The weakest spots are context choices and the explicit
human-confirmation option; the strongest are capability choices and the
complex routing tier, where the 2B beats D3 nano by 7 test cases.

## Speed and memory

MPS on an M5 Pro with 64 GiB, BF16, eager attention, one call at a time.
Median inference per call, first call of each pack excluded (warm-up):
115 ms (physics) to 203 ms (human confirmation), 538 ms on capability with
its long catalogues. D3 nano Q8 on llama.cpp Metal answers the same packs in
about 52 ms (context, physics) and 141 ms (capability). Peak MPS allocation
4.4 GiB for the 2B in BF16, against about 2.8 GiB sampled RSS for D3 nano Q8;
worker RSS stayed under 1.7 GiB. The two memory figures are different
measurements and are not summed.

## Limits

- One run per pack on one host; no repeat timing.
- The 2B ships without the calibrator; scores are raw softmax probabilities.
  Only the arg-max is scored, so calibration would not change these counts.
- The GLiClass rendering is the publisher's (instruction, then text, then
  labels); D3 uses its own decision prompt. The comparison covers model,
  rendering and runtime together.
- No quantized GLiClass build was tested: BF16 is the only published format
  for this checkpoint.

## GLiClass v4 9B

Same nine packs, same code, profile `profiles/gliclass-v4-9b-mps.json`
(`14d11a92`, assets re-downloaded and byte-identical to the tracked manifest),
attempt 001 each, all 1,336 cases `ok`. Its context run reproduces the
17 October observation exactly: 117/132, with the same pass or fail on all
132 cases.

| Pack | GLiClass 9B, all | GLiClass 9B, test | D3 Flash Q4, test | D3 mini, test |
| --- | ---: | ---: | ---: | ---: |
| context-choice-v1 | 117/132 | **63/66** | 59/66 | 60/66 |
| capability-choice-v1 | 192/192 | **96/96** | 96/96 | 96/96 |
| physics-choice-v1 | 30/48 | 23/36 | 32/36 | 32/36 |
| facade-routing-v1 | 77/80 | 45/48 | 47/48 | 47/48 |
| facade-routing-advanced-v1 | 93/96 | 61/64 | 62/64 | 62/64 |
| facade-routing-complex-v1 | 91/96 | **59/64** | 59/64 | 60/64 |
| passage-relevance-v2 | 388/512 | **191/256** | 187/256 | 200/256 |
| facade-routing-hitl-v1 (explicit option) | 62/90 | 40/62 | 49/62 | 47/62 |
| facade-routing-hitl-8opt-v1 | 81/90 | 53/62 | 58/62 | 55/62 |
| **Test total** | | **631/754** | **649/754** | **659/754** |

Bold: packs where the 9B matches or beats D3 Flash Q4 on test. Its strength
is context choice, where it beats every D3 of its size; its weak spots are
physics (reasoning with a supplied law, 9 test cases behind) and the explicit
human-confirmation option (9 behind). Language: 460/540 French and 474/540
English cases.

Median inference per call, first call excluded: 307–571 ms, 1,514 ms on
capability (D3 Flash Q4 direct Metal: about 200–290 ms). Peak MPS allocation
16.7 GiB in BF16, against 6.6 GiB sampled RSS for D3 Flash Q4; no quantized
GLiClass 9B is published, so it cannot fit an 8 GB GPU.
