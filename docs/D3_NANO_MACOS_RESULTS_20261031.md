# D3 nano on macOS CPU: results

**30–31 October 2026.** Third Wave B candidate of the capability cohort, run
under the [dated protocol](D3_NANO_MACOS_CPU_PROTOCOL_20261030.md) on the pinned
macOS arm64 CPU runtime shared with D3 lite and Vela 2.0 0.3B. This is a **new
runtime identity**; the historical Linux/WSL CPU row for D3 nano is unchanged
and not merged with it. References are agent-authored and pending human review.

| Pack | Passed / scored | Eligible | Test split | Statuses |
|---|---:|---:|---:|---|
| Synthetic control | — | 0 scored | — | two controls passed |
| Technical canary (12 calibration) | 12 / 12 valid (12 correct, no gate) | 12 | — | — |
| Context 132 (anchor) | **117 / 132** | 132 | 61 / 66 | 132 `ok` |
| Tool proposal 24 (provisional) | 18 agreements / 24 valid | 24 | — | 24 `ok`; zero qualified cases |
| Capability 192, attempt 001 (60 s per call) | 42 / 42 scored | 192 | 18 / 18 scored of 96 | 42 `ok`, 150 `timeout` (1 actual, 149 cached, unattempted) |
| Capability 192, attempt 002 (300 s per call, [amendment](D3_NANO_MACOS_TIMEOUT_AMENDMENT_20261031.md)) | **188 / 192** | 192 | 92 / 96 | 192 `ok` |
| Physics 48 | **28 / 48** | 48 | 22 / 36 | 48 `ok` |

Aggregates: [context and tool](evidence/d3-nano-macos-20261031/analysis.json),
[capability attempt 001](evidence/d3-nano-macos-20261031/capability.json),
[capability attempt 002](evidence/d3-nano-macos-20261031/capability-002.json),
[physics](evidence/d3-nano-macos-20261031/physics.json). The coverage matrix
and rankings use attempt 002; attempt 001 stays published as recorded. Raw outputs, local
paths and process data stay in the ignored archives.

## Identity

| Item | Observed |
|---|---|
| Model | `vllm-sr/d3-nano` at `3aeb1c22…`, 30 files verified against the public manifest; backbone 2,213,241,664 parameters, readout [255, 2048] |
| Runtime | macOS arm64 CPU, Python 3.12.16, Torch 2.14.0 (macOS wheel), Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3; lock `runtimes/d3-macos/runtime.lock`; worker versions equal the lock |
| Settings | two threads, 4096 tokens, backbone bfloat16, readout float32, 12,288 MiB worker ceiling; **60 s per call** for context, tool and physics, **300 s** for capability attempt 002 (dedicated profile `d3-nano-macos-cpu-capability-v1`, otherwise identical) |
| Host | Apple M5 Pro, 64 GiB unified memory |
| Load | 5.3–6.4 s model load, 8.8 s adapter initialization; 717 MiB after load |

## Context 132 and tool 24

117/132 overall (test 61/66; FR 58/66, EN 59/66; documentary 68/76,
mathematics 26/28, chemistry 23/28). The historical Linux/WSL run of the same
checkpoint also scored **117/132**. Tool proposals: 24 valid decisions, 18
provisional agreements, zero semantically qualified cases. Median 7.3 s per
case.

## Capability 192, attempt 002: 188/192 under the amended timeout

Under the [dated amendment](D3_NANO_MACOS_TIMEOUT_AMENDMENT_20261031.md)
(300 s per call, everything else unchanged), all 192 cases were attempted and
answered: no timeout, 14.5–64.1 s per case (median 29.4 s, p95 49.1 s). The
slowest case stayed well under the amended limit and above the old one.

| Measure | Correct / total |
|---|---:|
| All cases | 188 / 192 |
| Test split | 92 / 96 |
| FR / EN | 94 / 96 · 94 / 96 |
| Compact / expanded catalogue | 94 / 96 · 94 / 96 |
| Observations track | 64 / 64 |
| Selection track | 63 / 64 (multi-tool 39/40) |
| Arguments track | 61 / 64 (dependency order 9/12) |

Peak worker RSS 3,554 MiB. For scale only: D3 Flash Q8 and Clef Flash Q8
reached 192/192 under native Metal; D3 lite 168/192 and Vela 2.0 0.3B 128/192
on this CPU runtime. The four errors are all dependency-order or multi-tool
selection cases.

## Capability 192, attempt 001: partial collection after one timeout

Every case has a recorded outcome, but only **43 of 192 were actually
attempted**. The first 42 cases in pack order (all selection-track, by
order, not by difficulty) answered correctly in 14–53 s (median 28 s). The
43rd case, `ccv1-selection-11-expanded-fr`, exceeded the profile's 60-second
per-call limit (60.1 s). The D3 adapter then **fails closed**: it stops the
worker and returns a cached `timeout` for every later case without an
attempt. The archive therefore shows 150 `timeout`: one measured, 149 cached
and unattempted (`cached_failure: true`, about 0 ms each). The aggregate's
`attempts` block records this split.

What this does and does not show: a 2.2B backbone at two CPU threads takes
roughly 2–4 times longer than D3 lite per capability case, and at least one
expanded-catalogue input exceeds 60 s. It says nothing about the arguments
and observations tracks, which never reached the worker. Coverage is 42/192
scored; FR 21/96, EN 21/96; compact 22/96, expanded 20/96; test 18 scored of
96. Peak worker RSS 3,484 MiB, under the 12,288 MiB ceiling.

The 60-second limit is the historical D3 CPU profile value, fixed before
predictions for this candidate. Per the protocol it was not raised during or
after the run. A complete collection requires a declared envelope amendment
(a longer per-call timeout for this candidate's capability pack, with attempt
001 retained and reported beside attempt 002), not a silent change.

## Physics 48

28/48 overall; test 22/36; calibration 6/12; FR 12/24, EN 16/24. Twelve task
types are 2/2 (heat energy, kinetic energy, lift efficiency, missing capacity,
missing mass, opposed forces, period, potential energy, series current, thin
lens, uniform distance, wave speed), four are 1/2 and eight are 0/2. Median
7.8 s per case; worker RSS peak 3,267 MiB. On the same pack: D3 Flash Q8
39/48, Vela 2.0 0.3B 18/48, D3 lite 14/48.

## Limits

- One checkpoint, one runtime, one device, one pass per case; FR/EN and
  catalogue variants are correlated within families.
- A new macOS CPU runtime identity: the identical 117/132 context total with
  the historical Linux row is an observation, not a claim of bitwise parity.
- Capability attempt 001 is a partial collection (one timeout, then a
  fail-closed adapter); attempt 002 under the amended 300 s limit is the
  complete observation used in the matrix. Both are published.
- Closed choices among supplied proposals: no tool execution, arguments,
  agent loop, retrieval or product qualification.
- Worker RSS is the process's own `ru_maxrss`; latency is descriptive.
- References pending human review.
