# D3 Flash Q8: first physics-choice observation

**29 October 2026 — physics 39/48 (81.25%), including test 32/36 (88.89%).**
All 48 choices were valid and scored. The separate fresh context anchor reached
124/132, including 61/66 test. References and translations are agent-authored
and pending scientific and linguistic human review. This is an exploratory
supplied-law choice experiment, not general physics or end-to-end RAG qualification.

[Public aggregate and task breakdowns](evidence/physics-flash-20261029/analysis.json) ·
[Frozen direct protocol](PHYSICS_FLASH_UPSTREAM_PROTOCOL_20261029.md) ·
[Plan](../plans/physics-flash-upstream-v1.json) · [Priorities](BENCHMARK_PRIORITIES_20261029.md)

## Scores and boundaries

| Phase | Correct / scored / all | Test correct / scored / all | Families |
|---|---:|---:|---:|
| Technical physics canary | 7/12/12 | Not a test score | 6 calibration families |
| Fresh context anchor | 124/132/132 | 61/66/66 | 66 |
| Physics-choice-v1 | 39/48/48 | 32/36/36 | 24 |

The canary had no accuracy threshold. Its wrong choices did not stop the full
campaign. Canary repeats and one technical warm-up per fresh session are
excluded from the two full-pack denominators. All phases have zero missing,
unsupported, error, timeout and abstain cases; `ok` means valid, not correct.
The two packs are not pooled into one accuracy.

| Physics group | Correct / all |
|---|---:|
| Calibration | 7/12 |
| Test | 32/36 |
| French | 19/24 |
| English | 20/24 |
| Authored D1 | 16/16 |
| Authored D2 | 12/16 |
| Authored D3 | 11/16 |

These 48 translations represent 24 scenario families, including 18 test
families. Nineteen families have both translations correct, one has mixed
correctness, and four have both incorrect. Choice agreement is 22/24 families;
agreement and correctness are different quantities. No independent-sample
confidence interval or universal difficulty scale is claimed.

The nine incorrect choices occur in five families:

| Supplied-law task | Correct / all |
|---|---:|
| Accelerated displacement | 0/2 |
| Lift efficiency and consumed energy | 0/2 |
| Perfectly inelastic collision | 1/2 |
| Joule energy | 0/2 |
| Capacitor energy | 0/2 |

Every other physics family has 2/2 correct. The inputs supply the laws and
assumptions; these errors do not isolate a mechanism or measure prior physics
knowledge. No reference, option, law, split or budget was changed in response.
The frozen physics and historical context hashes remain unchanged.

The fresh anchor matches the historical Flash Q8 totals, including documentary
72/76, mathematics 26/28 and chemistry 26/28. Equal totals alone do not establish
identical predictions or bitwise reproduction. This new binary and direct
listener remain a separate observation from the historical gateway-backed run.

## Runtime, latency and resource scope

Actual runtime: upstream llama.cpp, Metal, **33/33 layers offloaded**, Apple M5
Pro with 64 GiB unified memory. No application gateway, routing integration,
remote model API or paid inference service was used. The model assets were
downloaded explicitly and checked against the existing pinned size and SHA-256.

| Full phase | Timed OK calls / all | Adapter median ms | Adapter p95 ms | Sampled group RSS peak GiB |
|---|---:|---:|---:|---:|
| Context anchor | 132/132 | 194.6 | 200.6 | 9.36 |
| Physics | 48/48 | 193.7 | 202.1 | 9.36 |

These are one-pass adapter durations after a separately archived prepared-input
warm-up. Loading, asset verification and startup are excluded; cold startup
was not separately qualified. p95 is descriptive, not a production tail
guarantee. The sampled group peak includes startup, controls, warm-up and that
pack; it is not per-case RSS, a memory floor or total unified GPU allocation.
GPU allocation was not separately reported. Do not add it to RSS or treat this
as a controlled speed comparison against CPU/MPS or the application gateway.

The frozen envelope was context/batch/microbatch 4096, one slot/request/question,
30 seconds per call, 18 GiB group RSS and an 8 GiB host reserve. Neither full
phase tripped a resource guard. Available-memory readings use the macOS
free/inactive/speculative-page estimate, not Linux `MemAvailable`.

## Preparation, identity and retained attempts

The vocabulary-only helper prepared all **180 distinct inputs**, 128–211
native tokens, and rejected a separate oversized synthetic input. Its sampled
group RSS peak was 162.25 MiB under the separate 2 GiB/8 GiB/600-second envelope.
Preparation loaded no weight tensors, created no inference context and executed
no forward. Exact request bodies and token IDs remain local.

The adapter's bound preparation map matched request hashes and live declared
input counts for **12/12 canary, 132/132 anchor and 48/48 physics calls**.
The native endpoint does not expose physical-forward counters or truncation
receipts: those remain unknown. Count agreement does not independently compare
live token IDs. Golds, reference explanations, splits and descriptive case IDs
were absent from the native request bodies.

| Identity | Revision or SHA-256 |
|---|---|
| Model repository | `ggml-org/vllm-d3-flash-GGUF` |
| Model revision | `3d53d13778bf8035e6e1e534ce489ed052ee5663` |
| Q8_0 model SHA-256 | `7352edf6be85d93ab8806a17e1b3d0a7e71ee3685af3212ddbe679b742c2221b` |
| llama.cpp revision | `efe3626b119ff81033e309c3ba07a770bef2c546` |
| Newly built native binary SHA-256 | `d6ec60cbb70b61572c0f33305b6839952445fa35b9ee2f1355b71216ab28ada1` |
| Preparation helper SHA-256 | `0921056c584ed92f9d434028d83947e37dd38cfaf24b9c4987b956f5c19289f9` |

The benchmark used public base commit `8b164b8` plus the uncommitted physics
and direct-supervisor changes. Exact source/scorer fingerprints, dataset hashes,
outer seals and analysis hashes are in the public aggregate; exact source,
build provenance, original outputs and logs remain local. This is recorded
integrity, not independent authentication or reproducible-build certification.

Three initial setup attempts are retained with **zero corpus predictions**.
They stopped at the backend-observation check: native core logs require trace
verbosity in this pin, and the check initially mishandled lowercase
`ggml_metal`. Logging and the observation parser were corrected and tested before
the first corpus prediction. No resource guard, model identity or reference was
weakened. All subsequent phases used the same corrected source snapshot.

## Implication for the roadmap

Physics adds a discriminating observation alongside Flash's 192/192 capability
choices. The two results measure different supplied inputs and tasks; neither
qualifies executable arguments, an adaptive tool loop or final answer quality.
The fixed capability cohort still has six candidates unexecuted. Cross-model
physics comparisons and human reference review remain open work.

At the physics session's post-cleanup reading, the estimated available memory
was 23.76 GiB, below the existing 32 GiB admission envelope for the next
historical 27B candidate. That is a resource preflight, not a model failure.
Recheck admission before a later session; this campaign did not lower the
guard or change the fixed capability cohort/order to proceed.
