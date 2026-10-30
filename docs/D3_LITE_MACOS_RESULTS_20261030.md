# D3 lite on macOS CPU: results

**30 October 2026.** First Wave B candidate of the capability cohort, executed
under the [dated protocol](D3_LITE_MACOS_CPU_PROTOCOL_20261030.md) on a newly
pinned macOS arm64 CPU runtime. This is a **new runtime identity**; the
historical Linux/WSL CPU row for D3 lite is unchanged and not merged with it.
References are agent-authored and pending human review.

| Pack | Passed / scored | Eligible | Test split | Statuses |
|---|---:|---:|---:|---|
| Synthetic control | — | 0 scored | — | two controls passed (short choice, oversized refusal) |
| Technical canary (12 calibration) | 12 / 12 valid | 12 | — | no accuracy gate |
| Context 132 (anchor) | **94 / 132** | 132 | 49 / 66 | 132 `ok` |
| Tool proposal 24 (provisional) | 19 agreements / 24 valid | 24 | — | 24 `ok`; zero qualified cases |
| Capability 192 | **168 / 192** | 192 | 80 / 96 | 192 `ok` |
| Physics 48 | **14 / 48** | 48 | 12 / 36 | 48 `ok` |

Every pack was collected completely with no `missing`, `unsupported`, `error`,
`timeout` or `abstain` case. Aggregates:
[context and tool](evidence/d3-lite-macos-20261030/analysis.json),
[capability](evidence/d3-lite-macos-20261030/capability.json),
[physics](evidence/d3-lite-macos-20261030/physics.json). Raw outputs, local
paths and process data stay in the ignored archives.

## Identity

| Item | Observed |
|---|---|
| Model | `vllm-sr/d3-lite` at `a8d25a91…`, 31 files verified against the public manifest; backbone 852,985,920 parameters, readout [255, 1024] |
| Runtime | macOS arm64 CPU, Python 3.12.16, Torch 2.14.0 (macOS wheel), Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3; lock `runtimes/d3-macos/runtime.lock`; worker-reported versions equal the lock |
| Settings | two threads, 4096 tokens, backbone bfloat16, readout float32, 6,144 MiB worker ceiling, 60 s per call |
| Host | Apple M5 Pro, 64 GiB unified memory; available-memory estimate from vm_stat |
| Load | 5.2 s model load; 6.6 s adapter initialization; 717 MiB after load |

## Context 132 and tool 24

94/132 overall (test 49/66; FR 45/66, EN 49/66). The historical Linux/WSL run
of the same checkpoint scored 95/132 (test 50/66): one case apart, on a
different platform, Torch wheel and sampled-memory method, so the two rows are
reported side by side rather than compared as repeats. Tool proposals: 24
valid decisions, 19 provisional agreements, zero semantically qualified cases.
Median 3.2 s per case (max 4.1 s); worker RSS peak 1,592 MiB.

## Capability 192

168/192 overall; test 80/96; FR 84/96, EN 84/96; compact 85/96, expanded 83/96.

| Track | Correct / total |
|---|---:|
| Observations (next step after fixed tool observations) | 64 / 64 |
| Arguments and dependencies | 57 / 64 |
| Selection (capability/tool-set proposals) | 47 / 64 |

Selection errors concentrate on multi-tool choices (27/40) and source choice
(4/8); arguments errors on dependency order (7/12) and argument binding
(18/20). Every observation-track task type is 4/4. Median 13.3 s per case
(min 6.3 s, p95 23.0 s, max 29.7 s): the expanded 32-card catalogues approach
the 4096-token limit on a two-thread CPU worker. Worker RSS peak 1,873 MiB.

For scale only: D3 Flash Q8 and Clef Flash Q8 reached 192/192 on this pack
under a native Metal runtime. A 0.85B CPU classifier at 168/192 is a different
size class and runtime; the packs' references await human review and the
four-proposal format caps what any score can mean.

## Physics 48

14/48 overall; test 12/36; calibration 2/12; FR 8/24, EN 6/24. With four
options, 12/48 would be chance level. Of 24 task types, five are 2/2
(accelerated velocity, electrical power, parallel resistance, period,
potential energy), four are 1/2 and fifteen are 0/2. Median 3.1 s per case;
worker RSS peak 1,602 MiB. D3 Flash Q8 scored 39/48 on the same pack.

This is finite rule application with the law supplied in the input; the
result says that this sub-1B decision checkpoint does not perform it, not
that it lacks "physics knowledge".

## Limits

- One checkpoint, one runtime, one device, one pass per case; FR/EN and
  catalogue variants are correlated within families.
- A new macOS CPU runtime identity: numeric parity with the historical Linux
  CPU row is not assumed and the two are not pooled.
- Closed choices among supplied proposals: no tool execution, arguments,
  agent loop, retrieval or product qualification.
- Worker RSS is the process's own `ru_maxrss`; latency is descriptive.
- References pending human review; a low physics score is not a reference defect.

Next in the revised cohort order: Vela 2.0 0.3B, D3 nano and D3 mini on the
same macOS CPU runtime family, each with its own protocol and archives.
