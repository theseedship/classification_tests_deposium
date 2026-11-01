# Passage relevance v2: realigning the relevance projection

**Fixed on 1 November 2026, before any prediction on the v2 pack.**

## What went wrong in v1

The v1 relevance projection asks, for one question and one passage, which of
four grades applies: 3 direct, 2 partial, 1 "concerns the topic without
deciding", 0 "irrelevant". Across every published row (D3 and Clef Flash Q8 on
Metal, D3 lite/nano/mini and Vela on CPU and Metal), grade 1 scores 0–12%.
A review of the 224 rotation-0 test decisions shows two different causes:

1. **An ill-posed boundary.** Grade-1 passages are decoys: a sibling variant
   ("Caldrin S" for "Caldrin R"), another condition ("at 28 °C" for "at 17 °C"),
   another field or relation. "Concerns the topic" and "irrelevant" both
   describe them; models answer 0 for some decoy types and 3 for others, so
   the v1 score mixes a genuine error (taking a decoy for direct evidence)
   with an arbitrary one (0 versus 1). No retrieval decision uses the 0/1
   difference: neither passage may serve as evidence.
2. **An undecidable item.** `value_premise` passages (grade 2) give a value for
   an entity whose link to the question sits in another passage ("the sheet
   for Lorim gives 73" when only another passage says Lorim is Merova's batch).
   Judged alone, the passage cannot be known to matter; every model answers 0.

The references themselves were checked on examples of every role and are
consistent with the scenario definitions. The support and answerability
references were checked the same way and are kept: their common errors are
genuine model errors (entity-level decoys taken as support or refutation; an
explicit exception taken for a conflict).

## v2

[`passage-relevance-v2`](../datasets/passage-relevance-v2/README.md): three
options (direct, partial, no usable evidence with an explicit definition of
decoys), `value_premise` excluded, unique visible inputs only, option order
rotated, rotation-0 calibration (256) and test (256) cases. It is a new pack:
v1 rows and scores stay published unchanged.

## Runs

D3 lite, nano and mini as Q8 GGUF on Apple Metal (protocol
[D3_SMALL_GGUF_GPU_PROTOCOL_20261101](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md),
`small-gguf-8g-v1`) and Vela 2.0 0.3B on the macOS CPU runtime, one at a time,
all 512 cases. Report correct / all, test / 256, per-class and macro accuracy,
per v1 role, and the majority baseline.
