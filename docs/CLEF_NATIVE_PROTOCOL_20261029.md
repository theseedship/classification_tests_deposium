# Clef candidates: native text-choice protocol

**29 October 2026 — separate addition requested after the physics baseline.**
This protocol adds two candidate configurations without changing the frozen
[seven-candidate capability cohort](CAPABILITY_CAMPAIGN_PLAN.md). References
and translations remain agent-authored and pending human review. No published
provider evaluation is substituted for a result on these datasets.

## Candidate identities and execution scope

| Requested source | Prepared native configuration | Initial qualification |
|---|---|---|
| [ggml-org/Clef-GGUF](https://huggingface.co/ggml-org/Clef-GGUF/blob/d7492270abd7af222e98dca986580772e6229242/README.md) | Clef 27B class, Q4_K_M, revision `d7492270abd7af222e98dca986580772e6229242` | Manifest pinned; requires 32 GiB available before hashing/loading; not run |
| [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash/blob/f0b7d3cd65296abfe459e6c228b618f5d8b26d2f/README.md) | [ggml-org/Clef-Flash-GGUF Q8_0](https://huggingface.co/ggml-org/Clef-Flash-GGUF/blob/6e2a164d70aae2af7fce86005da3f91805565b1d/README.md), revision `6e2a164d70aae2af7fce86005da3f91805565b1d` | Prepared local route; not yet a model result |

These are distinct nominal 27B and 9B variants. The Flash conversion's card
links to Cloudflare/clef-flash. That link does not attest which exact upstream
weight revision was converted. The separately observed Cloudflare revision is
recorded for source review; it is not an asserted conversion-source identity.
Q8 native results do not qualify the publisher's BF16/PyTorch or CUDA path.

The [Flash Q8](../profiles/clef-flash-q8-assets.json) and
[27B Q4](../profiles/clef-27b-q4-assets.json) manifests retain exact filenames,
sizes and publisher LFS SHA-256 values. Verify the downloaded bytes before use.
No vision projector, images, video, free generation, `noul`, `score`, multi-question
batch or application integration is evaluated by the text-choice campaign.

## Native path and input audit

Use the existing upstream llama.cpp source at
`efe3626b119ff81033e309c3ba07a770bef2c546` and its separately fingerprinted
Metal binary. The source includes the Clef decision type and joint task path.
The shared `systemone_local` adapter still exposes only context, question and
ordered option descriptions, remapped to neutral `c0`… keys. No IDs, split,
reference explanation, annotation or expected answer enters a native request.

Clef's preparation is joint: the vocabulary-only helper must explicitly select
`--decision-type clef` and call the real native `fill_task_joint`, including its
option order and head layout. It must reject a D3 model declared as Clef.
Preserve token IDs/hashes, decision-order IDs/hashes, score count and exact
request-body hashes privately. The helper supports three/four-choice requests;
the three frozen full packs here all have four choices. Three-choice preparation
alone is not evidence that three-choice inference was evaluated.

Prepare all **372 distinct dataset inputs** (132 context + 192 capability +
48 physics), a separate three-choice synthetic preparation control and a
synthetic overflow control. Bound the helper to 2 GiB sampled group RSS,
8 GiB host reserve and 600 seconds, with no inference context, tensors or
forward. Require complete inputs within 4096; never silently truncate a catalogue.
The [current publisher Python helper](https://huggingface.co/Cloudflare/clef-flash/blob/f0b7d3cd65296abfe459e6c228b618f5d8b26d2f/joint_schema_model.py)
can clip state tokens after reserving the schema. This campaign instead audits
the real native preparation and refuses an over-budget complete input.

## Frozen Flash Q8 phases

| Phase | Dataset calls | Session time ceiling | Quality interpretation |
|---|---:|---:|---|
| Capability calibration canary | 12 | 600 s | Same exact three calibration families as the existing sequence; valid format/identity only, no accuracy gate |
| Fresh context anchor | 132 | 1,200 s | Full/132 and test/66 separately |
| Capability choices | 192 | 1,200 s | Full/192 and test/96; track, language and catalogue groups |
| Physics choices | 48 | 600 s | Full/48 and test/36; language, task and authored difficulty groups |

The [machine-readable addition](../plans/clef-native-v1.json) pins the cases,
hashes, exact canary IDs, candidate configurations and phase order. There are
384 planned dataset calls including the separate canary. They never become a
single accuracy denominator. Four prepared-input warm-ups and auth/overflow
controls are additional, excluded technical calls.

Use `scripts/run-upstream-native-pilot.py --decision-type clef`, the selected
asset manifest, a native preparation receipt and one new output per phase.
Fresh owned sessions use context/batch/microbatch 4096, one slot/request/question,
30-second calls, no retries, no model/backend fallback and no context shifting
or automatic fitting. Flash uses **18 GiB group RSS + 8 GiB reserve**; admit
at **26 GiB** before model hashing and require actual full-layer Metal offload.
The watcher samples at 250 ms. Do not alter an envelope in response to test results.

The 27B configuration has a separate **24 GiB RSS + 8 GiB reserve** admission
envelope. Do not download/load it when that admission fails, lower a guard to
fit it, reorder the original cohort, or treat a preflight as a model failure.
Its executable phases require a candidate-specific supervised envelope; the
current Flash-specific launcher deliberately refuses a different RSS limit.

## Evidence and reporting

Freeze exact benchmark/helper/runtime bytes before any dataset prediction.
Keep previous D3 physics/capability source snapshots, binaries, outputs and
seals unchanged; this helper extension is a new source observation. The bound
adapter rejects unprepared wire bytes before HTTP and live token-count mismatch
after response. Missing native truncation and physical-forward receipts remain
unknown. Preparation/count agreement does not compare live token IDs or head order.

Report every status, coverage and denominator, with family-correlated language
and catalogue variants. A valid wrong choice does not fail the canary. Never
change a reference or stop a full admitted campaign based on accuracy. Keep
raw outputs, logs, local paths and source captures in ignored archives; only
reviewed synthetic aggregate evidence is eligible for public results.
