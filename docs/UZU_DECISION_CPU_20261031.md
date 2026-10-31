# Uzu d3-flash: CPU-tested transport and controller

31 October 2026. This contribution connects a separate
`uzu_systemone_local` candidate to the existing campaign engine, System One
request projection, response validator and scorer. It includes a controller
tested with synthetic files, mocked processes and HTTP. **Zero Uzu model cases
have run.** There is no model score, measured speed, RAM saving, Metal
qualification or product integration to add to the results table.

The three initial packs remain unchanged: context (132), capability (192) and
physics (48), with their existing splits and authored reference limitations.
The original seven-candidate cohort and historical archives are unchanged.
Existing llama.cpp profiles retain their namespace, authentication and behavior.

## Pinned source and pack

- [Uzu](https://github.com/trymirai/uzu/tree/023bf5d94c719d15734e7b77b2e44b4452b2819f):
  `023bf5d94c719d15734e7b77b2e44b4452b2819f`.
- [Mirai-M pack](https://huggingface.co/trymirai/d3-flash-M/tree/86f617b67e3f0ce02fe678c38801e2296a303777):
  `86f617b67e3f0ce02fe678c38801e2296a303777`, text decisions only.
- The source exposes decision sessions and `/v1/systemone`; use its
  [decision example](https://github.com/trymirai/uzu/blob/023bf5d94c719d15734e7b77b2e44b4452b2819f/crates/legacy/uzu/bindings/python/examples/decision.py),
  rather than the catalogue's generic chat snippet. No conversion is needed.

The multi-file asset manifest uses `deposium.model-assets/v1` with exactly
`schema_version`, `repo_id`, `revision` and `files`. Each file has exactly
`path`, positive integer `size` and SHA-256. Stage only these runtime inputs
in a fresh directory: `model.safetensors`, `config.json`, `chat_template.jinja`,
`tokenizer.json`, `tokenizer_config.json`, `LICENSE`. Missing, extra, duplicate,
escaped, symlinked or altered inputs are rejected. In particular, an untracked
`encoding.json` cannot silently change a local pack's rendering.

The configuration must declare `DecisionModelConfig`, 255 distinct ordered codes,
temperature 1 and the same embedded/standalone template. Actual tensor loading
and numerical conformance remain native prerequisites. Expected file hashes and
source pins are provenance declarations, not signatures or build attestations.

## Transport and supervision

`UzuSystemOneAdapter` subclasses the common System One client. The common client
has small hooks for profile/session binding, authentication policy and overflow
classification; HTTP framing, input projection, response validation and scoring
are not reimplemented. The existing authenticated adapter remains unchanged
in scope. Uzu's `credential_env` is null: this local source does not establish
authentication, so no application/provider secret is sent or inherited.

The candidate retains the ordinary `deposium.candidate/v1` envelope and its
model fields: loopback `/v1/systemone` endpoint, exact served model ID, pack
repository, session manifest/hash, input limit, RSS budget and null credential
environment. Its qualification is `model_isolated`, its capability is only
`bench.context-choice`, and its revision is the pack revision above.

The private `deposium.uzu-model-session/v1` binds:

- `model`: repository/revision/alias, local pack directory, asset-manifest path/hash;
- `runtime`: Uzu repository/revision and binary path/hash;
- `preparation`: preparation receipt path/hash;
- endpoint, PID and supervisor PID;
- `settings`: `client_max_tokens`, concurrency 1, one question per call,
  `implicit_acquisition:false`; and `max_rss_mb`.

The matching live `native_supervision` scope is required before construction
can hash the resident pack, and before/after each request. A saved profile,
live PID or successful HTTP response alone is insufficient. Pack inventory and
file metadata changes, guard loss and response-token disagreement reject the
result. Response probabilities and original error/timeout statuses are retained.
Uzu's explicit context-overflow error has its own recognizer; llama.cpp error
patterns are not reused. Absence of a truncation flag remains unknown.

## Input preparation is still a native prerequisite

The controller **consumes** a `deposium.uzu-input-preparation/v1` receipt.
This contribution does not implement or qualify the actual Uzu-renderer
producer. Do not hand-author counts from estimates or reuse the llama.cpp
vocabulary helper's counts. The producer must use the pinned
`hanashi::decision::DecisionEncoding` with the staged pack tokenizer/template.

The closed receipt contains `schema_version`, `uzu_revision`, `model_id`,
`assets_sha256`, integer `max_tokens`, the renderer name, `weights_loaded:false`,
`forward_executed:false`, `request_tokens` and `overflow_control`.
`request_tokens` maps exact UTF-8 wire-body SHA-256 to
`{input_tokens, token_ids_sha256}`. Counts are positive integers within the
client limit. The overflow control contains its different
`request_body_sha256`, count above that limit and token-ID digest; it is not
a fabricated server-overflow receipt. Missing/unknown data cannot become zero.
The controller requires exactly the distinct wire inputs of the selected pack.

This receipt binds preparation, not live token-ID equivalence or physical
forward counts. Both remain unknown in candidate provenance. A comparison with
an independently rendered reference must qualify that boundary before stronger
claims. The input limit is a client policy, not a claimed Uzu `n_ctx` setting.

## Explicit future execution

`scripts/run-uzu-pilot.py --help` describes the invocation without starting
anything. Execution requires `--execute` and explicit paths to the local pack,
asset manifest, binary, runtime manifest, native preparation receipt, unchanged
dataset and new private output directory, plus the exact served model ID.
The runtime manifest has Uzu repository/revision and `binary_sha256`.

The proposed first envelope is Mac ARM64 only, 4096 prepared input tokens,
one request/question at a time, 30 s per call, 14336 MiB group RSS and 8192 MiB host
reserve, at most 1200 s including controller preparation and cleanup. These are
controller bounds, not measured RAM requirements or an approved campaign plan.
Initial admission precedes hashing weights; the reserve is rechecked afterward.
An expired prelaunch deadline cannot start the service.

The command uses the pinned local directory, IPv4 loopback and no prefix cache.
Because the stock CLI includes a downloader, macOS `sandbox-exec` requests
loopback-only network egress; this policy itself still needs a bounded real Mac
check before a model campaign. Child environment excludes inherited provider
credentials. Readiness verifies the served ID. Resource supervision and campaign
execution reuse the existing code. The selected dataset is copied unchanged.

Exact preparation/asset/runtime metadata originals are retained beside the
unchanged dataset. The campaign uses the ordinary archive seal; after closure,
`pilot-seal.json` fingerprints the evidence bundle, excluding mutable private
runtime cache files. No weights are copied into an archive.

The controller keeps technical collection coverage separate from quality.
Incorrect predictions can complete a campaign without passing its score.
Parent exit does not establish descendant cleanup: an extant process group,
cleanup exception or late closure prevents global completion and retains an
explicit unknown/error receipt. An unverified group is never signalled as owned.
HTTP timeout does not assert that native compute stopped. No automatic rerun.

## Validation and next step

Run the new no-model fixtures with Python 3.11+:

```bash
python3 -B -m unittest discover -s tests -p 'test_uzu*.py' -v
```

They exercise synthetic multi-file identities, preparation bindings, mapping,
invalid probabilities, timeout/no retry, guard loss, resource preflight,
readiness failures, cleanup uncertainty/deadlines and a sealed campaign through
the actual shared scorer. Every Uzu process and socket is mocked.
They do not certify Uzu compilation, the native preparation producer, the
macOS network policy, actual Metal use or model quality.

Next: review the CPU contribution, prepare/verify the real renderer producer
and runtime build without modifying historical receipts, then freeze a separate
native plan. Coordinate its bounded window with other local benchmarks before
any launch. Use a calibration canary, then separate context/capability/physics
archives and the normal result generator; passage evidence remains a later step.
Mirai-M/Uzu versus GGUF/llama.cpp compares two deployments and cannot isolate
the causal effect of quantization, Uzu or Memfit.

Local validation on macOS/Python 3.12.16: 143 targeted adapter/controller,
campaign, supervision, schema and regression checks, 129 passed and 14 optional
skips, including 32 new no-model Uzu checks. Ruff F/E9, result-view generation
check and staged-public-content checks also pass. This is targeted validation.
The existing GLiNER temporary-path assertion also fails on the unchanged public
base when macOS returns the `/var` alias; using canonical `TMPDIR=/private/tmp`
avoids that alias in the targeted run. No test or reference was weakened.
Optional skipped validators are not successful qualifications; no full-suite
Linux or native qualification is claimed by this contribution.
