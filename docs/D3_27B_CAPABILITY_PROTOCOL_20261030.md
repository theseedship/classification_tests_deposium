# Historical D3 27B Q4: deferred capability campaign

**30 October 2026: `deferred_by_maintainer`; inference `not_run`, zero cases
scored.** Actual execution remains deferred. Offline code,
protocol and mocked tests establish preparation only. They do not establish
model loading, a completed canary, Metal execution or a model score.

This is candidate two in the unchanged
[capability sequence](../plans/capability-choice-v1-sequence.json). Its
[separate readiness plan](../plans/d3-27b-capability-v1.json) does not alter the
original cohort, datasets, references or completed Flash/Clef observations.
The historical 27B is neither Flash nor Ultra/Turbo. Comparing it with Flash
changes checkpoint, size and quantization together.

## Fixed identity and resource envelope

Use only `ggml-org/vllm-d3-GGUF` at
`de9670136f5ddd83e677c89ce041d5b9bb3b0dcb`, file
`vllm-d3-Q4_K_M.gguf`, 19,403,686,112 bytes, SHA-256
`a5a341e8611dc5d916c8f4c693dbef4a68e57eb17d37914fd56dcb5a9221eb2d`.
The [existing asset manifest](../profiles/d3-27b-q4-assets.json) remains intact.
Alias: `d3-27b-q4-v1`; decision type: `d3`; task: `choices` only.

The real direct upstream llama.cpp listener must be clean at
`efe3626b119ff81033e309c3ba07a770bef2c546`. Verify actual binary, native source,
helper source/build and benchmark fingerprints for this observation. A build
or token count from Flash does not qualify 27B. No application gateway,
database, product router or deployed configuration is required or modified.

The explicit `--execution-envelope d3-27b-q4-24g-v1` requires context, batch
and microbatch 4096; one slot, request and question at a time; 30-second calls;
24,576 MiB sampled owned-process-group RSS; and an 8,192 MiB host reserve.
Admission requires **32,768 MiB estimated available before reading/hashing
model bytes**. Preserve the reserve after verification and during execution.
The 250 ms watcher stops only its owned group. RSS is sampled, not an
instantaneous or total unified-memory cap; macOS available memory is an
estimate from reclaimable page categories.

The default `flash-clef-18g-v1` behavior stays at 18,432 MiB RSS and a maximum
1,200-second phase. It refuses the historical 27B identity. Selecting a larger
RSS limit alone cannot opt into the 27B envelope or raise a Flash/Clef limit.
No guard is weakened because admission or an experiment fails.

## Complete native preparation before the canary

Keep the exact public context pack, SHA-256
`767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616`
(132 cases), and capability pack, SHA-256
`0b409a09bb5358b5c8d7574cbd330799511851a2acd90676e2f092f3d3c75eb0`
(192 cases). Use the shared `native_request` projection with the fixed alias.
Only context, question and ordered descriptions enter native request bytes.
Do not expose references, splits, family IDs or semantic case identifiers.

The actual vocabulary-only helper must prepare **all 324 source inputs**, plus
exactly one separate `synthetic-native-overflow` input. Its body is the shared
runner's `overflow_input(4096)` projection. Preserve exact body and token-ID
hashes. Every ordinary variant must fit 4096; the overflow must be unsupported.
Missing, extra or mismatched rows prevent launch, even for a twelve-case canary.
No weights, inference context, decode or forward are loaded by this helper.
Run its owned process under **2,048 MiB RSS / 8,192 MiB reserve / 600 seconds**.

`--preparation-receipt` is mandatory for this envelope. It is generated from
the actual bounded preparation, not from unit-test fixtures. Its closed JSON
shape is:

```json
{
  "schema_version": "deposium.d3-27b-native-preparation/v1",
  "execution_envelope": "d3-27b-q4-24g-v1",
  "model_id": "d3-27b-q4-v1",
  "model_assets": "THE EXACT OBJECT FROM profiles/d3-27b-q4-assets.json",
  "native_revision": "efe3626b119ff81033e309c3ba07a770bef2c546",
  "helper": {
    "source_sha256": "CURRENT PUBLIC HELPER SOURCE HASH",
    "binary_sha256": "ACTUAL HELPER BINARY HASH",
    "build_manifest_sha256": "ACTUAL BUILD MANIFEST HASH"
  },
  "audit_sha256": "ACTUAL 325-ROW PREPARATION FILE HASH",
  "case_count": 324,
  "overflow_controls": 1,
  "resources": {
    "rss_limit_mib": 2048,
    "reserve_mib": 8192,
    "max_seconds": 600,
    "rss_peak_mib": "MEASURED POSITIVE NUMBER AT MOST 2048",
    "min_available_mib": "MEASURED NUMBER AT LEAST 8192",
    "elapsed_seconds": "MEASURED POSITIVE NUMBER AT MOST 600",
    "stop_reason": null,
    "completed": true
  }
}
```

The explanatory strings above are placeholders, not a runnable receipt.
Retain actual helper/build sources, dependency identities, invocation, model
verification, resource samples, audit and receipt privately. The supervisor
checks the receipt's declared identity, hashes, coverage and resource bounds;
this consistency check is not an independent attestation of its author.

## Canary first; measured budgets before full phases

The canary is exactly the twelve calibration IDs from the original sequence:
`ccv1-{selection,arguments,observations}-02-{compact,expanded}-{fr,en}`, in that
order. Its whole supervised session has a fixed **600-second** ceiling.
Require twelve structurally valid decisions and actual HTTP attempts with the
correct model, Metal offload, request hashes and preparation counts. There is
**no accuracy threshold**: valid wrong choices remain valid technical results.
Do not tune prompts, references, selection or budgets from test outcomes.

After a genuine completed canary, freeze full-phase time budgets with the pure
`derive_phase_budgets` function in the existing supervisor:

`ceil(180 + 2 × phase_case_count × max_canary_adapter_ms / 1000)`.

Use all twelve positive adapter durations, including wrong decisions. The
180-second term is a declared startup allowance; the factor two is a fixed
calibration margin. The resulting whole-session budgets must be at most
**1,200 seconds for the 132-case anchor** and **1,800 seconds for the 192-case
capability pack**. Refuse a derivation above either ceiling; do not clamp or
increase the ceiling to obtain a completed score. These are experimental
admission rules, not predicted production latency or physical-forward timing.

Both full phases require `--calibration-receipt`, with this closed shape:

```json
{
  "schema_version": "deposium.d3-27b-calibration/v1",
  "execution_envelope": "d3-27b-q4-24g-v1",
  "model_id": "d3-27b-q4-v1",
  "model_sha256": "PINNED 27B MODEL HASH",
  "preparation_receipt_sha256": "EXACT PREPARATION RECEIPT HASH",
  "canary_archive": "ABSOLUTE LOCAL CANARY DIRECTORY; NEVER PUBLISH",
  "canary_seal_sha256": "ACTUAL OUTER CANARY SEAL HASH",
  "derivation": {
    "rule": "ceil_180_plus_2n_times_max_canary_adapter_seconds/v1",
    "max_canary_adapter_ms": "ACTUAL MAXIMUM OF ALL TWELVE DURATIONS",
    "phase_max_seconds": {
      "anchor": "DERIVED INTEGER AT MOST 1200",
      "capability": "DERIVED INTEGER AT MOST 1800"
    }
  }
}
```

The supervisor verifies the exact outer inventory/seal and inner campaign
seal, frozen twelve calibration inputs, all twelve successful actual HTTP
attempts and preparation matches, same model/runtime/helper-preparation
identity, full Metal offload, and the numeric derivation. It reads retained
files only and never restarts the saved session. `--max-seconds` must equal
the frozen derived value for the requested full phase. No genuine canary or
calibration receipt exists merely because these offline checks pass.

The retained native answer is revalidated through the same pure response
validator used by the live transport: model, choice/probabilities, token usage
and option mapping must produce the recorded choice. Cached failures and
explicit truncation are refused; absent truncation evidence stays unknown.
The sealed inner summary must be complete and match the shared scorer's
results, while wrong but structurally valid choices remain eligible for timing.

## Launch and reporting after the deferral ends

Use a fresh clean clone of public source. Keep models/runtime inputs read-only
at their actual local locations; keep generated files in a new ignored
`results/` study. Preserve every failed attempt. For the canary only, after all
prerequisites and fresh admission succeed:

```bash
python3 scripts/run-upstream-native-pilot.py \
  --source-root "$NATIVE_SOURCE" --binary "$NATIVE_BINARY" \
  --runtime-manifest "$NATIVE_MANIFEST" --model "$MODEL_FILE" \
  --assets-manifest profiles/d3-27b-q4-assets.json \
  --preparation "$STUDY/native-prepared.jsonl" \
  --preparation-receipt "$STUDY/preparation-receipt.json" \
  --dataset "$STUDY/canary.jsonl" --model-id d3-27b-q4-v1 \
  --decision-type d3 --task choices \
  --execution-envelope d3-27b-q4-24g-v1 --phase canary \
  --context 4096 --max-rss-mb 24576 --min-free-mb 8192 \
  --max-seconds 600 --output "$STUDY/canary-001"
```

For each full phase use its unchanged complete source pack, a fresh session
and output, the same preparation receipt, the verified calibration receipt,
and its exact derived budget. Keep anchor 132/test66 and capability192/test96
separate. Canary repeats, warm-ups and guard calls are excluded from quality
denominators. Never pool the packs or treat the larger model as ground truth.

Preserve missing, unsupported, error, timeout and abstain statuses, partial
collections and resource refusal. Require live request-body/prepared-count
agreement; missing native truncation and physical-forward receipts remain
unknown. Publish reviewed aggregates and safe pins only. Paths, source
snapshots, raw outputs, PIDs, keys and logs remain ignored. This preparation
does not qualify tool execution, a product workflow or a complete RAG journey.
