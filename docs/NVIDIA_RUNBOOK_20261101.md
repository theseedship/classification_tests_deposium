# NVIDIA runbook: D3 GGUF on CUDA, and the 8 GB on-device budget

**1 November 2026.** Step-by-step commands for an NVIDIA machine (WSL2 or
native Linux), for [issue #65](https://github.com/theseedship/classification_tests_deposium/issues/65).
Two goals:

1. **Bench rows:** the D3 GGUF models on CUDA, same packs and protocol as the
   Apple Metal rows ([protocol](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md),
   [Metal results](D3_SMALL_GGUF_METAL_RESULTS_20261101.md),
   [deployment variants](DEPLOYMENT_VARIANTS_RESULTS_20261101.md)).
2. **8 GB budget (exploratory):** can a D3 decision model, LFM3-1.7B Q4 and the
   BGE v2-m3 reranker stay loaded together on an 8 GB card?

Everything needed is in this repository. What is not (model files, the
llama.cpp build, archives) is recreated from pinned identities under the
ignored `results/` directory; nothing from another machine is required.

## 0. Prerequisites

NVIDIA driver and CUDA toolkit (`nvcc`), `cmake`, a C++ compiler, `git`,
Python 3.12 and about 25 GB free disk. Record for the report: GPU model and
VRAM, driver and CUDA versions, WSL2 or native Linux, CPU model. Never
hostnames, user names or paths.

```bash
git clone https://github.com/theseedship/classification_tests_deposium
cd classification_tests_deposium
python3.12 -m unittest discover -s tests   # offline; some adapter tests need local sockets
```

## 1. llama.cpp at the pin, built for CUDA

The source checkout must stay clean; the build is out of tree.

```bash
R=$PWD/results; mkdir -p $R/sources $R/runtime-cuda
git clone https://github.com/ggml-org/llama.cpp.git $R/sources/llama-d3
git -C $R/sources/llama-d3 checkout --detach efe3626b119ff81033e309c3ba07a770bef2c546
cd $R/sources/llama-d3
cmake -S . -B $R/runtime-cuda/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_APP=OFF -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TOOLS=ON
cmake --build $R/runtime-cuda/build --target llama-server -j
git status --porcelain --untracked-files=all | wc -l   # must print 0
cd -
python3.12 - <<'EOF'
import hashlib, json
binary = "results/runtime-cuda/build/bin/llama-server"
json.dump({"repository": "https://github.com/ggml-org/llama.cpp.git",
           "revision": "efe3626b119ff81033e309c3ba07a770bef2c546",
           "binary_sha256": hashlib.sha256(open(binary, "rb").read()).hexdigest()},
          open("results/runtime-cuda/runtime-manifest.json", "w"), indent=2)
EOF
python3.12 scripts/build-systemone-preflight.py --source-dir $R/sources/llama-d3 \
  --runtime-build-dir $R/runtime-cuda/build --output-dir $R/preflight-helper
```

## 2. Models, pinned and verified

```bash
for m in d3-lite-q8 d3-nano-q8 d3-mini-q8 d3-mini-q4 d3-flash-q4 lfm3-1.7b-q4 bge-reranker-v2-m3-q8; do
  python3.12 scripts/fetch-gguf.py --assets profiles/$m-assets.json --output-dir results/models
done
```

| Model | File | Size |
|---|---|---:|
| D3 lite Q8 | `vllm-d3-lite-Q8_0.gguf` | 1.1 GB |
| D3 nano Q8 | `vllm-d3-nano-Q8_0.gguf` | 2.6 GB |
| D3 mini Q8 / Q4_K_M | `vllm-d3-mini-Q8_0.gguf` / `-Q4_K_M` | 5.2 / 3.7 GB |
| D3 Flash Q4_K_M | `vllm-d3-flash-Q4_K_M.gguf` | 6.6 GB |
| LFM3-1.7B Q4_K_M | `LFM3-1.7B-Q4_K_M.gguf` | 1.1 GB |
| BGE reranker v2-m3 Q8 | `bge-reranker-v2-m3-Q8_0.gguf` | 0.6 GB |

## 3. Bench rows on CUDA

One model at a time, nothing else running on the GPU. The series script
prepares each pack (vocabulary only), runs it through the pinned
`llama-server`, refuses to fall back to CPU, skips completed phases and samples
GPU memory with `nvidia-smi` beside each archive.

```bash
export LLAMA_SOURCE=$PWD/results/sources/llama-d3 LLAMA_RUNTIME=$PWD/results/runtime-cuda \
       PREFLIGHT=$PWD/results/preflight-helper/systemone-preflight
for model in lite-q8 nano-q8 mini-q8 mini-q4 flash-q4; do
  scripts/run-gguf-gpu-series.sh cuda $model
done
```

Packs, in order: facade routing easy/advanced/complex, context, capability,
physics, passage relevance v2, human confirmation (nine and eight options),
passage evidence rotation 0. Each line prints `"completed": true` and the
peak GPU memory. Envelopes: `small-gguf-8g-v1` for lite, nano and mini;
`d3-flash-q4-12g-v1` for Flash Q4 (it needs 20 GiB of free host memory at
start).

**Publish** only the aggregates, one file per model, with the existing
exporter (it verifies seals, pack bytes, asset manifest, pinned revision and
full CUDA offload):

```bash
D=results/gpu-cuda-runs
python3.12 scripts/export-gguf-gpu-campaign.py --label D3miniQ8Cuda --assets profiles/d3-mini-q8-assets.json \
  --backend cuda --hardware "<GPU model>; <VRAM> GiB; <WSL2|Linux>" --protocol docs/D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md \
  --phase context=$D/d3-mini-q8-cuda-context-001 --phase capability=$D/d3-mini-q8-cuda-capability-001 \
  --phase physics=$D/d3-mini-q8-cuda-physics-001 --phase passages=$D/d3-mini-q8-cuda-passages-001 \
  --private-analysis results/export-d3-mini-q8-cuda --output docs/evidence/d3-gguf-cuda-<date>/d3-mini-q8.json
python3 scripts/check-public-content.py
```

Then open a pull request with the aggregates and the GPU identity. Archives,
`.vram.csv` files and logs stay in `results/`.

## 4. The 8 GB budget (exploratory, not a bench row)

Question: with LFM3-1.7B Q4 and the BGE reranker resident, does a D3 decision
model still fit, and what is the peak GPU memory? Estimates from the Mac
(not measured on NVIDIA):

| Combination | D3 | LFM3 Q4 | BGE Q8 | Estimate |
|---|---:|---:|---:|---:|
| D3 Flash Q4_K_M + LFM3 + BGE | 6.6 | 1.2 | 0.7 | ~9 GB, expected not to fit |
| D3 mini Q4 + LFM3 + BGE | 3.9 | 1.2 | 0.7 | ~6.5 GB |
| D3 nano Q8 + LFM3 + BGE | 2.8 | 1.2 | 0.7 | ~5.5 GB |

LFM3 needs a llama.cpp newer than the pin (its architecture was added after
12 October 2026); use a separate recent build for it only. BGE runs on the
pinned build.

```bash
# terminal 1: LFM3 on the GPU (recent llama.cpp build, CUDA)
<recent>/llama-server -m results/models/LFM3-1.7B-Q4_K_M.gguf -ngl 99 -c 8192 --port 12001
# terminal 2: BGE reranker on the GPU (pinned build)
results/runtime-cuda/build/bin/llama-server -m results/models/bge-reranker-v2-m3-Q8_0.gguf --reranking -ngl 99 --port 12002
# terminal 3: one LFM3 generation and one rerank call, so both have allocated their buffers
curl -s localhost:12001/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Résume en une phrase : le routeur choisit un outil."}],"max_tokens":64}'
curl -s localhost:12002/v1/rerank -H 'Content-Type: application/json' \
  -d '{"query":"capitale de la France","documents":["Paris est la capitale.","Les bananes sont jaunes."]}'
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
# then the D3 phases with both servers resident (separate output directory)
OUT=results/gpu-cuda-budget scripts/run-gguf-gpu-series.sh cuda mini-q4 context facade
OUT=results/gpu-cuda-budget scripts/run-gguf-gpu-series.sh cuda flash-q4 context facade
```

Report, per D3 model: whether the phase completed (an out-of-memory load is a
result, not an error to hide), the `nvidia-smi` peak printed by the script
(it includes the two resident servers and the desktop), the median call time
from the archive and, for comparison, the same phase's call time without the
other servers. Note whether WSL2 or native Linux, and anything else using the
GPU.

## Where Uzu fits

Uzu is the fastest engine for D3 Flash on the Mac
([results](DEPLOYMENT_VARIANTS_RESULTS_20261101.md)), but its release CLI
targets Apple Metal. Its source has an experimental WebGPU backend
(Vulkan/DirectX 12) that is not enabled in the release; it is not part of
this runbook. A smaller D3 Flash GGUF (about 4.5 GB) is the planned NVIDIA
counterpart of Mirai's 4-bit pack and will be added here once measured on the
Mac.
