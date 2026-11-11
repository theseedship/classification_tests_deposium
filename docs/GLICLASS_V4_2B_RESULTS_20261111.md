# GLiClass v4 2B on the closed-choice packs: results

**11 November 2026. GLiClass v4 2B scores about like D3 nano and below D3
mini, and does not pass the reading rule fixed in the
[protocol](GLICLASS_V4_2B_PROTOCOL_20261111.md) before any prediction**: it
matches or beats D3 nano on the held-out test split of 4 packs out of 9 (five
were required), and its summed test score is 595/754 against 600 for D3 nano
and 659 for D3 mini. The answer for our use is therefore no, whatever the
publisher's benchmarks. References are synthetic and agent-authored, pending
human review; this is an exploratory reading, not a product decision.

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
