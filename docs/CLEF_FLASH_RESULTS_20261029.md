# Clef Flash Q8: context, capability and physics choices

**29 October 2026 — first completed Clef Flash Q8/Metal observation.** Clef
scored **110/132 context choices**, **192/192 capability choices**, and
**41/48 physics choices**. These are separate datasets and denominators.
References and translations are agent-authored and pending human review.
This is an isolated text-choice experiment; no tools, application routing,
retrieval or final answer generation were executed.

[Public aggregate and groups](evidence/clef-flash-20261029/analysis.json) ·
[Frozen protocol](CLEF_NATIVE_PROTOCOL_20261029.md) ·
[Frozen plan](../plans/clef-native-v1.json) · [Roadmap status](CAMPAIGN_STATUS.md)

## Scores and comparison

All 384 planned dataset calls completed with valid, scored outputs: the
12-call capability calibration canary, then context/132, capability/192 and
physics/48. Every phase has zero missing, unsupported, error, timeout and
abstain cases. `ok` means valid, not correct. Canary repeats and four separate
prepared-input warm-ups are excluded from the full-pack denominators. The
canary scored 12/12 but had no accuracy gate.

| Dataset | Clef correct / scored / all | Clef test correct / scored / all | Prior D3 Flash overall | Prior D3 Flash test |
|---|---:|---:|---:|---:|
| Context | 110/132/132 | 59/66/66 | 124/132 | 61/66 |
| Capability | 192/192/192 | 96/96/96 | 192/192 | 96/96 |
| Physics | 41/48/48 | 31/36/36 | 39/48 | 32/36 |

The D3 context and physics observations used the same pinned direct upstream
binary and the same dataset/scorer identities, in separate sessions. The
[earlier capability observation](CAPABILITY_FLASH_RESULTS_20261029.md) used
another binary and an application gateway. Its accuracy is a historical
comparison on the same frozen cases, not a controlled runtime comparison.
No prior model was rerun or archive changed for this report.

Clef's higher full physics total comes from calibration: **10/12 versus 7/12**
for D3. On held-out physics cases Clef is **31/36 versus 32/36**. These totals
do not establish a general physics advantage. Context test differs by two
choices; correlated translations and small denominators limit interpretation.

| Context domain | Clef correct / all | Prior D3 Flash |
|---|---:|---:|
| Documentary | 63/76 | 72/76 |
| Mathematics | 25/28 | 26/28 |
| Chemistry | 22/28 | 26/28 |

The perfect capability result covers all three 64-case tracks: capability/tool
sets, arguments/dependencies, and next steps after fixed observations. French,
English, compact catalogues and expanded catalogues each score 96/96. All
48 families, including 24 test families, have all four variants correct.
This confirms a ceiling on this closed-choice pack for these two candidates;
it does not qualify free-form arguments or executed workflows.

## Physics errors and paired outcomes

Clef scores FR **20/24**, EN **21/24**, authored D1 **16/16**, D2 **14/16** and
D3 **11/16**. Twenty of 24 families have both translations correct, one is
mixed and three have both wrong. The seven incorrect choices occur in:

| Supplied-law task | Clef correct / all |
|---|---:|
| Lift efficiency and consumed energy | 0/2 |
| Joule energy | 0/2 |
| Thermal mixing | 0/2 |
| Capacitor energy | 1/2 |

Every other physics family has 2/2 correct. Laws and assumptions are supplied
in the inputs; these errors do not isolate a reasoning mechanism or measure
general scientific expertise. References, inputs, order and budgets were not
adjusted after predictions.

The aggregate pairs individual cases with the archived direct D3 observation.
Both original analysis hashes match the previously published D3 aggregate;
the dataset and scorer fingerprints match. This is descriptive pairing of
existing scored observations, not fresh D3 inference or a new timing run.

| Matched cases | Both correct | D3 only correct | Clef only correct | Both incorrect | Families |
|---|---:|---:|---:|---:|---:|
| Context, all 132 | 107 | 17 | 3 | 5 | 66 |
| Context, test 66 | 56 | 5 | 3 | 2 | 33 |
| Physics, all 48 | 37 | 2 | 4 | 5 | 24 |
| Physics, test 36 | 30 | 2 | 1 | 3 | 18 |

The few complementary errors do not qualify a model-selection rule or cascade.
Exposed test cases cannot become a fresh held-out routing benchmark.

## Runtime and resources

Actual runtime: pinned upstream llama.cpp on Metal, **33/33 layers offloaded**,
decision type **clef**, Apple M5 Pro with 64 GiB unified memory. Each phase
used a fresh owned loopback listener, one slot/request/question, context/batch/
microbatch 4096, a 30-second call timeout, no retries, no context shifting,
automatic fitting or backend fallback. No paid model API was used.

| Full phase | Timed OK calls / all | Adapter median ms | Adapter p95 ms | Sampled group RSS peak GiB |
|---|---:|---:|---:|---:|
| Context | 132/132 | 196.8 | 219.8 | 9.56 |
| Capability | 192/192 | 616.9 | 953.5 | 10.60 |
| Physics | 48/48 | 196.7 | 211.7 | 9.55 |

Compact capability inputs have median/p95 **464.0/567.8 ms**; expanded inputs
have **811.7/962.1 ms**. The views also change distractors and positions, so this
does not isolate catalogue size. Latencies are one ordered pass after an
excluded warm-up; loading/startup is excluded. Median uses the central-pair
midpoint and p95 the nearest rank. No stable tail or controlled speed ranking
against earlier candidates is claimed.

RSS is sampled over the owned process group every 250 ms and includes startup,
controls and warm-up. It is not per-response RSS, a memory floor or total
unified GPU allocation. GPU allocation was not separately reported. All four
sessions stayed within **18 GiB RSS + 8 GiB host reserve**, with no resource
stop. The macOS available-memory estimate counts free, inactive and speculative
pages and is not Linux `MemAvailable`. Owned sessions were stopped before seals
were written.

## Input preparation and identities

Before inference, the vocabulary-only helper called the actual upstream Clef
joint-task renderer. All **372 distinct dataset inputs** fit within 4096 tokens,
from **183 to 1265 tokens**. A separate three-choice synthetic input prepared
successfully and an oversized synthetic input was rejected. Preparation used
no weight tensors, inference context or forward; its sampled RSS peak was
177.44 MiB under the separate 2 GiB/8 GiB/600-second envelope.

All **384/384 dataset responses** matched exact prepared request-body hashes
and native input counts. Only context, question and ordered option descriptions
reached the native endpoint, with neutral choice keys. Golds, explanations,
annotations, split labels and descriptive case IDs were absent. Output-token
counts were zero. Live token IDs and joint head order were not independently
compared; physical-forward counters and native truncation receipts remain
unknown for every response.

All four sessions rejected unauthenticated requests with HTTP 401 and rejected
the oversized input with this pin's recognized native overflow error (HTTP
500). That specific rejection is not evidence that arbitrary HTTP 500 errors
represent input overflow. Three-choice inference was not evaluated.

| Identity | Revision or SHA-256 |
|---|---|
| Model repository | `ggml-org/Clef-Flash-GGUF` |
| Model revision | `6e2a164d70aae2af7fce86005da3f91805565b1d` |
| Q8_0 model SHA-256 | `25f801e2a27610b0ccc0cb1558d7eda3d7a304e34e2c4a04e3079357ff7d906e` |
| llama.cpp revision | `efe3626b119ff81033e309c3ba07a770bef2c546` |
| Native binary SHA-256 | `d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1` |
| Preparation helper SHA-256 | `42ea3604621a346818bbc27a55488ad411fbb508326d178226305638f3d4e97b` |
| Public benchmark base | `501f0963077a787dfea6168330dde9754affd3e7` |

The downloaded model bytes and 50 helper dependency files were verified before
preparation. Public benchmark bytes were frozen before the first prediction and
verified unchanged through all phases. The aggregate retains dataset/scorer,
source, preparation, analysis and archive fingerprints. Original outputs, logs,
source captures and path-bearing receipts remain local. These are integrity
records, not independent certification or a reproducible-build guarantee.

The original campaign seals, preparation bindings and analysis hashes were
verified before aggregate export. After adding this report, the 22 existing
result-generation tests passed and generated views matched their sources.
The full macOS suite was not repeated for these reporting changes; its
pre-existing failures are documented in [the checkpoint](CAMPAIGN_STATUS.md).

The conversion card links to Cloudflare/clef-flash, but its exact converted
source revision is not attested. These Q8/Metal results do not qualify
Cloudflare's BF16/PyTorch or CUDA runtime, vision, generation or multi-question
features. Clef 27B remains unexecuted and needs its separate resource envelope.

## Next useful experiment

Move to evidence assessment on matching passage inputs: freeze the stronger
D3 Flash comparison's support/relevance/answerability protocol, audit its native
inputs and budgets, then run technical calibration and full observations.
Extend to Clef under a separately frozen protocol. Context and capability
scores do not establish support-task readiness. The original capability cohort
is unchanged; six candidates and executable tool episodes remain open work.
