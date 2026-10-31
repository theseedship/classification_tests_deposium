# D3 nano on macOS CPU: complementary-pack protocol

**Fixed on 30 October 2026, before any prediction on the capability or physics
packs.** Executed 30–31 October; see the [results](D3_NANO_MACOS_RESULTS_20261031.md):
the capability pack is a partial collection (one 60 s timeout, then 149 cases
unattempted because the adapter fails closed), retained as recorded. Third Wave B candidate in the revised execution order of the
[capability cohort](CAPABILITY_CAMPAIGN_PLAN.md#initial-cohort-and-order), after
[D3 lite](D3_LITE_MACOS_CPU_PROTOCOL_20261030.md) and
[Vela 2.0 0.3B](VELA2_03_MACOS_CPU_PROTOCOL_20261030.md). Candidate, packs,
references and scorers are unchanged from the cohort plan.

The historical D3 nano observation ran on Linux/WSL CPU (117/132). This is a
**new runtime identity** (macOS arm64 CPU) reported beside it, never merged
with it.

## Fixed identity

| Item | Fixed value |
|---|---|
| Model | `vllm-sr/d3-nano` at `3aeb1c22a5632aac72353c36b3d0111c40e7dbf4`; 30 files, every size and SHA-256 bound by the unchanged public [asset manifest](../profiles/d3-nano-assets.json); backbone 2,213,241,664 parameters, readout [255, 2048] |
| Adapter | `d3` (`bridges/d3-worker.py`), CPU, backbone bfloat16, readout float32, loading mode `native-d3-bf16-readout-fp32`, two threads, 4096 tokens, 12,288 MiB worker RSS ceiling, 60 s per call |
| Runtime | the pinned macOS arm64 environment [`runtimes/d3-macos/runtime.lock`](../runtimes/d3-macos/runtime.lock) (Python 3.12.16, Torch 2.14.0 macOS wheel, Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3, Accelerate 1.15.0, Einops 0.8.2); the worker refuses any version drift |
| Profile | [`profiles/d3-nano-macos-cpu.json`](../profiles/d3-nano-macos-cpu.json), `d3-nano-macos-cpu-v1`; contract `bench.context-choice`, shared prompt |
| Packs | context 132 (`767e239c…5616`), capability 192 (`0b409a09…5eb0`), physics 48 (`e21cd2e0…7307`); unchanged |
| Host memory | at least 16,384 MiB estimated available before loading (adapter rule for this model); macOS available memory is the vm_stat reclaimable-page estimate; worker RSS is sampled through the owned process group |

The platform port of the D3 CPU path is the one fixed for D3 lite; no code
changes are specific to this candidate.

## Order of execution

1. Synthetic control (`scripts/check-d3-cpu.py`), zero scored cases.
2. Technical canary: the twelve calibration IDs of the sequence; valid
   identity, runtime pins and decisions; **no accuracy threshold**.
3. Context 132, capability 192, physics 48, then tool proposal 24, each
   with a fresh worker and a new archive.

```bash
python3 -m deposium_bench run --profile profiles/d3-nano-macos-cpu.json \
  --dataset datasets/<pack>/cases.jsonl --output results/d3-nano-macos-<pack>-NEXT
```

## Reporting

Report each pack with its full denominator and every `missing`, `unsupported`,
`error`, `timeout` and `abstain` status; test splits apart; FR/EN, track,
catalogue view and domain groups where declared. Record load time, call
latencies and sampled worker RSS with their scopes. Add the observation as a
new runtime identity (`D3 nano · macOS CPU`) through the shared exporter and
results generator, never by overwriting the historical row.

A 2.2B classifier on four-proposal synthetic choices measures closed-choice
agreement with agent-authored references pending human review. It does not
qualify tool execution or a product workflow.
