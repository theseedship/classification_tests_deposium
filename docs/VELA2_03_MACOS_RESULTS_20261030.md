# Vela 2.0 0.3B on macOS CPU: results

**30 October 2026.** Second Wave B candidate of the capability cohort, run
under the [dated protocol](VELA2_03_MACOS_CPU_PROTOCOL_20261030.md) on the same
pinned macOS arm64 CPU runtime as D3 lite. This is a **new runtime identity**;
the historical Linux/WSL CPU row for Vela 2.0 0.3B is unchanged and not merged
with it. References are agent-authored and pending human review.

| Pack | Passed / scored | Eligible | Test split | Statuses |
|---|---:|---:|---:|---|
| Synthetic control | — | 0 scored | — | two controls passed |
| Technical canary (12 calibration) | 12 / 12 valid (10 correct, no gate) | 12 | — | — |
| Context 132 (anchor) | **65 / 132** | 132 | 37 / 66 | 132 `ok` |
| Tool proposal 24 (provisional) | 18 agreements / 24 valid | 24 | — | 24 `ok`; zero qualified cases |
| Capability 192 | **128 / 192** | 192 | 62 / 96 | 192 `ok` |
| Physics 48 | **18 / 48** | 48 | 14 / 36 | 48 `ok` |

Every pack was collected completely, with no `missing`, `unsupported`,
`error`, `timeout` or `abstain` case. Aggregates:
[context and tool](evidence/vela2-03-macos-20261030/analysis.json),
[capability](evidence/vela2-03-macos-20261030/capability.json),
[physics](evidence/vela2-03-macos-20261030/physics.json).

## Identity

| Item | Observed |
|---|---|
| Model | `vllm-sr/Vela-2.0-0.3B` at `d6f03aa9…`, 38 files verified against the public manifest; 309,114,369 parameters (publisher declared) |
| Runtime | macOS arm64 CPU, Python 3.12.16, Torch 2.14.0 (macOS wheel), Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3; lock `runtimes/d3-macos/runtime.lock` (shared with D3 lite); worker versions equal the lock |
| Settings | two threads, 4096 tokens, float32, loading mode `hf-automodel-fp32`, 4,096 MiB worker ceiling, 30 s per call |
| Host | Apple M5 Pro, 64 GiB unified memory; available memory from the vm_stat estimate |
| Load | 4.9–5.4 s model load, 6.0 s adapter initialization; 1,114 MiB after load |

## Context 132 and tool 24

65/132 overall (test 37/66; FR 33/66, EN 32/66; documentary 52/76,
chemistry 9/28, mathematics 4/28). The historical Linux/WSL run of the same
checkpoint also scored **65/132**; the two rows remain separate observations
of different runtimes. Tool proposals: 24 valid decisions, 18 provisional
agreements, zero semantically qualified cases. Median 154 ms per case (max
204 ms); worker RSS peak about 1.2 GiB.

## Capability 192

128/192 overall; test 62/96; FR 67/96, EN 61/96; compact 66/96, expanded 62/96.

| Track | Correct / total |
|---|---:|
| Selection (capability/tool-set proposals) | 53 / 64 |
| Next step after fixed observations | 45 / 64 |
| Arguments and dependencies | 30 / 64 |

The profile is the reverse of D3 lite's: selection is the strongest track
(multi-tool 30/40, single-tool 16/16, source choice 7/8) and arguments the
weakest (clarification 2/12, resource choice 2/12, argument binding 10/20,
dependency order 8/12). In the observation track, partial-answer cases are
0/4 and stop-when-unavailable 1/4. Median 345 ms per case (p95 528 ms, max
630 ms); worker RSS peak 1,291 MiB.

## Physics 48

18/48 overall; test 14/36; calibration 4/12; FR 8/24, EN 10/24. With four
options, 12/48 is chance level. Seven task types are 2/2 (hydrostatic
pressure, kinetic energy, lift efficiency, missing capacity, parallel
resistance, period, potential energy), four are 1/2 and thirteen are 0/2.
Median 170 ms per case; worker RSS peak 1,186 MiB. D3 Flash Q8 scored 39/48
and D3 lite (macOS) 14/48 on the same pack.

## Limits

- One checkpoint, one runtime, one device, one pass per case; FR/EN and
  catalogue variants are correlated within families.
- A new macOS CPU runtime identity: the identical 65/132 context total with
  the historical Linux row is an observation, not a claim of bitwise parity.
- Closed choices among supplied proposals: no tool execution, arguments,
  agent loop, retrieval or product qualification.
- Worker RSS is the process's own `ru_maxrss`; latency is descriptive.
- References pending human review.

Next in the revised cohort order: D3 nano, then D3 mini, on the same macOS
CPU runtime family.
