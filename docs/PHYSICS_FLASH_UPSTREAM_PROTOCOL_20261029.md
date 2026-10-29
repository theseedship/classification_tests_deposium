# Physics Flash Q8: direct upstream execution variant

**29 October 2026 — frozen before model predictions; not_run.** This variant
retains the datasets, model, native revision, phase order, 4096 context/batches,
30-second calls, time/RSS ceilings and 8 GiB reserve from the
[physics protocol](PHYSICS_FLASH_PROTOCOL_20261029.md). Its
[separate plan](../plans/physics-flash-upstream-v1.json) preserves the original
gateway-backed plan, which remains unexecuted.

The isolated model runs in the real upstream llama.cpp `llama-server` at
`efe3626b119ff81033e309c3ba07a770bef2c546`, built locally with CMake 3.31.6,
static libraries, Metal and Accelerate. UI, OpenSSL, tests and extra applications
are disabled in this build. Preserve the compiler, build flags, source tree,
binary, helper and dependency hashes privately. A fresh build is a new runtime
observation; neither bitwise parity nor historical adapter latency is assumed.

There is **no Deposium application gateway or application integration** in this
variant. The shared `systemone_local` adapter calls the upstream SystemOne HTTP
endpoint directly on authenticated IPv4 loopback. Its session identifies that
listener truthfully as the native binary. It does not claim application
model-alias, route-kind, ACL or product guards. The owned native process and
watcher remain bound through the existing live supervision scope.

Use `scripts/run-upstream-native-pilot.py` with a new output per phase.
It calls the existing campaign engine; no scorer or notebook pipeline is added.
Fixed alias: `physics-flash-q8-v1`. Disable native automatic fitting, context
shifting and empty-run warm-up. Require actual Metal offload of every model
layer before corpus calls; fail rather than fall back to CPU.

Before inference, the existing vocabulary-only C++ helper prepares all 180
distinct anchor/physics inputs and a separate synthetic overflow control.
Supervise it at 2 GiB group RSS, 8 GiB reserve and 600 seconds. Archive exact
UTF-8 body and token hashes. The overflow record must be unsupported; all 180
ordinary inputs must be within 4096. No weights, inference context or forward
are loaded in this preparation phase.

The native adapter optionally binds this validated preparation map by hash.
An unprepared request fails before HTTP. A live input-count mismatch fails the
response and caches the failure, preventing further inference through that
adapter. Missing native truncation and physical-forward receipts remain unknown;
count agreement does not prove equality of live token IDs.

Each fresh phase checks native authentication and actual overflow rejection.
One prepared input is then repeated as a technical warm-up, separately archived
and excluded from quality denominators. For the frozen packs this is a physics
calibration input in the canary/physics phases and the first train input in the
anchor. It is never used to tune prompts, budgets, references or stop on accuracy.
There are 192 planned dataset calls (12 canary + 132 anchor + 48 physics), plus
three excluded warm-ups and excluded guard attempts if all phases complete.

The canary has no accuracy threshold. Keep 132/66 and 48/36 denominators,
coverage, all unsuccessful states, correlations and reference-review limits
separate. `completed` describes collection, not semantic PASS. Source captures,
prepared token IDs, keys, paths and raw outputs stay in ignored local archives.
Only reviewed public aggregates may later update results; no real-model score
is established by compiling the runtime or passing offline tests.
