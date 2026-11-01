# Facade routing with human confirmation

**90 synthetic closed-choice cases, 45 FR/EN families, frozen on 1 November
2026 before any prediction, in two variants** built from [`specs.json`](specs.json):

* `facade-routing-hitl-v1` (this directory): nine options, the eight routing
  categories plus *human confirmation*. Cases SHA-256
  `80a65a54eb1ce33e2e6c6dd9b18a29a39a63ad92928a230b51fecacb344719fa`.
* [`facade-routing-hitl-8opt-v1`](../facade-routing-hitl-8opt-v1/): the eight
  usual options; a request hesitating between two categories accepts either.
  Cases SHA-256 `3901e26503d37ce80fb1d06af3065f1bc021a9101ca62f620dab7b32330ca521`.

16 families need a human (8 hesitations, 8 irreversible or sensitive
actions), 21 are close but clear controls, 8 are out of scope or too vague.
Splits: 14 TRAIN, 14 calibration, 62 TEST cases. [Design and scoring](../../docs/FACADE_ROUTING_HITL_DESIGN_20261101.md).

```bash
python3 scripts/build-facade-routing-hitl.py --check
```

References are agent-authored, written without access to any router rule, and
pending human review.
