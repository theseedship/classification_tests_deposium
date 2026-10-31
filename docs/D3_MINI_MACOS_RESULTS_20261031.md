# D3 mini on macOS CPU: results

**31 October 2026.** Fourth and last Wave B candidate of the capability cohort,
run under the [dated protocol](D3_MINI_MACOS_CPU_PROTOCOL_20261031.md) on the
pinned macOS arm64 CPU runtime shared with D3 lite, Vela 2.0 0.3B and D3 nano.
This is a **new runtime identity**; the historical Linux/WSL CPU row for D3
mini (119/132) is unchanged and not merged with it. References are
agent-authored and pending human review.

| Pack | Passed / scored | Eligible | Test split | Statuses |
|---|---:|---:|---:|---|
| Synthetic control | — | 0 scored | — | two controls passed |
| Technical canary (12 calibration, 120 s profile) | 10 / 10 valid (10 correct, no gate) | 12 | — | 10 `ok`, 2 `timeout`; two worker restarts |
| Context 132 (anchor) | **119 / 132** | 132 | 60 / 66 | 132 `ok` |
| Tool proposal 24 (provisional), attempt 002 | 20 agreements / 24 valid | 24 | — | 24 `ok`; zero qualified cases; attempt 001 stopped at 13/24 by the default 300 s wall budget |
| Capability 192 (300 s per call) | **192 / 192** | 192 | **96 / 96** | 192 `ok`, no restart |
| Physics 48 | **39 / 48** | 48 | 32 / 36 | 48 `ok` |

Aggregates: [context and tool](evidence/d3-mini-macos-20261031/analysis.json),
[context pack export](evidence/d3-mini-macos-20261031/context.json),
[capability](evidence/d3-mini-macos-20261031/capability.json),
[physics](evidence/d3-mini-macos-20261031/physics.json). Raw outputs, local
paths and process data stay in the ignored archives.

## Identity

| Item | Observed |
|---|---|
| Model | `vllm-sr/d3-mini` at `a475367d…`, 32 files (8.48 GiB) verified against the public manifest; backbone 4,539,265,536 parameters, readout [255, 2560] |
| Runtime | macOS arm64 CPU, Python 3.12.16, Torch 2.14.0 (macOS wheel), Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3; lock `runtimes/d3-macos/runtime.lock`, unchanged since D3 lite |
| Settings | two threads, 4096 tokens, backbone bfloat16, readout float32, 14,336 MiB worker ceiling; **120 s per call** (context, tool, physics), **300 s** for capability (dedicated profile `d3-mini-macos-cpu-capability-v1`, otherwise identical), both fixed before the first prediction from lite and nano latencies |
| Host | Apple M5 Pro, 64 GiB unified memory; a user virtual machine used about four cores during the first hour of the capability campaign |
| Load | 5.1–5.2 s model load, 12.1 s adapter initialization; 7,525–8,009 MiB worker RSS peak across packs |

## Canary: the restart policy exercised live

The twelve-case technical canary ran under the general 120 s profile, which
the protocol did not reserve for capability-shaped inputs: six compact and
expanded selection/arguments cases answered in 39–110 s, then
`ccv1-arguments-02-expanded-fr` and `ccv1-observations-02-expanded-fr`
exceeded 120 s. Under the [restart policy](CPU_WORKER_RESTART_POLICY_20261031.md)
each timeout was recorded for its case only, the worker was relaunched (10.2 s
and 8.6 s) and the remaining cases were attempted: 10 `ok`, all correct, 2
`timeout`. The canary has no accuracy gate; it confirmed identity, pins and
decisions, and that the 300 s capability profile was the right one.

## Context 132 and tool 24

119/132 overall (test 60/66; FR 60/66, EN 59/66; documentary 71/76,
mathematics 24/28, chemistry 24/28). The historical Linux/WSL run of the same
checkpoint also scored **119/132**. Median 17.2 s per case, maximum 22.4 s.

Tool proposals: attempt 001 stopped after 13 of 24 cases when the observation
script's default 300 s wall budget expired (mini needs about 17 s per call);
it is kept as recorded and not analysed. Attempt 002, with the 600 s budget
the script allows for `d3` profiles, is complete: 24 valid decisions,
20 provisional agreements, zero semantically qualified cases.

## Capability 192: 192/192

All 192 cases answered and correct, test 96/96, FR 96/96 and EN 96/96,
compact 96/96 and expanded 96/96, every track 64/64 (selection, arguments,
observations), D1/D2/D3 52/52, 84/84, 56/56. Latency 37.8–134.8 s per case
(median 78.8 s, p95 126.6 s), under the 300 s profile with a 2.2× margin; no
timeout, no worker restart. Peak worker RSS 8,009 MiB. Native input tokens
362–1,214 (median 721).

For scale: D3 Flash Q8 and Clef Flash Q8 reached 192/192 under native Metal;
on this CPU runtime D3 nano 188/192, D3 lite 168/192, Vela 2.0 0.3B 128/192.
D3 mini is the smallest model to reach the pack's ceiling, which is a ceiling
on four-proposal synthetic choices, not evidence of tool discovery or
executable workflows.

## Physics 48: 39/48

39/48 overall; test 32/36; calibration 7/12; FR 19/24, EN 20/24; D1 16/16,
D2 10/16, D3 13/16. Twenty task types are 2/2, one is 1/2 (lift efficiency)
and four are 0/2 (accelerated distance, hydrostatic pressure, inelastic
collision, Joule energy). Median 16.8 s per case; worker RSS peak 7,515 MiB.
On the same pack: Clef Flash Q8 41/48, D3 Flash Q8 39/48 (test 32/36), D3 nano
28/48, Vela 2.0 0.3B 18/48, D3 lite 14/48. D3 mini equals D3 Flash Q8 on both
totals; Clef leads all cases.

## Limits

- One checkpoint, one runtime, one device, one pass per case; FR/EN and
  catalogue variants are correlated within families.
- A new macOS CPU runtime identity: the identical 119/132 context total with
  the historical Linux row is an observation, not a claim of bitwise parity.
- Tool attempt 001 is an incomplete observation stopped by a harness wall
  budget, not by the model; it is kept and not scored.
- Closed choices among supplied proposals: no tool execution, arguments,
  agent loop, retrieval or product qualification.
- Latency is descriptive; part of the capability campaign shared the host
  with a user virtual machine.
- References pending human review.
