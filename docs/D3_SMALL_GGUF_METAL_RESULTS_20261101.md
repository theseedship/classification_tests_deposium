# D3 lite, nano and mini Q8 on Apple Metal

**1 November 2026 — complete observations of the three small D3 decision
models as Q8 GGUF on Apple Metal, on every closed-choice pack.** Same weights
as the macOS CPU rows (byte-identical `vllm-sr` sources), converted by
ggml-org, served by upstream llama.cpp at `efe3626b`. Every case returned `ok`
and every layer was offloaded to Metal. References are agent-authored and
pending human review.

[Protocol and amendment](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md) ·
Aggregates: [lite](evidence/d3-small-gguf-metal-20261101/d3-lite.json),
[nano](evidence/d3-small-gguf-metal-20261101/d3-nano.json),
[mini](evidence/d3-small-gguf-metal-20261101/d3-mini.json),
[facade routing](evidence/facade-routing-tiers-20261101/easy-metal.json) ·
[All results](RESULTS.md) · NVIDIA [#65](https://github.com/theseedship/classification_tests_deposium/issues/65),
AMD [#66](https://github.com/theseedship/classification_tests_deposium/issues/66)

## The answer: same decisions, two orders of magnitude faster

Correct / all on Metal Q8, then the same model on the macOS CPU runtime
(BF16 backbone, two threads), the share of identical answers, and the median
call time.

| Model | Pack | Metal Q8 | CPU BF16 | Identical answers | Median call, Metal / CPU |
|---|---|---:|---:|---:|---:|
| D3 mini | Context (132) | 119 | 119 | 132/132 | 0.10 s / 17.3 s |
| D3 mini | Capability (192) | 192 | 192 | 192/192 | 0.33 s / 78.9 s |
| D3 mini | Physics (48) | 39 | 39 | 48/48 | 0.10 s / 16.9 s |
| D3 mini | Facade routing (80) | 79 | 79 | 80/80 | 0.16 s / 30 s |
| D3 mini | Passages (1,408 decisions) | 266 / 517 / 102 | 266 / 527 / 104 | 1,386/1,408 | 0.11 s / 20.2 s |
| D3 nano | Context | 117 | 117 | 132/132 | 0.05 s / 7.3 s |
| D3 nano | Capability | 187 | 188 | 191/192 | 0.14 s / 29.4 s |
| D3 nano | Physics | 27 | 28 | 47/48 | 0.05 s / 7.8 s |
| D3 nano | Facade routing | 75 | 76 | 79/80 | 0.07 s / 11.7 s |
| D3 nano | Passages | 252 / 366 / 94 | 252 / 366 / 93 | 1,397/1,408 | 0.06 s / 8.6 s |
| D3 lite | Context | 94 | 94 | 132/132 | 0.03 s / 3.2 s |
| D3 lite | Capability | 170 | 168 | 189/192 | 0.08 s / 13.3 s |
| D3 lite | Physics | 14 | 14 | 47/48 | 0.03 s / 3.1 s |
| D3 lite | Facade routing | 71 | 71 | 79/80 | 0.04 s / 5.2 s |
| D3 lite | Passages | 231 / 449 / 88 | 229 / 439 / 88 | 1,392/1,408 | 0.03 s / 3.7 s |

Passage cells are relevance / support / answerability out of 512 / 768 / 128.

- Q8 changes at most 2.1% of the answers (one physics case of 48). Where a score moves, it moves by
  one or two cases in either direction (lite gains two capability cases; nano
  loses one capability and one physics case; mini loses ten support and two
  answerability decisions out of 1,408 passage decisions).
- Speed-up is 100× to 240×. D3 mini answers a facade-routing request in about
  160 ms, which makes it usable for interactive routing on this machine; on the
  CPU runtime it took 30 s.
- Latency scopes differ: Metal times the adapter call including loopback HTTP;
  CPU times the worker call. Both are medians over `ok` calls of one pass.

## Memory

Sampled process-group RSS peaks (unified memory, not a GPU allocation):
D3 lite 1.4 GiB, D3 nano 2.8–2.9 GiB, D3 mini 5.4–5.5 GiB, against 1.8, 3.5 and
8.0 GiB for the CPU workers on passages. 25 layers for lite and nano, 33 for mini.

## Attempts and envelope

- The first Metal series refused most phases at admission (no model load, no
  archive): the 18 GiB envelope needs 26 GiB estimated free memory. A dated
  amendment introduced `small-gguf-8g-v1` (8 GiB ceiling, same 8 GiB reserve)
  for the phases not yet run. D3 lite context and D3 mini context, capability
  and physics completed under the 18 GiB envelope and keep it.
- D3 mini facade routing attempt 001 was interrupted by the operator (unsealed)
  and D3 mini passages attempt 001 stopped at its warm-up (preparation missed
  the calibration warm-up input). Both are recorded, unranked; attempt 002 is
  the published row.
- The context, capability and physics archives were written before the
  facade-tier scorer change; the exporter verifies their seals, rescores them
  into derived archives without inference, and requires identical scores.

## Boundaries

Each Metal row is a separate runtime identity beside its CPU row; nothing is
pooled. One Apple M5 Pro host; other GPUs are the subject of #65 and #66. The
first-tool proposal task (24) was not run on Metal. Single pass per case.
