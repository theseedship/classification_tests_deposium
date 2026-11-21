# Uzu Vulkan on WSL: hardware exposed, device requirements unmet

1 November 2026. A process-local Mesa Dozen driver exposes the RTX 5060 to
Linux Vulkan inside WSL. The unchanged Uzu Vulkan branch still refuses this
device: Dozen advertises Vulkan **1.2.354**, below Uzu's **1.4** requirement.
A direct call to upstream `Engine::<Vulkan>::new()` returns
`Backend(Context(NoSuitableDevice))`; it does not reproduce the native Windows
model-loading crash. No WSL GPU model was loaded or executed.

## Scope and identities

- Upstream Uzu remains pinned to
  [`95e8f2282daf0fb78938b620f835b8fd3d716c73`](https://github.com/trymirai/uzu/tree/95e8f2282daf0fb78938b620f835b8fd3d716c73).
  Its source, version checks and device requirements are unchanged.
- Host environment: Ubuntu 24.04 under WSL2, kernel 6.6.87.2. The initially
  installed Mesa 25.2.8 package omitted Dozen; its Vulkan discovery exposed
  only software CPU rendering. The D3D12 bridge and `/dev/dxg` already existed.
- Experimental driver: **Mesa 26.2.6~kisak1~n**, from the third-party
  [kisak-mesa archive](https://launchpad.net/~kisak/+archive/ubuntu/kisak-mesa),
  extracted into an ignored local prefix. No repository was added to apt and
  no system package, driver, service or WSL configuration was changed.
- Local dependencies: Ubuntu `libdisplay-info1` 0.1.1-2build1 and `vulkan-tools`
  1.3.275.0+dfsg1-1, likewise downloaded and extracted rather than installed.
  The package index signature, index hash and Mesa package hash were verified.
  The public signing-key fingerprint was checked against Launchpad metadata.

Dozen is a Vulkan-to-D3D12 translation path. A Microsoft WSL contributor
[identifies this route](https://github.com/microsoft/WSL/issues/41410); it is
distinct from using the native Windows NVIDIA Vulkan driver. A later
[WSLg issue](https://github.com/microsoft/wslg/issues/1492) reports a different
NVIDIA setup crashing during device creation. That external report is not
our observation: both Dozen enumeration and the feature query completed here.

## Measured matrix

| Check | Observation | Qualification |
|---|---|---|
| Corrected system software control | `vulkaninfo --summary` completed with llvmpipe | Software control only |
| Private Dozen enumeration | Discrete `Microsoft Direct3D12 (NVIDIA GeForce RTX 5060)` exposed; exit 0 | Hardware discovery, not inference |
| Full Dozen feature query | Completed; Vulkan 1.2.354, Mesa 26.2.6 | Actual translated-driver capabilities |
| Pinned Uzu admission probe | Device rejected as `vulkan_api_version_below_1_4`; exit 3 | No native context or model created |
| Direct upstream context constructor | `Backend(Context(NoSuitableDevice))`; exit 2 | Actual unchanged engine refusal, not merely the external probe's prediction |
| WSL GPU model forward | Not attempted | Zero outputs; campaign `not_run`, zero scored cases |

The feature query also exposes unmet requirements beyond the API version:

| Capability required by Uzu | Dozen observation |
|---|---|
| `storagePushConstant8` | false |
| `storagePushConstant16` | false |
| `shaderSignedZeroInfNanPreserveFloat16` | false |
| `shaderSignedZeroInfNanPreserveFloat32` | false |
| `shaderFloat16` | true |
| Float16/Float32 round-to-even | true |
| Subgroup arithmetic, ballot and shuffle | present |

These are limitations of the measured translated Vulkan interface, not claims
that the physical GPU lacks those abilities. The same machine's native Windows
path advertises Vulkan 1.4.341; see the separate
[native Windows reproduction](UZU_VULKAN_NATIVE_PROBE_20261101.md).

The exact upstream gates are in
[`vk_context.rs`](https://github.com/trymirai/uzu/blob/95e8f2282daf0fb78938b620f835b8fd3d716c73/crates/uzu-engine/src/backends/vulkan/context/vk_context.rs)
and
[`vk_physical_device.rs`](https://github.com/trymirai/uzu/blob/95e8f2282daf0fb78938b620f835b8fd3d716c73/crates/uzu-engine/src/backends/vulkan/device/vk_physical_device.rs).
Lowering only the API check would not establish compatibility. No version
override, emulated capability or weakened check was used.

One initial software-control attempt accidentally resolved the private Mesa
software library, which required an unavailable LLVM 21 runtime. Its error is
retained locally. The corrected control excludes that directory from its
library path; the hardware checks select only the Dozen ICD explicitly.

## Reproduction boundary

Keep the chosen driver and dependencies in a private prefix. Set
`VK_DRIVER_FILES` to its `dzn_icd.json` and `LD_LIBRARY_PATH` to its library
directory, the extracted display-info dependency and `/usr/lib/wsl/lib`, for
the child process only. Select the NVIDIA adapter with
`MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`. Capture exit status, stderr and
capabilities with a deadline before attempting any model.

The repository's [external probe](../native/uzu-vulkan-probe/main.rs) reports
readable observed/required API versions and an explicit rejection reason.
It preserves the source gate instead of calling the Vulkan 1.4 feature-query
chain on an older device. The direct upstream-constructor observation was a
separate executable linked to the same unchanged engine and lockfile cohort.

Raw logs, device identifiers, package archives, library paths and executable
hashes remain under ignored local directories. This report contains reviewed
aggregate observations only. No application service, pretrained weight,
reference dataset, Mac runtime identity or historical score was changed.

## Contribution insight

The Windows and WSL results identify different stages: native Windows reaches
GPU model loading and terminates in a native module; this WSL route exposes
the hardware but fails device admission cleanly. A useful upstream contribution
is the reproducible capability matrix and explicit device-rejection diagnostic,
alongside the small synthetic fixture. This evidence does not justify a
workaround that simply lowers Uzu's advertised Vulkan requirement.

The WSL capability matrix and direct-constructor reproduction were published
in [uzu#1003](https://github.com/trymirai/uzu/issues/1003#issuecomment-6563474281),
with a link to the separate [Windows synthetic-model reproduction](https://github.com/trymirai/uzu/issues/1049).
Both posted bodies were read back and matched their reviewed drafts. These are
diagnostic contributions, not an engine patch or completed GPU qualification.
Cross-machine results and next diagnostics are tracked in
[benchmark #77](https://github.com/theseedship/classification_tests_deposium/issues/77).
