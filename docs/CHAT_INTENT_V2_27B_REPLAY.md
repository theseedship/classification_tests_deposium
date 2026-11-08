# Optional 27B replay of a frozen private intent pack

This is a separate extension of [the private replay protocol](CHAT_INTENT_V2_REPLAY.md).
It uses the shared upstream launcher, native preparation, adapter and scorer.
No private data, case identities, results or model weights are distributed here.
Offline tests qualify the admission code, not model execution or answer quality.

## Fixed candidate and budgets

The candidate, alias and runtime are the exact historical D3 27B Q4 from the
[27B protocol](D3_27B_CAPABILITY_PROTOCOL_20261030.md). Existing context/capability
phases and their receipts remain unchanged. This extension has its own explicit
envelope, `d3-27b-intent-q4-24g-v1`, and phases `canary` and `intent`.

- Metal must offload all layers. Context and batches stay at 4096, one slot,
  one call at a time, 30-second calls, no retry or backend fallback.
- Admission: 32 GiB estimated available; sampled owned-group RSS at most
  24 GiB, with 8 GiB host reserve. Sampling is not a hard instantaneous GPU
  allocation cap. Do not raise limits or stop unrelated workloads for a score.
- The technical canary has 12 calls plus its excluded calibration warm-up
  and guard controls, at most 600 seconds. Wrong valid answers are retained;
  there is no canary accuracy gate.
- The full phase budget is frozen from all 12 canary adapter durations:
  `ceil(180 + 2 * full_pack_case_count * max_canary_ms / 1000)`.
  Refuse a derived budget above 1800 seconds; do not clamp or extend it.

## Pin the pack before preparation

The dataset owner supplies the private pack and a trusted SHA-256 of its
`manifest.json`. Supply both explicitly as `--intent-pack-root` and
`--intent-pack-manifest-sha256`. Computing a hash of unknown received data does
not independently authenticate its annotations. Freeze the selected pin before
predictions and keep it with the retained study.

The launcher reuses the report's pack verifier, then the shared case/oracle
validators. It requires the frozen intent cards and preview-only projection.
It derives the canary as the **first twelve calibration cases in frozen file
order**, without inspecting predictions, labels or reference difficulty.
The first case of the full pack must be calibration, so the technical warm-up
never uses a held-out input. Keep references, cards, inputs and split groups
unchanged. Do not tune on previously observed test results.

Use an ignored `results/` directory for a new study. Materialize the canary
with the shared `campaigns._encode` serializer and the selection above; do not
hand-select examples. Prepare **the entire frozen pack**, not only the canary,
using `scripts/prepare-native-inputs.py`, the actual 27B model and the pinned
native helper. Preparation must cover every input and the separate overflow
control, within 2 GiB RSS / 8 GiB reserve / 600 seconds.

## Receipts and execution

The envelope returned by `execution_envelope` contains a `study_binding`:
manifest, dataset and cards hashes; full case count; fixed canary rule; and
SHA-256 of the serialized canary. It contains no candidate input or gold label.
All receipts and generated archives remain private and ignored by Git.

Use the existing preparation receipt fields from the 27B protocol, with:

- schema `deposium.d3-27b-native-preparation/v2`;
- this explicit intent envelope;
- `case_count` equal to the complete frozen pack's count;
- the exact `study_binding` and actual helper/audit/resource observations.

Resource observations must come from the actual supervised preparation, not
test fixtures or configured limits. Archive the helper build manifest and raw
resource samples. Retain every failed attempt; never overwrite an archive.

Run the shared launcher with all normal required model/runtime/preparation
arguments, plus the pack pin, this envelope and `--phase canary
--max-rss-mb 24576 --min-free-mb 8192 --max-seconds 600`.
The canary file must exactly match the derived cases. Its preparation receipt
is mandatory; a calibration receipt is forbidden at this stage.

Only after a completed, sealed canary, create a calibration receipt using the
existing receipt fields, with schema `deposium.d3-27b-calibration/v2`, the intent
envelope, the same `study_binding` and the derivation above. The launcher checks
actual HTTP attempts, model/runtime/helper bindings, preparation counts, native
response validity, resource bounds, all-layer offload and complete summaries.
This is consistency verification of retained evidence, not an independent
attestation of its producer. No model or service is launched by verification.

For the full phase, pass the **byte-identical frozen cases.jsonl**,
`--phase intent`, both receipts, and `--max-seconds` equal to the derived
budget. A legacy preparation/calibration receipt, changed pack, partial or
reordered canary, missing call or rewritten time budget is refused.

Preserve the complete inner campaign, outer native seal, preparation and
calibration receipts, logs, raw calls, source identities and resource samples.
Use `scripts/report-chat-intent-v2.py` to compare the sealed full campaign with
the owner's baseline and other candidates. Keep calibration/test metrics,
all failure denominators, per-label changes, memory and latency separate.
The result is an isolated classification observation, never product promotion,
execution of tools, or a test of conversational generation.
