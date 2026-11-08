# Replay a private chat-intent v2 pack

This public guide describes the generic toolkit. The dataset owner supplies the
frozen pack, its restore instructions and trusted manifest hash through a private
channel. A public clone contains no production messages or private baseline.
Keep original data, case files, source identifiers, annotations, raw outputs and
all reports private. Generated files belong under this checkout's ignored
`results/`; never force-add them to public Git.

The pack uses `deposium.intent-private-pack/v2`; its required artifacts include
`manifest.json`, `protocol.frozen.json`, `intent-choice-cards.frozen.json` and
`cases.jsonl`. The owner also supplies the recorded baseline archive, or the
private profile/recordings needed to reconstruct it. Authenticate the received
manifest against the owner's trusted hash before using its listed file hashes.
A matching manifest alone does not establish annotation authenticity.

The public implementation is
[`chat_intent_v2_corpus.py`](../deposium_bench/chat_intent_v2_corpus.py), with
[frozen bilingual cards](../deposium_bench/data/intent-choice-cards.v2.json).
References use the canonical ten intent labels and options `a` through `j`.
The reviewed label, literal review timestamp, source metadata and split group
stay in archival fields. Candidate input contains only the bounded
`message_preview` wrapped as context, the generic question and option
descriptions. The native HTTP projection sends no gold label, source identity,
review metadata or split.

Reuse the exact frozen case/reference/card bytes and whole-family split
assignment. Do not relabel, change criteria, reorder options or tune the rubric
once test predictions have been observed. Record a separately reviewed dataset
version if an annotation must later change. Case language denotes the prompt
language; it does not independently annotate the message language.

## Restore and validate privately

Set `$BENCH_ROOT` to the physical path of this benchmark checkout,
`$PRIVATE_PACK` to the privately restored pack directory, and `$PRIVATE_BASELINE`
to its sealed recorded baseline campaign. Retain the owner's benchmark revision
and hashes. Use new output names for every attempt; tools refuse overwrites.

```bash
cd "$BENCH_ROOT"
python3 -m deposium_bench validate-cases --dataset "$PRIVATE_PACK/cases.jsonl"
python3 - "$PRIVATE_PACK/cases.jsonl" <<'PY'
from pathlib import Path
import sys
from deposium_bench.cases import load_cases
cases, _ = load_cases(Path(sys.argv[1]))
assert cases[0]['split'] == 'calibration', 'First case must be a calibration warm-up'
assert any(case['split'] == 'test' for case in cases), 'Frozen pack needs a test split'
PY
python3 scripts/report-chat-intent-v2.py \
  --baseline "$PRIVATE_BASELINE" --pack-root "$PRIVATE_PACK" \
  --output "$BENCH_ROOT/results/intent-replay-pack-check"
```

The report command verifies listed pack hashes, card equality and baseline
cases against the pack. Validation is structural, not a fresh human annotation
review. If the baseline must be reconstructed, use only the owner's supplied
private profile/recordings with the shared engine:

```bash
python3 -m deposium_bench run --dataset "$PRIVATE_PACK/cases.jsonl" \
  --profile "$PRIVATE_BASELINE_PROFILE" --output "$PRIVATE_BASELINE"
```

Choose a new ignored `results/` path for `$PRIVATE_BASELINE` in that case.
The resulting baseline is explicitly a recorded harness control. Its replay
latency is not the production router's latency.

## Prepare the Mac runtime

Run Mini Q8 first as a hardware/runtime control, then Flash Q8. These are separate
candidate observations; a Mac control does not establish CUDA behavior.
[D3 Flash's model card](https://huggingface.co/vllm-sr/d3-flash) calls it the 9B
model and lists 8.39B total parameters including the vision encoder. This replay
uses the pinned text-only GGUF listed in the asset manifest, without a vision
projector. The larger [D3 model](https://huggingface.co/vllm-sr/d3) is a separate
27B-class checkpoint.

Follow the build requirements in the
[GPU protocol](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md) and
[direct upstream protocol](PHYSICS_FLASH_UPSTREAM_PROTOCOL_20261029.md).
Use a clean `https://github.com/ggml-org/llama.cpp.git` checkout at
`efe3626b119ff81033e309c3ba07a770bef2c546` as `$NATIVE_SOURCE`. Keep the build
outside that source tree. With CMake and the Apple compiler toolchain installed:

```bash
NATIVE_BUILD="$BENCH_ROOT/results/intent-replay-metal-build"
NATIVE_BINARY="$NATIVE_BUILD/bin/llama-server"
NATIVE_MANIFEST="$BENCH_ROOT/results/intent-replay-metal-runtime.json"
HELPER_ROOT="$BENCH_ROOT/results/intent-replay-metal-helper"
cmake -G "Unix Makefiles" -S "$NATIVE_SOURCE" -B "$NATIVE_BUILD" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_METAL=ON -DGGML_CUDA=OFF -DGGML_HIP=OFF -DGGML_VULKAN=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_APP=OFF \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_OPENSSL=OFF \
  -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TOOLS=ON
cmake --build "$NATIVE_BUILD" --target llama-server -j 4
python3 - "$NATIVE_BINARY" "$NATIVE_MANIFEST" <<'PY'
import hashlib, json, sys
from pathlib import Path
binary = Path(sys.argv[1])
with Path(sys.argv[2]).open('x') as stream:
    json.dump({'repository': 'https://github.com/ggml-org/llama.cpp.git',
               'revision': 'efe3626b119ff81033e309c3ba07a770bef2c546',
               'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}, stream)
PY
python3 scripts/build-systemone-preflight.py --source-dir "$NATIVE_SOURCE" \
  --runtime-build-dir "$NATIVE_BUILD" --output-dir "$HELPER_ROOT"
```

The launcher checks the clean source identity and binary hash. Keep compiler,
flags, helper/build provenance and native logs private. A build is preparation;
actual Metal execution requires the launcher's observed full-layer offload.
Provision model files separately at the exact manifest revisions and hashes.
Nothing in ordinary validation downloads weights or starts inference.

A Mac advertised with 64 GB of unified memory shares it between the OS, GPU and
other processes; it is not 64 GB of dedicated VRAM. Check actual available memory
before each phase. The launcher enforces sampled process-group RSS and host
reserve; these are not a complete accounting of all unified GPU allocations.
No fit or completion is promised by physical capacity alone. Keep one campaign
active at a time and preserve partial archives when a guard stops execution.

## Prepare and run each candidate

For the first observation, point `$MODEL_FILE` to the locally provisioned Mini Q8
file and choose a unique attempt label:

```bash
RUN_LABEL=mini-q8-metal-attempt-01
MODEL_ALIAS=d3-mini-q8
ASSETS="$BENCH_ROOT/profiles/d3-mini-q8-assets.json"
ENVELOPE=small-gguf-8g-v1
MAX_RSS_MB=8192
# MODEL_FILE: vllm-d3-mini-Q8_0.gguf, verified against ASSETS
```

For each selected configuration, run the following preparation and campaign.
Preparation must be regenerated locally for that model, alias and exact dataset;
do not reuse another machine's tokenizer/preparation archive.

```bash
PREPARATION="$BENCH_ROOT/results/$RUN_LABEL-preparation"
PILOT="$BENCH_ROOT/results/$RUN_LABEL"
python3 scripts/prepare-native-inputs.py \
  --helper "$HELPER_ROOT/systemone-preflight" \
  --model "$MODEL_FILE" --model-id "$MODEL_ALIAS" --assets-manifest "$ASSETS" \
  --dataset "$PRIVATE_PACK/cases.jsonl" --output "$PREPARATION" \
  --context 4096 --max-rss-mb 2048 --min-free-mb 8192 --max-seconds 600
python3 scripts/run-upstream-native-pilot.py \
  --source-root "$NATIVE_SOURCE" --binary "$NATIVE_BINARY" \
  --runtime-manifest "$NATIVE_MANIFEST" \
  --model "$MODEL_FILE" --model-id "$MODEL_ALIAS" --assets-manifest "$ASSETS" \
  --preparation "$PREPARATION/native-preparation.jsonl" \
  --dataset "$PRIVATE_PACK/cases.jsonl" --output "$PILOT" \
  --backend metal --execution-envelope "$ENVELOPE" \
  --context 4096 --max-rss-mb "$MAX_RSS_MB" --min-free-mb 8192 --max-seconds 1200
```

The full pack must start with a calibration case: the choices launcher repeats
the first case as an excluded technical warm-up before collecting the full pack.
Report test results separately from calibration and combined results. Passing a
test-only file would warm up on a test input and changes this protocol.

Next set `$MODEL_FILE` to `vllm-d3-flash-Q8_0.gguf`, configure Flash Q8 below,
and repeat the preparation and campaign commands:

```bash
RUN_LABEL=flash-q8-metal-attempt-01
MODEL_ALIAS=d3-flash-q8
ASSETS="$BENCH_ROOT/profiles/d3-flash-q8-assets.json"
ENVELOPE=flash-clef-18g-v1
MAX_RSS_MB=18432
```

Flash Q8 uses the default 18 GiB RSS envelope plus 8 GiB host reserve. Its
admission therefore requires at least 26 GiB estimated available memory. Mini's
small-model envelope does not admit this larger file. Fixed context/batches,
single-slot execution, per-call timeout and no automatic retry remain in force.

Optionally, set `$MODEL_FILE` to `vllm-d3-flash-Q4_K_M.gguf`, configure the
separate quantized candidate below, and repeat preparation and campaign:

```bash
RUN_LABEL=flash-q4-metal-attempt-01
MODEL_ALIAS=d3-flash-q4
ASSETS="$BENCH_ROOT/profiles/d3-flash-q4-assets.json"
ENVELOPE=d3-flash-q4-12g-v1
MAX_RSS_MB=12288
```

D3 27B is optional and requires the existing
[27B protocol](D3_27B_CAPABILITY_PROTOCOL_20261030.md), model-specific preparation,
canary and bound calibration/resource receipts. That launcher path gates its
existing datasets and phases; it is not an unrestricted chat-intent launch.
A separate reviewed extension is required before applying it to this pack.
Do not substitute a 27B model into the Flash command or relax guards to obtain
an outcome.

## Derive a private comparison

Point the candidate variables at the sealed `campaign/` subdirectories of the
corresponding pilot outputs. Reports are derived without additional inference:

```bash
python3 scripts/report-chat-intent-v2.py \
  --pack-root "$PRIVATE_PACK" --baseline "$PRIVATE_BASELINE" \
  --candidate "mini-q8-metal=$MINI_CAMPAIGN" \
  --candidate "flash-q8-metal=$FLASH_CAMPAIGN" \
  --output "$BENCH_ROOT/results/intent-replay-comparison"
```

An optional Q4 archive can be supplied with another `--candidate LABEL=ARCHIVE`.
Keep `report.json` and `report.md` private. They retain test/calibration/all
metrics, per-label confusion, missing/error/timeout/unsupported/abstention
coverage, paired corrections and regressions, and evidence hashes. The reporter
requires exact frozen cases for every candidate case; source metadata remains
outside model input.

This is a descriptive comparison of historical recorded labels with isolated
model choices. The stock `compare` command rejects recorded harness controls;
the derived reporter preserves those qualification and protocol distinctions.
Its gates do not establish promotion, downstream answer quality, message-language
qualification, CUDA execution or production latency. Preserve raw archives and
runtime evidence alongside the report in the private handoff.
