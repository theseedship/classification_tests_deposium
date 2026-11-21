# Uzu Vulkan branch: native context and synthetic decision probe

1 November 2026. The experimental upstream Vulkan branch builds unchanged on
Linux and native Windows. Native Windows creates a Vulkan context with a
discrete NVIDIA device eligible. A tiny synthetic decision model runs on CPU,
but native Vulkan model loading terminates before any probabilities return.
**This is a technical reproduction, not a D3 campaign or a qualified GPU model.**

## Frozen identities

- Upstream: [`trymirai/uzu`, Vulkan branch at
  `95e8f2282daf0fb78938b620f835b8fd3d716c73`](https://github.com/trymirai/uzu/tree/95e8f2282daf0fb78938b620f835b8fd3d716c73).
  No upstream file was modified. The native Windows source transfer matched
  all 2,348 tracked files byte for byte.
- Compiler: Rust 1.98.1. Slang 2026.19 matches the version selected by the
  branch's locked Nix environment; the separately downloaded release archives
  were checked against their published SHA-256 digests. Windows also used
  portable libclang 18.1.1 and an existing MSVC toolchain.
- Probe: [`main.rs`](../native/uzu-vulkan-probe/main.rs), an external executable
  calling the upstream public `Engine`, `load_decision_model` and
  `probabilities` APIs. The source checkout remains unchanged.
- Fixture: [`generate_fixture.py`](../native/uzu-vulkan-probe/generate_fixture.py),
  agent-authored synthetic arithmetic weights, not a published model or a
  semantic reference. One attention/MLP layer, dimension 64, vocabulary and
  decision code count 2; six BF16/F32 tensors, 58,112 payload bytes.

The fixture deliberately has a real layer that initializes the residual
shortcut. An empty transformer would not establish a valid forward path.
The tokenizer loads, but these tests supply raw token IDs; text rendering and
tokenization agreement are not qualified.

## Observations

| Check | Observation | Boundary |
|---|---|---|
| Linux external probe build | Completed with the upstream Vulkan feature | No model acquisition or application stack |
| Initial Linux Vulkan device gate | Only software CPU Vulkan was available; GPU gate refused it | Initial system configuration; see the later isolated Dozen check below |
| Native Windows build | Completed with unchanged upstream source on a Windows drive | Source on a WSL network path failed Slang imports |
| Native Windows context | Created; the sole enumerated eligible device was an RTX 5060, Vulkan 1.4.341, driver 610.88 | The helper reports eligibility and expected selection; it does not expose the engine's selected device handle |
| Synthetic CPU inference | All four inputs returned valid, normalized, nonuniform probabilities on Linux and Windows; outputs matched | Implementation control, not model quality |
| Invalid-input controls | Empty input, zero options and excess options rejected on CPU | GPU controls were not reached |
| Synthetic GPU loading | Two attempts terminated during `load_decision_model`, before a completed load or returned probabilities | Native process exception; not a timeout, abstention or incorrect prediction |

The four inputs are `[0]`, `[1]`, `[0,1]` and `[1,0]`, each with two options.
CPU outputs are approximately `[0.829366, 0.170634]` and its reversal, according
to the final input token. These are observations, not regenerated gold answers.
The comparison protocol fixed absolute probability tolerance `0.001`, equal
argmax and three negative controls **before GPU execution**. No GPU output
completed, so CPU/Vulkan parity is **not established**.

Both GPU attempts exited with Windows exception `0x80000003`. Windows
application events named `nvgpucomp64.dll` as the faulting module. The last
external probe stage was `decision_model_load`. Loading includes both memory
transfers and pipeline creation; the evidence does not distinguish invalid
generated shaders, driver behavior, or another triggering condition. A faulting
module alone is not proof of a driver defect.

The attempted full CLI check on Linux also encountered a missing ALSA
development dependency. The successful external engine probe does not qualify
the CLI or `/v1/systemone` server. The real D3 Flash pack was not downloaded
or loaded. Campaign status remains `not_run`, with **zero scored cases**.

## Reproduce without pretrained weights

First check out the exact upstream revision and prepare the external crate:

```bash
python3 scripts/build-uzu-vulkan-probe.py \
  --uzu-source .cache/uzu-pc/source-vulkan-95e8f228 \
  --output results/uzu-vulkan-probe-new
python3 native/uzu-vulkan-probe/generate_fixture.py \
  --output results/uzu-vulkan-fixture-new
```

The builder only prepares files; it never builds, runs a model or downloads
anything. Provide the Slang headers/libraries and libclang explicitly, then
build the generated crate with the recorded compiler. The copied upstream
lockfile needs the external root package resolved; retain the resulting
lockfile and its hash separately from the original preparation receipt.

With the built executable and appropriate native library search path:

```bash
uzu-vulkan-probe
UZU_BACKEND=cpu uzu-vulkan-probe --decision-model results/uzu-vulkan-fixture-new
UZU_BACKEND=vulkan uzu-vulkan-probe --decision-model results/uzu-vulkan-fixture-new
```

On Windows, set `UZU_BACKEND` using the shell's environment syntax. Use a
native drive for Cargo caches, targets and source; place Slang's DLL directory
on the process PATH. Keep each attempt in a new private archive, capture the
process exit and stderr even when stdout is empty, and enforce a deadline.
Context creation is distinct from successful GPU model loading or inference.

The preparation receipts contain local paths and stay under ignored `results/`.
Raw Windows events, device identifiers, build logs, binaries and installed
dependencies also remain local. Only this reviewed aggregate is public-facing.

## Follow-up on Uzu 0.7.3

The 21 November retest used the updated configuration schema and the same
synthetic weights, tokenizer and token inputs. It reproduced the CPU predictions.
Native Vulkan context creation succeeded on Windows. Both GPU model-load
attempts ended with `0x80000003` in `nvgpucomp64.dll` before a probability
was returned. See the [upstream retest](https://github.com/trymirai/uzu/issues/1049#issuecomment-7056315931).

## Contribution boundary

The fixture and probe provide a bounded reproduction candidate for upstream:
CPU execution, real Vulkan context admission, typed invalid-input controls and
a small model that reaches the failing GPU load. The native Windows crash was
reported in [uzu#1049](https://github.com/trymirai/uzu/issues/1049), including
the complete external caller and synthetic fixture generator. Its published
body was read back and matched the reviewed report. No engine fix is claimed.
The benchmark's [coordination issue #77](https://github.com/theseedship/classification_tests_deposium/issues/77)
tracks upstream replies, independent machines and publication of the local harness.

Next diagnostics are a first-chance native stack at the breakpoint and Vulkan
validation with a separately installed portable layer. They should identify a
minimal failing operation before proposing a kernel or driver workaround.
The existing Mac adapter, datasets, references and historical results remain
unchanged.

A subsequent [isolated WSL Dozen probe](UZU_WSL_DOZEN_PROBE_20261101.md)
exposes the RTX as a Linux Vulkan device, but its Vulkan 1.2 interface and
missing capabilities fail the unchanged engine's device requirements. This is
a separate refusal from the native Windows crash; neither is a completed GPU
decision campaign.
