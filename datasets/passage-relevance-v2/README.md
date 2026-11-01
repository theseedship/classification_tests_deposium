# Passage relevance v2

**512 synthetic closed-choice cases, 3 options, six languages.** Frozen on
1 November 2026 before any candidate prediction. Cases SHA-256
`f95b3a604af5c1762ac5a59e096f35de6c88ff7a601e67c5483cf87516f154a0`.
Derived deterministically from [passage-evidence-v1](../passage-evidence-v1/README.md)
(rotation-0 calibration and test pools, the pools of every published passage
campaign); no v1 reference is changed. [Why and how](../../docs/PASSAGE_RELEVANCE_V2_DESIGN_20261101.md).

Each case shows one question and one passage and asks how much the passage
helps answer it:

| Option | v1 grades | Cases |
|---|---|---:|
| Directly establishes or refutes the requested fact | 3 | 112 |
| Supplies part of the necessary evidence | 2 | 16 |
| No usable evidence: off-topic, or another entity, condition or value than the one asked | 1 and 0 | 384 |

Passages whose v1 role is `value_premise` are excluded: they only help through
another passage, which a single-passage judgement cannot see. Identical
visible inputs are kept once (the `full` and `head_384` views often coincide).
Option order is rotated so each answer position holds about a third of the
cases. Classes are imbalanced: always answering *no usable evidence* scores
384/512, so report per-class and macro accuracy beside totals.

```bash
python3 scripts/build-passage-relevance-v2.py --check
python3 -m deposium_bench validate-cases --dataset datasets/passage-relevance-v2/cases.jsonl
```

References are agent-authored and pending human review.
