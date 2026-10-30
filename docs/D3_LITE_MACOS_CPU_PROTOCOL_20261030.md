# D3 lite on macOS CPU: complementary-pack protocol

**Fixed on 30 October 2026, before any prediction on the capability or physics
packs.** This is the first Wave B candidate of the
[capability cohort](CAPABILITY_CAMPAIGN_PLAN.md), executed out of the plan's
nominal order (revision 4 of the [sequence](../plans/capability-choice-v1-sequence.json)
records the reordering: small candidates first, because their platform-specific
runtime is cheaper to qualify than the 27B native path). The candidate, packs,
references and scorers are unchanged.

The historical D3 lite observation ran on Linux/WSL CPU. This is a **new
runtime identity** (macOS arm64 CPU); it does not replace the historical row and
its scores are not comparable to it as if the runtime were the same.

## Fixed identity

| Item | Fixed value |
|---|---|
| Model | `vllm-sr/d3-lite` at `a8d25a91ef75552803f7009d25b7bd435991abd9`; 31 files, every size and SHA-256 bound by the unchanged public [asset manifest](../profiles/d3-lite-assets.json); backbone 852,985,920 parameters, readout [255, 1024] |
| Adapter | `d3` (`bridges/d3-worker.py`), CPU, backbone bfloat16, readout float32, loading mode `native-d3-bf16-readout-fp32`, two threads, 4096 tokens, 6,144 MiB worker RSS ceiling, 60 s per call |
| Runtime | isolated macOS arm64 environment pinned by [`runtimes/d3-macos/runtime.lock`](../runtimes/d3-macos/runtime.lock): Python 3.12.16, Torch 2.14.0 (macOS wheel, not the Linux `+cpu` wheel), Transformers 5.17.0, Tokenizers 0.23.2, Safetensors 0.8.0, NumPy 2.5.3, Hub 1.33.0, Accelerate 1.15.0, Einops 0.8.2, Pillow 12.3.0, Psutil 7.2.2. The worker refuses any version drift from the lock |
| Profile | [`profiles/d3-lite-macos-cpu.json`](../profiles/d3-lite-macos-cpu.json), `d3-lite-macos-cpu-v1`; contract `bench.context-choice`, the shared prompt |
| Packs | context 132 (`767e239c…5616`), capability 192 (`0b409a09…5eb0`), physics 48 (`e21cd2e0…7307`); all unchanged |
| Host memory | the worker needs at least 8,192 MiB estimated available before loading (adapter rule for this model); macOS available memory is the vm_stat reclaimable-page estimate; worker RSS on macOS is sampled through the owned process group |

## Platform port, fixed before predictions

The D3 adapter, worker and smoke script read `/proc/meminfo` and `/proc/<pid>/status`,
which do not exist on macOS, and the worker's `ru_maxrss` is in bytes on macOS.
The port adds a Darwin branch that uses the same vm_stat estimate and
process-group RSS helpers as the Vela 3 fast and native adapters, and divides
`ru_maxrss` by the platform's unit. Linux behavior is unchanged. No scoring,
prompt, projection or reference code changed.

## Order of execution

Each step is a new archive; failed or partial attempts are kept.

1. **Synthetic control** (`scripts/check-d3-cpu.py`): one short choice and one
   oversized input through the real worker; zero scored cases. Required before
   any dataset work.
2. **Technical canary**: the twelve calibration IDs of the sequence
   (`ccv1-{selection,arguments,observations}-02-{compact,expanded}-{fr,en}`).
   Gate: correct identity, device and runtime pins, complete inputs, valid
   decisions. **No accuracy threshold.**
3. **Historical anchor**: context 132 under this runtime (report test/66 apart).
4. **Capability pack**: 192 cases (report test/96 and every declared group).
5. **Physics pack**: 48 cases (report test/36 apart).

Run each dataset with the shared engine, a fresh worker and a new output:

```bash
python3 -m deposium_bench run --profile profiles/d3-lite-macos-cpu.json \
  --dataset datasets/<pack>/cases.jsonl --output results/d3-lite-macos-<pack>-NEXT
```

## Reporting

Report each pack with its full denominator and every `missing`, `unsupported`,
`error`, `timeout` and `abstain` status; test splits separately; FR/EN,
track, catalogue view and domain groups where the pack declares them. Record
load time, first and subsequent call latencies and sampled worker RSS with
their scopes. Add the observation to the shared results generator as a new
runtime identity (`D3 lite · macOS CPU`), never by overwriting the historical
Linux/WSL row.

A sub-1B classifier's scores on four-proposal synthetic choices measure
closed-choice agreement with agent-authored references pending human review.
They do not qualify tool execution, a product workflow or the historical CPU
numbers on this platform.
