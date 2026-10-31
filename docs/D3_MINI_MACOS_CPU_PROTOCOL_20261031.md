# D3 mini on macOS CPU: complementary-pack protocol

**Fixed on 31 October 2026, before any prediction.** Fourth Wave B candidate
in the revised execution order of the
[capability cohort](CAPABILITY_CAMPAIGN_PLAN.md#initial-cohort-and-order),
after [D3 lite](D3_LITE_MACOS_CPU_PROTOCOL_20261030.md),
[Vela 2.0 0.3B](VELA2_03_MACOS_CPU_PROTOCOL_20261030.md) and
[D3 nano](D3_NANO_MACOS_CPU_PROTOCOL_20261030.md). Tracked by issue #49.
Candidate, packs, references and scorers are unchanged from the cohort plan.

The historical D3 mini observation ran on Linux/WSL CPU (119/132). This is a
**new runtime identity** (macOS arm64 CPU) reported beside it, never merged
with it.

## Fixed identity

| Item | Fixed value |
|---|---|
| Model | `vllm-sr/d3-mini` at `a475367de0d8133a3c1a2a0dc12303d89cfa2ab4`; 32 files (8.48 GiB), every size and SHA-256 bound by the unchanged public [asset manifest](../profiles/d3-mini-assets.json); backbone 4,539,265,536 parameters, readout [255, 2560] |
| Adapter | `d3` (`bridges/d3-worker.py`), CPU, backbone bfloat16, readout float32, loading mode `native-d3-bf16-readout-fp32`, two threads, 4096 tokens, 14,336 MiB worker RSS ceiling (the historical Linux/WSL peak was 7.55 GiB) |
| Runtime | the pinned macOS arm64 environment [`runtimes/d3-macos/runtime.lock`](../runtimes/d3-macos/runtime.lock), unchanged since D3 lite; the worker refuses any version drift |
| Profiles | [`profiles/d3-mini-macos-cpu.json`](../profiles/d3-mini-macos-cpu.json) (`d3-mini-macos-cpu-v1`, **120 s per call**) for context, tool and physics; [`profiles/d3-mini-macos-cpu-capability.json`](../profiles/d3-mini-macos-cpu-capability.json) (`d3-mini-macos-cpu-capability-v1`, **300 s per call**) for the capability pack; otherwise identical; contract `bench.context-choice`, shared prompt |
| Packs | context 132 (`767e239c…5616`), capability 192 (`0b409a09…5eb0`), physics 48 (`e21cd2e0…7307`), tool 24; unchanged |
| Host memory | at least 18,432 MiB estimated available before loading (adapter rule for this model) |
| Timeout policy | the [worker restart policy](CPU_WORKER_RESTART_POLICY_20261031.md): a timed-out case is recorded as `timeout`, the worker is relaunched at most three times per campaign, later cases are attempted |

## Why these timeouts

The per-call values are fixed here, before the first prediction, from the
measured latencies of the two smaller D3 rows on the same runtime, host and
settings. Backbone sizes: lite 0.85B, nano 2.21B, mini 4.54B.

| Pack | D3 lite max (p95) | D3 nano max (p95) | nano/lite | Expected mini max (×2.1 to ×3 of nano) | Fixed timeout |
|---|---:|---:|---:|---:|---:|
| Context 132 | 4.0 s (3.8) | 9.3 s (8.5) | 2.3 | 20–28 s | 120 s |
| Physics 48 | 4.2 s (3.8) | 12.8 s (12.1) | 3.0 | 27–38 s | 120 s |
| Capability 192 | 29.5 s (22.8) | 64.0 s (48.9) | 2.2 | 135–192 s | 300 s |

The tool pack uses context-sized inputs and takes the 120 s profile. 300 s is
the schema maximum for the `d3` adapter, admitted for nano's capability
[amendment](D3_NANO_MACOS_TIMEOUT_AMENDMENT_20261031.md); it leaves a margin
of about 1.6× over the upper estimate. If a capability case still exceeds it,
the restart policy keeps the rest of the campaign attempted and the case is
reported as `timeout` in its denominator; no value is raised after the fact.

## Order of execution

1. Synthetic control (`scripts/check-d3-cpu.py`), zero scored cases.
2. Technical canary: the twelve calibration IDs of the sequence; valid
   identity, runtime pins and decisions; **no accuracy threshold**.
3. Context 132 (anchor), capability 192, physics 48, then tool proposal 24,
   each with a fresh worker and a new archive.

```bash
python3 -m deposium_bench run --profile profiles/d3-mini-macos-cpu.json \
  --dataset datasets/<pack>/cases.jsonl --output results/d3-mini-macos-<pack>-NEXT
python3 -m deposium_bench run --profile profiles/d3-mini-macos-cpu-capability.json \
  --dataset datasets/capability-choice-v1/cases.jsonl --output results/d3-mini-macos-capability-NEXT
```

## Reporting

Report each pack with its full denominator and every `missing`, `unsupported`,
`error`, `timeout` and `abstain` status; test splits apart; FR/EN, track,
catalogue view and domain groups where declared. Record load time, call
latencies, sampled worker RSS and any worker restart (from the sealed
`adapter-final.json`) with their scopes. Add the observation as a new runtime
identity (`D3 mini · macOS CPU`) through the shared exporter and results
generator, never by overwriting the historical row.

A 4.5B classifier on four-proposal synthetic choices measures closed-choice
agreement with agent-authored references pending human review. It does not
qualify tool execution or a product workflow.
