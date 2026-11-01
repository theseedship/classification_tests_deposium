# D3 lite, nano and mini Q8 on GPU runtimes

**Fixed on 1 November 2026, before any prediction of these GGUF models.**
Question: how much faster do the small D3 decision models answer on a GPU
runtime than on the pinned macOS CPU runtime, and does Q8 quantization change
their answers? Apple Metal runs first on the maintainer's Mac; NVIDIA CUDA
([#65](https://github.com/theseedship/classification_tests_deposium/issues/65))
and AMD ROCm or Vulkan
([#66](https://github.com/theseedship/classification_tests_deposium/issues/66))
follow the same protocol on other machines.

## Models

Official ggml-org Q8 conversions, text only (no `mmproj` projector). Their
source weights and `config.json` are byte-identical (Hugging Face LFS hashes)
to the `vllm-sr` revisions of the macOS CPU rows; only quantization and runtime
differ.

| Model | Asset manifest | Alias |
|---|---|---|
| D3 lite | [`profiles/d3-lite-q8-assets.json`](../profiles/d3-lite-q8-assets.json) | `d3-lite-q8` |
| D3 nano | [`profiles/d3-nano-q8-assets.json`](../profiles/d3-nano-q8-assets.json) | `d3-nano-q8` |
| D3 mini | [`profiles/d3-mini-q8-assets.json`](../profiles/d3-mini-q8-assets.json) | `d3-mini-q8` |

## Runtime

Upstream llama.cpp `llama-server` at `efe3626b119ff81033e309c3ba07a770bef2c546`,
the revision of the published D3/Clef Flash Q8 rows, built out of tree from a
clean checkout: Release, static libraries, no tests, examples, app, web UI or
OpenSSL, and one GPU backend (`-DGGML_METAL=ON`, `-DGGML_CUDA=ON`,
`-DGGML_HIP=ON` or `-DGGML_VULKAN=ON`). The local runtime manifest records the
repository, revision and binary SHA-256. A fresh build is a new runtime
identity; each backend is a separate row.

`scripts/run-upstream-native-pilot.py --backend <metal|cuda|rocm|vulkan>`
requires every model layer offloaded to the declared backend before corpus
calls and fails rather than falling back to CPU. Its fixed envelope is kept:
context and batches 4096, one slot, one question per call, 30 s per call, no
retry, 18 GiB sampled process-group RSS, 8 GiB host reserve, at most 1,200 s
per phase. A phase stopped by a guard is reported partial and not extended.

## Preparation, before each phase

`scripts/prepare-native-inputs.py` builds the exact request bytes through the
shared projection, runs the vocabulary-only helper
(`scripts/build-systemone-preflight.py`, now accepting 2–16 options) without
loading weights, and checks that a synthetic oversized input is refused. The
launcher binds the run to that audit by hash. Token IDs and paths stay local.

## Phases and order

Per backend, models in the order lite, nano, mini; per model:

1. `facade-routing-v1` (80), the pack where CPU latency mattered most;
2. `context-choice-v1` (132);
3. `capability-choice-v1` (192);
4. `physics-choice-v1` (48);
5. passage evidence, rotation 0 test (728 physical calls), `--task passages`.

One phase at a time, no other campaign on the host, no checkout in the working
copy during a phase. Each phase starts one technical warm-up input, archived
and excluded from the denominators. No canary threshold: a valid wrong answer
is a result.

## Amendment, 1 November 2026, before the remaining Metal phases

The first Metal series refused most phases at admission, before any model
load: the 18 GiB envelope requires 26 GiB of estimated available memory and
the host hovered around 26 GiB. Observed sampled RSS was 1.4 GiB for D3 lite
and 5.5 GiB for D3 mini. A dedicated envelope, `small-gguf-8g-v1`, now applies
to every phase not yet run: **8 GiB sampled RSS ceiling**, the same 8 GiB host
reserve (admission at 16 GiB), same context, timeouts and 1,200 s per phase;
it is limited to model files of at most 6 GiB. Phases already completed under
the 18 GiB envelope (D3 lite facade and context; D3 mini context, capability
and physics) keep it and are reported with it. Refused admissions created no
archive and no prediction.

Two attempts are recorded and not ranked: D3 mini facade attempt 001 was
interrupted by the operator while the series runner was stopped (unsealed);
D3 mini passages attempt 001 stopped at its technical warm-up because the
preparation did not include the launcher's calibration warm-up input. The
preparation driver now includes it, and both phases are rerun as new attempts.

## Reporting

Per model, backend and pack: correct / all with every non-`ok` status kept;
median and p95 adapter latency; sampled RSS (unified memory on Apple Silicon,
so not comparable with discrete VRAM); and paired agreement with the same
model's macOS CPU row (both right, only GPU right, only CPU right, neither).
A Q8 GPU row never replaces or pools with a BF16 CPU row. Raw archives stay
under ignored `results/`; only reviewed aggregates are published.
