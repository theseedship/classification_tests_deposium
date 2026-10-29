# Physics-choice-v1: first Flash Q8 campaign protocol

**Status: prepared protocol, not_run; zero real-model cases scored.**
This experiment is separate from the completed capability campaign and its
fixed seven-candidate cohort. It does not require the hosted Turbo adapter.
The machine-readable [plan](../plans/physics-flash-v1.json) freezes dataset,
model identity, phase order and resource limits before physics predictions.

## Question and reference limits

Measure D3 Flash Q8's application of supplied elementary physical laws across
48 synthetic FR/EN cases in 24 families. There are 12 calibration cases in six
families and 36 test cases in 18 families. D1/D2/D3 are authored strata, not an
empirical difficulty scale. All scientific and linguistic human review remains
pending. Exact rational checks do not establish general physics knowledge.

An agent source review found the listed calculations consistent with the
explicit fixture laws: uniform/accelerated motion, signed forces, energies,
efficiency, momentum, circuits, waves, lens distances, ideal gas, heat and gauge
pressure. The mixing case states identical constant specific heat, isolation
and a negligible container; the lens states its sign convention; the two
insufficient-information cases admit distinct exact counterexamples. This
review neither changes references nor supplies independent human certification.

## Frozen inputs and identities

Use physics-choice-v1 SHA-256
`e21cd2e0f4e35465b56158ba1fa07c8d8203be81a969c6edf4b7630d2f0d7307`
and context-choice-v1 SHA-256
`767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`.
Preserve their versioned manifests and source-oracle hashes. No reference or
option change is part of this protocol. The shared analysis must label the
physics pack `physics-choice-v1`, including rows with no scored prediction.

Model: `ggml-org/vllm-d3-flash-GGUF` revision
`3d53d13778bf8035e6e1e534ce489ed052ee5663`, Q8_0 file/hash in the
[asset manifest](../profiles/d3-flash-q8-assets.json). Runtime: llama.cpp
`efe3626b119ff81033e309c3ba07a770bef2c546`, Metal. Verify the current native
binary, helper and real gateway implementation; old session identities do not
establish current readiness. Record exact source/build hashes and local changes
privately. Do not restore or publish old private Git history to supply a harness.

## Phases and fixed budgets

| Phase | Inputs | Time ceiling | Memory ceiling and reserve |
|---|---|---:|---|
| Native preparation | All 180 distinct anchor + physics inputs; separate oversize negative control | 600 s | 2 GiB sampled group RSS + 8 GiB host reserve |
| Technical canary | All 12 physics calibration cases, six complete FR/EN families | 600 s | 18 GiB sampled group RSS + 8 GiB host reserve |
| Fresh context anchor | 132 cases; test/66 reported separately | 1,200 s | Same inference envelope |
| Physics | All 48 cases; test/36 reported separately | 600 s | Same inference envelope |

Preparation reuses the pinned native vocabulary-only helper and exact
`native_request` bytes, as in the [capability protocol](CAPABILITY_NATIVE_PROTOCOL_20261029.md).
No decode/forward occurs in this phase. Validate every rendered native variant
against 4096 tokens, record counts/hashes privately and reject an oversized
synthetic request. A byte-size check is not a native token-length check.

Inference uses context/batch/microbatch 4096, one slot, one request and one
question at a time, a 30-second per-call timeout, no retries and no model/backend
fallback. Admission requires at least 26 GiB estimated available memory before
model hashing. Preserve the 8 GiB reserve and 250 ms watcher interval. Budgets
are ceilings fixed before predictions, not promised runtimes or memory floors.

Use the existing `scripts/run-native-pilot.py` with explicit `--dataset`, the
pinned asset manifest, and the listed context, RSS, reserve and phase time
limits. Each phase needs a fresh owned session and new ignored output directory.
Supply actual local service/stack/model locations through the CLI; no personal
paths or application-source snapshots belong in this public document. The
supervisor runs only the selected dataset and no Mastra phase in explicit mode.

The canary has **no accuracy threshold**. Require valid choices, expected
identity/device and valid preparation evidence; preserve wrong answers.
Its twelve repeated calibration calls do not enlarge the 48-case denominator.
There are 192 planned dataset inference calls (12 + 132 + 48); synthetic
smoke/guard calls are additional technical controls, never scored cases.

## Evidence, analysis and stop rules

Freeze exact current benchmark source/scorer fingerprints and runtime artifacts
before the first forward. The local physics port changes the scorer fingerprint;
historical campaigns remain unchanged and any old rescore needs a new archive.
Capture the physics oracle source and selected input snapshot in the native
source archive. Retain every failed attempt and partial archive.

Use the shared CLI engine and `analyze-context`, with separate outputs for each
pack. Report correct/scored/all, test counts, all six statuses, FR/EN, authored
difficulty, task types and family grouping. Report loading, first and later
call times separately, actual device/precision, sampled group RSS and its scope.
Never pool the two pack accuracies or count translations as independent facts.

Match live request-body hashes and reported input token counts to preparation.
This runtime pin lacks a physical-forward counter and native truncation receipt;
keep those observations unknown. Count agreement alone does not establish
identical live token IDs. Stop on identity/encoding failure, overflow, supervision
loss, time or resource guard; never raise limits in response to a test outcome.

A missing model, pinned runtime, preparation helper or real gateway leaves the
campaign `not_run`, services `not_observed` and zero cases scored. Offline
validation and mocked supervisor tests do not establish campaign readiness.
Public reporting requires a reviewed aggregate from the new sealed archive;
all private locators, logs, raw outputs and source captures stay outside Git.
