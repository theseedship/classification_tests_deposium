# Facade routing with human confirmation: results

**1 November 2026 — can a model tell when to ask a human before acting?**
D3 lite, nano and mini as Q8 on Apple Metal, Vela 2.0 0.3B on CPU and a private
replay of the production router, on both frozen variants (90 FR/EN requests,
62 TEST). Every answer `ok`. [Design and scoring rule](FACADE_ROUTING_HITL_DESIGN_20261101.md) ·
[Packs](../datasets/facade-routing-hitl-v1/README.md) ·
[Aggregate](evidence/review-packs-20261101/facade-hitl.json) ·
[All results](RESULTS.md#facade-routing-human-confirmation)

TEST has 12 hesitations between two categories, 12 irreversible or sensitive
actions, and 38 requests that should not be escalated (26 clear controls,
6 out of scope, 6 too vague).

## 1. Explicit option: the model must choose "human confirmation"

| Model / runtime | Hesitations asked /12 | Irreversible asked /12 | False alarms /38 | Correct / 90 (TEST /62) |
|---|---:|---:|---:|---:|
| D3 mini · Q8 Metal | 0 | **9** | **0** | 71 (47) |
| D3 nano · Q8 Metal | 0 | 5 | 2 | 61 (39) |
| D3 lite · Q8 Metal | 0 | 0 | 1 | 49 (30) |
| Vela 2.0 0.3B · CPU | 0 | 1 | 4 | 44 (29) |
| Router · private replay | 0 | 0 | 0 | 26 (17) |

D3 mini asks before deleting, overwriting, purging or exporting sensitive
data, and never asks on a clear request. No model asks when a request
hesitates between two categories: they pick one (D3 mini picks a plausible
candidate 11 times of 12).

## 2. Own confidence: ask when the top-1 probability is low

Eight options; τ fixed on TRAIN + calibration (28 cases) by balanced accuracy,
applied unchanged to TEST.

| Model / runtime | τ | Detected /24 (hesitations, irreversible) | False alarms /38 | AUC | Routing correct when not escalated |
|---|---:|---:|---:|---:|---:|
| D3 mini · Q8 Metal | 0.892 | 18 (8, 10) | 12 | 0.83 | 32/32 |
| D3 nano · Q8 Metal | 0.889 | 18 (10, 8) | 14 | 0.81 | 30/30 |
| D3 lite · Q8 Metal | 0.921 | 19 (9, 10) | 17 | 0.74 | 23/26 |
| Vela 2.0 0.3B · CPU | 0.942 | 20 (11, 9) | 22 | 0.72 | 20/20 |

The router returns no probability and is not thresholded.

## Reading

- **The two approaches are complementary.** The explicit option is precise
  (D3 mini: 9/12 irreversible actions, no false alarm) but blind to
  hesitation. The model's own confidence does reveal hesitation (8–11/12) but
  also escalates about a third of the clear requests.
- **D3 mini's confidence is the best calibrated** (AUC 0.83): when it does
  not escalate, all 32 TEST requests it routes are correct.
- A product would combine both: the explicit option for irreversible or
  sensitive actions, and a confidence threshold, tuned on real traffic, for
  ambiguity. Here, adding the confidence threshold to D3 mini's explicit
  option gives 18/24 detections for 12 false alarms.

## Boundaries

References are agent-authored and pending human review; what counts as
"sensitive" is a product decision that a human should confirm. The first
freeze of these packs reused three requests of other splits; they were
replaced and every candidate was rerun on the corrected packs (runs on the
first freeze stay local and unpublished). τ is fitted on 28 cases, so its
value is indicative. Correlated FR/EN pairs do not support a general ranking.
