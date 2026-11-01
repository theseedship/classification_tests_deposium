# D3 Flash 4-bit on Uzu: protocol

**Fixed on 1 November 2026, before any dataset prediction on Uzu.** Question:
what does Mirai's 4-bit D3 Flash pack served by the Uzu engine score, how
fast and in how much memory, against D3 Flash Q8 and D3 mini Q8/Q4 on
llama.cpp Metal? This compares deployments (weights format, quantization method
and engine together); it cannot isolate the effect of Uzu alone.

## Identities

- Pack: [`trymirai/d3-flash-M`](https://huggingface.co/trymirai/d3-flash-M/tree/86f617b67e3f0ce02fe678c38801e2296a303777)
  at `86f617b6`, INT4 G64 (YAQA), six files in
  [`profiles/d3-flash-m-uzu-assets.json`](../profiles/d3-flash-m-uzu-assets.json);
  weights SHA-256 `dcf55ac5…`, as in the earlier functional check.
- Runtime: the official Uzu/Mirai CLI **0.6.15** release binary (archive
  `59ae1ced…`, executable `c3e57981…`), whose release commit is
  `d3d3a5b20a3de507522e1099457d1dae0243effb`. `deposium_bench/uzu_local.py` is
  repinned from `023bf5d9` to that commit: the source pin must match the binary,
  and building the runtime from source needs the Metal compiler, which this
  host does not have.
- Input preparation: `native/uzu-preparation/main.rs`, built by
  `scripts/build-uzu-preparation.py` against a clean checkout at the same
  commit, calls `hanashi::decision::DecisionEncoding` with the pack's codec
  configuration and tokenizer, never its weights.
  `scripts/prepare-uzu-inputs.py` writes the `deposium.uzu-input-preparation/v1`
  receipt (token count and token-ID digest per request body, plus a refused
  oversized control). On facade-routing-v1 its counts (254–317 tokens) equal
  those of the llama.cpp preparation of the same requests.
- Served model ID: `pack-d3-flash-M` (the pack directory name, read from
  `/v1/models` in a technical start with no dataset request).

## Envelope and order

`scripts/run-uzu-pilot.py --execute` with its fixed envelope: 4,096 prepared
tokens, one request and one question at a time, 30 s per call, 14 GiB sampled
group RSS, 8 GiB host reserve, at most 1,200 s per phase. The stock CLI
bootstraps its online catalogue at start (`egress_isolated:false`). One phase at
a time, no other campaign on the host:

1. facade-routing-v1, advanced, complex;
2. context-choice-v1, capability-choice-v1, physics-choice-v1;
3. passage-relevance-v2;
4. facade-routing-hitl-v1 and -8opt-v1.

Passage evidence (the passage pipeline) is not run on Uzu here.

## Reporting

Per pack: correct / all and TEST, every non-`ok` status, median call time,
sampled RSS; answers paired with D3 Flash Q8 Metal where it ran (context,
capability, physics) and with D3 mini Q8 and Q4 Metal on every pack. Raw
archives stay under ignored `results/`; only reviewed aggregates are published.
