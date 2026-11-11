# GLiClass v4 2B (then 9B) on the closed-choice packs: protocol

**Fixed on 11 November 2026, before any dataset prediction by GLiClass v4 2B.**
Question: on our own packs, does Knowledgator's GLiClass v4 2B do as well as
the D3 models of its size, and is the 9B worth a full run afterwards? The
publisher reports Decision Index and KGJevBench results on its own protocol
and NVIDIA hardware; those are claims, not results here. GLiClass is a
different family (decoder-KV classifier with a label scorer), not a D3
readout: a comparison covers model, rendering and runtime together.

## Identities

- Model: [`knowledgator/gliclass-v4-2b`](https://huggingface.co/knowledgator/gliclass-v4-2b/tree/40fe023b45e8d97d1ae4f7f9342279ac1c76317d)
  at `40fe023b`, Qwen3.5-2B backbone, eight publisher files verified against
  the Hub's LFS and Git hashes in
  [`profiles/gliclass-v4-2b-assets.json`](../profiles/gliclass-v4-2b-assets.json)
  (weights SHA-256 `8b830837…`, 4,733,273,906 bytes). `training_args.bin` and
  `trainer_state.json` are not downloaded. This checkpoint ships **without the
  post-hoc calibrator** that the 9B has: single-label probabilities are the raw
  softmax over label logits. The decision is the arg-max, as for the 9B.
- Code: the official GLiClass source at
  [`6a00f806`](https://github.com/Knowledgator/GLiClass/tree/6a00f8067648f25aa0f4f477d167c5f391cb4165),
  unchanged from the 17 October 9B run. The five upstream commits since then
  add FP8, `torch.compile`, adapters and an HTTP service; none changes the
  BF16 eager forward used here.
- Runtime: the audited `runtimes/gliclass/runtime.lock` environment (Python
  3.12.12, torch 2.14.0, transformers 5.19.0). The checkpoint was saved with
  transformers 5.20.0; the configuration differs from the 9B only in sizes and
  the absent calibrator.
- Adapter: `deposium_bench/gliclass_adapter.py` and the unchanged worker and
  backend bridges. The adapter now accepts two pinned identities, the 9B at
  `14d11a92` and the 2B at `40fe023b`, each with its own fixed RSS ceiling;
  every other check is unchanged.
- Profile: [`profiles/gliclass-v4-2b-mps.json`](../profiles/gliclass-v4-2b-mps.json).

## Input and execution

Same projection as the 9B run and as the publisher's documented decision
mapping: the case context is the text, the question is the instruction
(`prompt`), the ordered option descriptions are the labels, one forward per
case, `single-label`, `max_length` 4,096 tokens counting the labels. An input
that would be truncated, or that contains a reserved GLiClass marker, is
refused as `unsupported` with no forward pass. Option identifiers, splits,
annotations and expected answers never reach the model. Nothing is trained or
tuned on any split; `train` and `calibration` cases are scored like `test`.

MPS, BF16, eager attention, two threads, offline worker with network calls
blocked, 30 s per call. Envelope: **16,384 MiB** worker group RSS and an
8,192 MiB host reserve (the 9B keeps its historical 32,768 MiB). One model and
one campaign at a time on the host.

A synthetic smoke (two invented options, plus an oversized refusal) ran before
this protocol with no dataset case: `completed:true`, correct synthetic choice,
`gliclass_context_overflow` on the oversized control.

## Packs and order

`python3 -m deposium_bench run` with the shared engine and scorers, one sealed
archive per pack, in this order:

| Pack | Cases | Test | Options | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| context-choice-v1 | 132 | 66 | 4 | `767e239c…` |
| capability-choice-v1 | 192 | 96 | 4 | `0b409a09…` |
| physics-choice-v1 | 48 | 36 | 4 | `e21cd2e0…` |
| facade-routing-v1 | 80 | 48 | 8 | `03f30a62…` |
| facade-routing-advanced-v1 | 96 | 64 | 8 | `42364fed…` |
| facade-routing-complex-v1 | 96 | 64 | 8 | `389d362d…` |
| passage-relevance-v2 | 512 | 256 | 3 | `f95b3a60…` |
| facade-routing-hitl-v1 | 90 | 62 | 9 | `0bd9506d…` |
| facade-routing-hitl-8opt-v1 | 90 | 62 | 8 | `50bc0892…` |

1,336 cases in all. Passage evidence (relevance, support, answerability over
fixed pools), executed episodes and the first-tool proposals use other
contracts and are not run. A pack stopped by a guard is reported partial and
kept; a technical rerun gets the next attempt number and both are kept.

## Comparison and reading rule

Comparators are the published rows on the same pack bytes and scorers:
**D3 nano** (2.2B backbone, the same size class) as the primary comparator,
D3 mini (4.5B) as the secondary one, both Q8 Metal (macOS CPU rows where a
Metal row is missing). Answers are paired case by case where the D3 archive is
still on this host; otherwise counts are compared.

Fixed now, before seeing any GLiClass output: the 2B is **worth further work**
only if, on the held-out `test` split, it matches or beats D3 nano on at least
five of the nine packs **and** its summed test score over the nine packs is at
least D3 nano's. Otherwise the answer is no for our use, whatever the
publisher's benchmarks. This is an exploratory reading on synthetic,
agent-authored references awaiting human review, not a product promotion.

The 9B (`14d11a92`, 17 GB BF16) then runs the same packs with the same code
and its historical profile, against D3 Flash Q4 Metal and D3 mini. Its
17 October context run is not repeated unless its runtime identity changes.

## Reporting

Per pack: correct over all cases and over `test`, every non-`ok` status,
median and p95 call time on MPS (the first call includes warm-up), peak GPU
allocation and worker RSS as separate measurements, never summed. Raw
archives stay under ignored `results/`; only reviewed aggregates are published.
