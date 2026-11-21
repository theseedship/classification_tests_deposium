# llama.cpp CUDA canary on WSL2, 21 November 2026

The GPU was an RTX 5060 (8 GB class) under WSL2 with NVIDIA driver 610.88.
Both runs used their verified, official x64 CUDA 12.8 release archives, the same
[D3 lite Q8 asset](../profiles/d3-lite-q8-assets.json), and the same twelve
existing calibration rows in frozen context-choice-v1 file order. Each native
vocabulary helper used the headers and server libraries of its candidate.
The 12 request hashes matched across runs. Each server ran with a context and
batch of 4096 and one slot. The original benchmark revision and historical
archives retain their own pin.

| Official build | Valid and correct | Layers on CUDA | Adapter median / p95 | Device memory reported by llama.cpp |
|---|---:|---:|---:|---:|
| [b11572](https://github.com/ggml-org/llama.cpp/releases/tag/b11572), `efe3626b119ff81033e309c3ba07a770bef2c546` | 12/12 | 25/25 | 18.86 / 20.94 ms | 1,120 MiB |
| [v1.0.0 / b12359](https://github.com/ggml-org/llama.cpp/releases/tag/b12359), `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` | 12/12 | 25/25 | 17.27 / 23.53 ms | 1,120 MiB |

All twelve choices matched. The native checks observed unauthenticated and
input-overflow rejection and clean server exits. The p95 uses the nearest rank
and is the maximum of twelve calls. These were single runs of a calibration
canary. The timings describe this small sample.

The official b12359 **CUDA 13.5** bundle instead exited with a segmentation
fault at `--list-devices`, before loading a model. The WSL driver exposed CUDA
UMD 13.3 at the time. The CUDA 12.8 bundle at the same source commit detected
the GPU and was used for the canary. The cause of the 13.5 failure was not
isolated. The results and startup failure are recorded in
[campaign #65](https://github.com/theseedship/classification_tests_deposium/issues/65#issuecomment-7056316198).

## Reproduce device enumeration

Extract each Ubuntu x64 bundle and its matching CUDA runtime libraries into
separate directories. Set the variables below to the executable directory
and CUDA runtime library directory for one bundle. Repeat with CUDA 12.8 and
13.5 from b12359. The commands exercise enumeration before any model is opened.

```sh
export LD_LIBRARY_PATH="$LLAMA_BIN_DIR:$LLAMA_CUDA_LIB_DIR:/usr/lib/wsl/lib"
nvidia-smi
"$LLAMA_BIN_DIR/llama-server" --version
"$LLAMA_BIN_DIR/llama-server" --list-devices
```

The model comparison used the first 12 calibration cases in
[context-choice-v1](../datasets/context-choice-v1/README.md) in file order.
Use the same frozen inputs, model asset, context, batch and slot count
to compare the two CUDA 12.8 builds. Report the CUDA bundle separately
from the llama.cpp source revision.
