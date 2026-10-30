# Vela 2.0 0.3B on macOS CPU: complementary-pack protocol

**Fixed on 30 October 2026, before any prediction on the capability or physics
packs.** Executed the same day; see the [results](VELA2_03_MACOS_RESULTS_20261030.md).
Second Wave B candidate in the revised execution order of the
[capability cohort](CAPABILITY_CAMPAIGN_PLAN.md#initial-cohort-and-order), after
[D3 lite on macOS CPU](D3_LITE_MACOS_CPU_PROTOCOL_20261030.md). Candidate,
packs, references and scorers are unchanged from the cohort plan.

The historical Vela 2.0 0.3B observation ran on Linux/WSL CPU (65/132). This
is a **new runtime identity** (macOS arm64 CPU) reported beside it, never
merged with it.

## Fixed identity

| Item | Fixed value |
|---|---|
| Model | `vllm-sr/Vela-2.0-0.3B` at `d6f03aa9baca4f9017fa8f8e9c2764d3bed3f409`; 38 files, every size and SHA-256 bound by the unchanged public [asset manifest](../profiles/vela2-03-assets.json) |
| Adapter | `vela2` (`bridges/vela2-worker.py`), CPU, float32, loading mode `hf-automodel-fp32`, two threads, 4096 tokens, 4,096 MiB worker RSS ceiling, 30 s per call |
| Runtime | the same pinned macOS arm64 environment as D3 lite, [`runtimes/d3-macos/runtime.lock`](../runtimes/d3-macos/runtime.lock) (Python 3.12.16, Torch 2.14.0 macOS wheel, Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3); the worker refuses any version drift |
| Profile | [`profiles/vela2-03-macos-cpu.json`](../profiles/vela2-03-macos-cpu.json), `vela2-03-macos-cpu-v1`; contract `bench.context-choice`, shared prompt |
| Packs | context 132 (`767e239c…5616`), capability 192 (`0b409a09…5eb0`), physics 48 (`e21cd2e0…7307`); unchanged |
| Host memory | at least 8,192 MiB estimated available before loading (adapter rule for this model), checked again after each case; macOS available memory is the vm_stat reclaimable-page estimate; worker RSS is sampled through the owned process group |

## Platform port, fixed before predictions

The Vela2 adapter and worker read `/proc/meminfo` and `/proc/<pid>/status`
and divide `ru_maxrss` by 1024; on macOS those files do not exist and
`ru_maxrss` is in bytes. The port adds the same Darwin branch as the D3 path
(vm_stat estimate, process-group RSS, platform divisor). Linux behavior,
scoring, prompt, projection and references are unchanged.

## Order of execution

1. Synthetic control (`scripts/check-vela2-cpu.py`), zero scored cases.
2. Technical canary: the twelve calibration IDs of the sequence; valid
   identity, runtime pins and decisions; **no accuracy threshold**.
3. Context 132, then tool proposal 24 (provisional agreement), then
   capability 192, then physics 48, each with a fresh worker and a new archive.

```bash
python3 -m deposium_bench run --profile profiles/vela2-03-macos-cpu.json \
  --dataset datasets/<pack>/cases.jsonl --output results/vela2-03-macos-<pack>-NEXT
```

## Reporting

Report each pack with its full denominator and every `missing`, `unsupported`,
`error`, `timeout` and `abstain` status; test splits apart; FR/EN, track,
catalogue view and domain groups where declared. Record load time, call
latencies and sampled worker RSS with their scopes. Add the observation as a
new runtime identity (`Vela 2.0 0.3B · macOS CPU`) through the shared exporter
and results generator, never by overwriting the historical row.

A 0.3B classifier on four-proposal synthetic choices measures closed-choice
agreement with agent-authored references pending human review. It does not
qualify tool execution or a product workflow.
