# Indecis worker, open mode without training

Pinned library: `339e191405ac9be90f6857f810f478b3312b7f35` (MIT), in the
ignored `.cache/indecis-source` checkout. The bridge directly imports its Go
module through a local replacement; it never downloads modules or model assets.

Clean reproduction requires explicit provisioning first, outside tests:

- Extract the official [Go 1.27.1 Linux amd64 archive](https://go.dev/dl/go1.27.1.linux-amd64.tar.gz)
  under `.cache/go1.27.1/`, after checking SHA-256
  `63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`.
- Clone [the upstream repository](https://github.com/Bornholm/indecis) into
  `.cache/indecis-source` and check out the detached pinned commit above.
  The helper rejects another revision or a dirty checkout.
- For a later, explicitly invoked campaign, provision the three Bekko files
  from revision `c721113d59a1d91b447450324f51c4b3332c924a` and check them against
  [the assets manifest](../../profiles/indecis-assets.json). The build/tests do
  not require them. See [the frozen pilot](../../docs/INDECIS_PILOT.md) for
  resource limits and campaign steps.

With the explicitly provisioned Go 1.27.1 toolchain:

```sh
python3 runtimes/indecis/build_worker.py --test
```

This runs fake-engine bridge tests, builds the resident executable under
`.cache/indecis-runtime/`, and records source/build manifests here. It does not
open weights, load a backbone, or perform inference. Source changes require a
new build and manifests before any new campaign. Historical archives remain
unchanged. Build inspection verifies the binary's Go version and embedded
CGO/architecture/SIMD settings, with network-disabled module resolution.
`GOFLAGS`, `GOWORK` and `GOENV` overrides are disabled. Go's experimental build
identifies itself as `go1.27.1-X:simd`; that exact binary version is recorded.

JSONL input is bounded to 1 MiB per line. First send `initialize` with exactly
`config={local_dir,prompt,revision,source_revision,max_length,threads}`. The
prompt is the frozen `deposium.indecis-choice-prompt/v1`; the revisions are the
pinned Bekko and Indecis commits. A ready response includes the Go runtime,
both revisions, its executable SHA-256, `load_ms` and process peak `rss_mb`.
Subsequent requests contain exactly `{op:"predict",sequence,input}` with the
shared context/question/options contract. Responses add the sequence to the
standard status/output/error/raw_output envelope. EOF closes the worker.

The official `DecideOpen` receives the context and options whose **names are
descriptions**, with the question in `Instructions`. Upstream therefore encodes
each option as `description + "\n" + question`. IDs stay in transport/remapping.
No trained model, head decision, option examples, int8, pair mode, or embedding
cache is enabled. Encoder computation uses the upstream FP32 path; source BF16
weights are loaded by its official loader. A candidate set lives for one call.

Before inference, the shared upstream tokenizer encodes every complete
sequence. Above `max_length`, the worker returns `unsupported` with
`indecis_context_overflow` or `indecis_option_overflow` and no forward. Otherwise it compares complete IDs
with the model's `TokenIDs` and then calls `DecideOpen`. This pinned unpaired
path uses the same `EncodeMax` operation for embeddings. No truncation or
chunking is accepted. `encoding_info.tokens` is the **maximum separate sequence
length**; `token_components.total_tokens` sums context and option sequences.
These are ragged sequences, not one joint window or an invented padded length.

`inference_ms` measures the official call, including its tokenization, option
encoding, cosine comparison and softmax. `decision_ms` also includes admission
and normalization. The native Answer retains its description-keyed distribution,
chosen description, confidence and optional cosine `score`/probability `margin`.
It is not a calibrated truth probability. On an indeterminate native failure,
raw audit is null rather than claiming that a forward did or did not occur.

Limits: Linux worker, parent-enforced process timeout and RSS budget. The Go
context cannot interrupt an encoder calculation already running. Blocking
attention reduces storage, while global attention computation remains quadratic
in each sequence length. The 4 096-token pilot window is a configured admission
budget, not demonstrated long-context quality or a resource guarantee.
