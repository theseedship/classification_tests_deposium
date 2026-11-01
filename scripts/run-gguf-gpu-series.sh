#!/usr/bin/env bash
# Run the D3 GGUF packs for one model on one GPU backend, one phase at a time.
#
#   scripts/run-gguf-gpu-series.sh BACKEND MODEL [PACK ...]
#
# BACKEND  cuda | rocm | vulkan | metal
# MODEL    lite-q8 | nano-q8 | mini-q8 | mini-q4 | flash-q4
# PACK     facade facade-advanced facade-complex context capability physics prv2 hitl9 hitl8 passages
#          (default: all, in that order)
#
# Environment (all paths under this checkout's ignored results/):
#   LLAMA_SOURCE   clean llama.cpp checkout at the pinned revision
#   LLAMA_RUNTIME  directory with build/bin/llama-server and runtime-manifest.json
#   PREFLIGHT      helper built by scripts/build-systemone-preflight.py
#   MODELS         directory with the GGUF files fetched by scripts/fetch-gguf.py (default results/models)
#   OUT            output directory (default results/gpu-<backend>-runs)
#
# A phase already completed in OUT with the same llama-server binary is skipped; any other phase gets the next
# attempt number. The script exits 1 when any requested phase did not complete.
# When nvidia-smi exists, used GPU memory is sampled every 500 ms to <archive>.vram.csv
# (beside the sealed archive, never inside it) and its peak is printed.
set -u
cd "$(dirname "$0")/.."
BACKEND=${1:?backend}; MODEL=${2:?model}; shift 2
PACKS=("$@"); [ ${#PACKS[@]} -eq 0 ] && PACKS=(facade facade-advanced facade-complex context capability physics prv2 hitl9 hitl8 passages)
: "${LLAMA_SOURCE:?}" "${LLAMA_RUNTIME:?}" "${PREFLIGHT:?}"
MODELS=${MODELS:-results/models}; OUT=${OUT:-results/gpu-$BACKEND-runs}; mkdir -p "$OUT"
case $MODEL in
  lite-q8|nano-q8|mini-q8|mini-q4) ASSETS=profiles/d3-$MODEL-assets.json; ENVELOPE=small-gguf-8g-v1; RSS=8192;;
  flash-q4) ASSETS=profiles/d3-flash-q4-assets.json; ENVELOPE=d3-flash-q4-12g-v1; RSS=12288;;
  *) echo "unknown model $MODEL" >&2; exit 2;;
esac
FILE=$(python3.12 -c "import json,sys;print(json.load(open(sys.argv[1]))['files'][0]['path'])" "$ASSETS")
GGUF=$MODELS/$FILE; ID=d3-$MODEL
[ -f "$GGUF" ] || { echo "missing $GGUF; run scripts/fetch-gguf.py --assets $ASSETS --output-dir $MODELS" >&2; exit 2; }
pack_of() {
  case $1 in
    facade) echo "facade-routing-v1 choices";; facade-advanced) echo "facade-routing-advanced-v1 choices";;
    facade-complex) echo "facade-routing-complex-v1 choices";; context) echo "context-choice-v1 choices";;
    capability) echo "capability-choice-v1 choices";; physics) echo "physics-choice-v1 choices";;
    prv2) echo "passage-relevance-v2 choices";; hitl9) echo "facade-routing-hitl-v1 choices";;
    hitl8) echo "facade-routing-hitl-8opt-v1 choices";; passages) echo "passage-evidence-v1 passages";;
    *) return 1;;
  esac
}
RUNTIME_SHA=$(python3.12 -c "import json,sys;print(json.load(open(sys.argv[1]))['binary_sha256'])" "$LLAMA_RUNTIME/runtime-manifest.json") || exit 2
# A completed archive counts only when it ran the requested binary (a rebuild is a new runtime identity).
completed_here() {
  python3.12 -c "import json,sys;p=json.load(open(sys.argv[1]));sys.exit(0 if p.get('completed') is True and p['runtime']['binary_sha256']==sys.argv[2] else 1)" \
    "$1/pilot.json" "$RUNTIME_SHA" 2>/dev/null
}
failed=0
free_port() { python3.12 -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1])"; }
for TAG in "${PACKS[@]}"; do
  read -r PACK TASK < <(pack_of "$TAG") || { echo "unknown pack $TAG" >&2; exit 2; }
  n=1; done_already=0
  while [ -d "$OUT/$ID-$BACKEND-$TAG-$(printf %03d $n)" ]; do
    completed_here "$OUT/$ID-$BACKEND-$TAG-$(printf %03d $n)" && done_already=1
    n=$((n + 1))
  done
  [ $done_already = 1 ] && { echo "skip $ID $TAG (completed with this binary)"; continue; }
  ARCHIVE=$OUT/$ID-$BACKEND-$TAG-$(printf %03d $n); PREP=$OUT/prep-$ID-$TAG
  if [ ! -f "$PREP/summary.json" ]; then
    rm -rf "$PREP"
    python3.12 scripts/prepare-native-inputs.py --helper "$PREFLIGHT" --model "$GGUF" --assets-manifest "$ASSETS" \
      --model-id "$ID" --dataset "datasets/$PACK/cases.jsonl" --task "$TASK" --output "$PREP" || { echo "preparation failed: $TAG" >&2; failed=1; continue; }
  fi
  SAMPLER=""
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$ARCHIVE.vram.csv" & SAMPLER=$!
  fi
  python3.12 scripts/run-upstream-native-pilot.py --source-root "$LLAMA_SOURCE" --binary "$LLAMA_RUNTIME/build/bin/llama-server" \
    --runtime-manifest "$LLAMA_RUNTIME/runtime-manifest.json" --model "$GGUF" --assets-manifest "$ASSETS" \
    --preparation "$PREP/native-preparation.jsonl" --dataset "datasets/$PACK/cases.jsonl" --task "$TASK" --model-id "$ID" \
    --backend "$BACKEND" --execution-envelope "$ENVELOPE" --max-rss-mb "$RSS" --max-seconds 1200 --port "$(free_port)" \
    --output "$ARCHIVE" > "$ARCHIVE.log" 2>&1
  [ -n "$SAMPLER" ] && kill "$SAMPLER" 2>/dev/null
  completed_here "$ARCHIVE" || failed=1
  status=$(grep -o '"completed": [a-z]*' "$ARCHIVE/pilot.json" 2>/dev/null | head -1)
  peak=$( [ -s "$ARCHIVE.vram.csv" ] && sort -n "$ARCHIVE.vram.csv" | tail -1 )
  echo "$(date +%T) $ID $TAG ${status:-no archive, see $ARCHIVE.log}${peak:+ · peak GPU memory ${peak} MiB}"
done
exit $failed
