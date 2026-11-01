# Facade routing: small CPU classifiers against the production router

**1 November 2026 — five complete observations on `facade-routing-v1`
([#56](https://github.com/theseedship/classification_tests_deposium/issues/56), option B).**
80 synthetic FR/EN requests to a document assistant; each asks which of eight
tool categories should handle the request, or *none* (out of scope or too
vague). Every candidate answered all 80 cases (`ok`). References are
agent-authored, written without access to any router rule, and pending human
review.

[Design, fixed before predictions](FACADE_ROUTING_DESIGN_20261031.md) ·
[Pack](../datasets/facade-routing-v1/README.md) ·
[Aggregate](evidence/facade-routing-20261101/analysis.json) ·
[All results](RESULTS.md#facade-routing-model-vs-router)

## Scores

| Candidate | Correct / 80 | Test / 48 | Direct /28 | Paraphrase /28 | Refused alternative /10 | Two-step /4 | Out of scope or vague /10 | Median call |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D3 mini · macOS CPU | 79/80 | 47/48 | 28/28 | 28/28 | 9/10 | 4/4 | 10/10 | 29.8 s |
| D3 nano · macOS CPU | 76/80 | 45/48 | 27/28 | 26/28 | 9/10 | 4/4 | 10/10 | 11.6 s |
| D3 lite · macOS CPU | 71/80 | 40/48 | 27/28 | 21/28 | 9/10 | 4/4 | 10/10 | 5.1 s |
| Vela 2.0 0.3B · macOS CPU | 64/80 | 34/48 | 26/28 | 17/28 | 9/10 | 2/4 | 10/10 | 64 ms |
| Production router · private replay | 28/80 | 10/48 | 14/28 | 5/28 | 0/10 | 0/4 | 9/10 | replay, < 1 s total |

The production router is a deterministic function replayed locally at a
pinned private revision; its row is **not externally reproducible**. Two
replays gave identical answers. Only its aggregate scores, the revision hash
and the recording hash are public: no code, rule, keyword or configuration.
Its fallback answer (no recognized intent) is scored as *none*, as fixed in the
design before any prediction. Counting that fallback as its default category
instead would lower it to 22/80, so the fixed mapping does not understate it.

## Per category

Correct / 10 per expected category (all splits).

| Candidate | Search | Analyse | Visualise | Graph | Evaluate | Process | System | None |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D3 mini · macOS CPU | 10 | 10 | 10 | 10 | 10 | 10 | 9 | 10 |
| D3 nano · macOS CPU | 10 | 10 | 10 | 9 | 10 | 10 | 7 | 10 |
| D3 lite · macOS CPU | 10 | 10 | 10 | 8 | 8 | 10 | 5 | 10 |
| Vela 2.0 0.3B · macOS CPU | 10 | 7 | 8 | 7 | 6 | 9 | 7 | 10 |
| Production router · private replay | 5 | 0 | 4 | 2 | 3 | 5 | 0 | 9 |

## Paired with the router

Over the 80 cases: both right, only the model right, only the router right,
neither.

| Model | Both | Model only | Router only | Neither | Test: model only / router only |
|---|---:|---:|---:|---:|---:|
| D3 mini · macOS CPU | 28 | 51 | 0 | 1 | 37 / 0 |
| D3 nano · macOS CPU | 28 | 48 | 0 | 4 | 35 / 0 |
| D3 lite · macOS CPU | 28 | 43 | 0 | 9 | 30 / 0 |
| Vela 2.0 0.3B · macOS CPU | 27 | 37 | 1 | 15 | 24 / 0 |

## Reading

- Every classifier scores at least as well as the router on every request
  kind. The gap is widest on paraphrases (requests that avoid the obvious
  word, written on purpose: router 5/28, classifiers 17–28/28) and refused
  alternatives such as "no chart needed" (router 0/10, classifiers 9/10).
- D3 mini (79/80, test 47/48) is close to the pack's ceiling: the pack
  separates the router from the classifiers, but has too few hard cases to
  rank the strongest classifiers reliably.
- *System* (service health, logs, resources) is the weakest category of the
  three D3 models; Vela 2.0 0.3B mostly falls back to *search* on analyse,
  evaluate and graph requests.
- The classifiers read the eight category descriptions supplied with each
  request; the router reads only the request, with its own fixed rules. That
  is how each works, not a handicap added by the bench.
- **Scope.** The router's role in the application is narrower than this
  pack. A low score here
  measures this request-to-category function on these synthetic requests; it
  does not mean the application fails on them. Ten requests per category and
  correlated FR/EN pairs do not support a general ranking.

## Cost

| Model | Median inference | p95 | Worker RSS peak |
|---|---:|---:|---:|
| D3 mini · macOS CPU | 29.84 s | 33.47 s | 7,531 MiB |
| D3 nano · macOS CPU | 11.61 s | 13.46 s | 3,275 MiB |
| D3 lite · macOS CPU | 5.07 s | 6.03 s | 1,603 MiB |
| Vela 2.0 0.3B · macOS CPU | 0.06 s | 0.09 s | 1,199 MiB |

Inference time per request on the pinned macOS CPU runtime, excluding model load. The router's replay of all 80 requests takes under a second.

## Provenance

- Classifier rows: the existing macOS CPU profiles of D3 lite, D3 nano,
  D3 mini and Vela 2.0 0.3B (same runtime lock and revisions as their context
  rows), run one at a time through the shared engine.
- Router row: its answers enter the engine as a `harness_control` recording
  kept outside Git; the public aggregate carries its revision and hashes.
- The aggregate is written by `scripts/export-facade-routing.py`, which
  verifies every seal, the pack hash, the tracked profiles and the model
  revisions, and writes no request text or raw output.
