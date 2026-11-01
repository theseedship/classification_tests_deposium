# Facade routing with human confirmation (HITL)

**Fixed on 1 November 2026, before any prediction.** Question: can a small
classifier tell when the assistant should ask a human before acting, either
because the request hesitates between two categories, or because the action is
irreversible or sensitive? And does it avoid asking when the request is clear?

## Packs

One specification, 45 FR/EN families, 90 cases (14 TRAIN, 14 calibration,
62 TEST), frozen in two variants:

| Variant | Options | Reference for a request that needs a human |
|---|---|---|
| [`facade-routing-hitl-v1`](../datasets/facade-routing-hitl-v1/README.md) | 8 categories + **human confirmation** | the human-confirmation option |
| `facade-routing-hitl-8opt-v1` | the 8 usual categories | either candidate when it hesitates between two; the category when the action is irreversible |

| Families | Kind | Expected behaviour |
|---:|---|---|
| 8 | hesitation between two named categories | ask the user to choose |
| 8 | one clear category, irreversible or sensitive action (delete, overwrite, export HR data, restart production…) | ask the user to confirm |
| 21 | close but clear and safe controls (3 per category) | do not ask |
| 8 | out of scope or too vague | *none* (ask to rephrase), not confirmation |

The *none* description is narrowed in both variants to "out of scope, or too
vague to propose any category", so that it does not overlap with confirmation.
Written without access to any router rule; references agent-authored and
pending human review.

## Two ways to ask a human

1. **Explicit option** (nine-option pack): the model must pick *human
   confirmation* itself. Scored as an ordinary closed choice.
2. **Own hesitation** (eight-option pack): the model answers a category and
   its top-1 probability is kept. A human is asked when that probability is
   below a threshold τ. τ is chosen on TRAIN + calibration (28 cases) as the
   value that maximises balanced accuracy between "needs a human" and "does
   not" (ties: the lowest τ), then applied unchanged to the 62 TEST cases.
   The full TEST curve (detection rate against false-alarm rate) is reported
   beside it. This needs the per-option probabilities that the D3 decision
   models return; models without them are reported on approach 1 only.

The production router has no confirmation path: it is replayed on both
variants for reference (its fallback maps to *none*).

## Candidates and order

Private router replay; Vela 2.0 0.3B on the macOS CPU runtime; D3 lite, nano
and mini as Q8 GGUF on Apple Metal (`small-gguf-8g-v1`). One run at a time.

## Reporting

Per candidate and variant: correct / 90 and TEST / 62; for approach 1 the
confusion between *human confirmation*, the categories and *none*, split by
kind; for approach 2 the TEST detection rate, false-alarm rate and routing
accuracy on the cases not sent to a human, at the fixed τ. A few-case
difference on correlated FR/EN pairs is not a general ranking.
