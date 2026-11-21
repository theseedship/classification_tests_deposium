# Uzu on PC: pinned WebGPU source preflight

1 November 2026. **The tested Mac release cannot yet be treated as a D3
GPU runtime for PC.** This is a source-level prerequisite check, not a model
campaign: `unsupported` for the reviewed WebGPU path, `not_run` for the
campaign, zero scored cases, no loaded weights and no observed Uzu backend.

## Revision and finding

The source is official [Uzu 0.6.15 at
`d3d3a5b20a3de507522e1099457d1dae0243effb`](https://github.com/trymirai/uzu/tree/d3d3a5b20a3de507522e1099457d1dae0243effb),
the same revision as the [Mac D3 Flash protocol](UZU_D3_FLASH_M_PROTOCOL_20261101.md).
No global runtime pin, historical result, dataset or reference was changed.

- The [engine manifest](https://github.com/trymirai/uzu/blob/d3d3a5b20a3de507522e1099457d1dae0243effb/crates/uzu-engine/Cargo.toml)
  defaults to `metal` and `cpu`; `webgpu` is an optional build feature. These
  are not CUDA or ROCm backends.
- In the [WebGPU kernel implementation](https://github.com/trymirai/uzu/blob/d3d3a5b20a3de507522e1099457d1dae0243effb/crates/uzu-engine/src/backends/webgpu/kernel.rs),
  `AttentionKernel` and `MatmulKernel` are both `Unsupported<WebGPU>`.
  Their constructors return `WebGPUError::NotSupported`.
- This affects the actual decision model: its
  [decision block](https://github.com/trymirai/uzu/blob/d3d3a5b20a3de507522e1099457d1dae0243effb/crates/uzu-engine/src/encodable_block/decision.rs)
  loads a transformer and a `LinearMatmul` readout. The
  [linear constructor](https://github.com/trymirai/uzu/blob/d3d3a5b20a3de507522e1099457d1dae0243effb/crates/uzu-engine/src/encodable_block/linear/matmul.rs)
  calls the backend's matmul constructor; the
  [attention constructor](https://github.com/trymirai/uzu/blob/d3d3a5b20a3de507522e1099457d1dae0243effb/crates/uzu-engine/src/encodable_block/mixer/attention/mod.rs)
  calls its attention constructor.

Enabling the feature or selecting `UZU_BACKEND=webgpu` therefore does not
complete D3 inference on this revision. The conclusion comes from the source;
it is not an observed native model-loading error. It does not establish a
limitation of every future Uzu revision or of NVIDIA/AMD hardware generally.

A separate read-only source inspection of the upstream HEAD fetched during
this check,
[`798803bba8fc26b2afd61e9a8ae23ab9c16d3994`](https://github.com/trymirai/uzu/blob/798803bba8fc26b2afd61e9a8ae23ab9c16d3994/crates/uzu-engine/src/backends/webgpu/kernel.rs),
found the same unsupported constructors. That revision was not built or used
to replace the frozen Mac runtime identity.

The CPU backend has separate matmul and attention implementations. It remains
a candidate for a distinct CPU qualification, not an automatic GPU fallback or
a qualified D3 deployment. AMD hardware has not been tested here.

A subsequent [native Vulkan branch probe](UZU_VULKAN_NATIVE_PROBE_20261101.md)
tests a separately pinned experimental backend. Its successful context creation
and reproduced synthetic GPU-load failure do not change this WebGPU source
finding or qualify real D3 inference.

## Reproduce the source gate

Python 3.11+ and Git suffice. This command inspects the source; it does not
compile Uzu, download weights or start a service. Use a new ignored output
directory on every attempt:

```bash
git clone --depth 1 --branch 0.6.15 https://github.com/trymirai/uzu.git \
  .cache/uzu-pc/source-0.6.15
python3 scripts/preflight-uzu-pc.py \
  --uzu-source .cache/uzu-pc/source-0.6.15 \
  --output results/uzu-pc-source-preflight-001
```

Expected gate: `unsupported`, with reason
`pinned_webgpu_required_kernels_not_supported`. Exit `1` means unsupported or
unknown source evidence; exit `2` means an invalid prerequisite or output.
There is no successful campaign verdict. Wrong origin/revision, dirty source,
missing evidence, changed hashes and existing outputs cannot become a pass.
The exact-byte evidence hashes also reject line-ending changes.

The private `preflight.json` includes source paths and stays outside Git.
Host device observations, dependency/build logs and any raw runtime archives
also stay local. Device detection, successful compilation and successful model
inference are separate checks; none substitutes for the others.

Offline regression command:

```bash
python3 -B -m unittest discover -s tests -p 'test_uzu*.py' -v
```

The new synthetic controls exercise source identity, unknown/unsupported/error
distinctions and private-output preservation. They use temporary Git
repositories and never call a GPU or model.

## Requirements before a PC campaign

1. Select and review a separately pinned runtime with the required model
   operations implemented on the intended backend; preserve the Mac identity.
2. Demonstrate actual accelerated device access and a native, weight-free
   backend check. A visible NVIDIA device in CUDA tooling does not establish
   WebGPU/Vulkan access.
3. Freeze a PC resource envelope with RAM, VRAM, host reserve, timeout and
   process ownership checks. Do not remove the existing Mac platform gate or
   relabel CPU observations as GPU execution.
4. Verify the existing D3 asset manifest, native input preparation and the
   `/v1/systemone` functional canary before using the shared campaign engine.
   Retain all failures and unchanged dataset/reference bytes.
5. Only after this qualification, compare with llama.cpp on the same machine
   and consider a separate integration behind `deposium-inference`.

The benchmark adapter, Mac launcher and application services are unchanged.
No PC model score is added to the result tables by this preflight.
