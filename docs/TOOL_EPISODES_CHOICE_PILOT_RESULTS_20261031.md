# Closed-choice tool episodes: pilot results

**31 October 2026.** Pilot under the [closed-choice step policy](TOOL_EPISODES_CHOICE_MODE_V1.md) (issue #55): can a small CPU classifier drive a bounded tool loop of three to five steps when the harness lists the possible next actions? Four candidates on the pinned macOS CPU runtime, each with the same inner profile already used for its context/capability/physics row. Frozen pack [tool-episodes-choice-v1](../datasets/tool-episodes-choice-v1/README.md): 32 episodes, 20 TRAIN and 12 TEST. References are agent-authored and pending human review.

## Results

| Model / runtime | Procedure correct / 32 | TRAIN / 20 | TEST / 12 | Task success / 12 | Correct stop / 32 | FR / 16 | EN / 16 | Execution |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| D3 mini · macOS CPU | **28** | 18 | 10 | 10/12 | 28/32 | 12 | 16 | 32 `ok` |
| D3 nano · macOS CPU | **16** | 12 | 4 | 10/12 | 17/32 | 6 | 10 | 32 `ok` |
| D3 lite · macOS CPU | **14** | 9 | 5 | 9/12 | 15/32 | 8 | 6 | 32 `ok` |
| Vela 2.0 0.3B · macOS CPU | **0** | 0 | 0 | 0/12 | 0/32 | 0 | 0 | 32 `ok` |

A case is **procedure correct** when every chosen action was legal, the episode ended with the right outcome (computed total, clarification or stop with the right reason) and no budget was exceeded. **Task success** counts the twelve episodes whose correct end is a total computed by the real sum tool. Public aggregate: [analysis.json](evidence/choice-episodes-20261031/analysis.json).

## What each model did

| Expected end | Cases | D3 mini · macOS CPU | D3 nano · macOS CPU | D3 lite · macOS CPU | Vela 2.0 0.3B · macOS CPU |
|---|---:|---|---|---|---|
| normal or one-retry route (total expected) | 12 | complete 10, persistent error 2 | complete 10, step limit 2 | complete 9, step limit 3 | unavailable 11, partial data 1 |
| identifier missing (clarification expected) | 4 | missing information 4 | missing information 2, persistent error 2 | missing information 4 | unavailable 4 |
| partial table (clarification expected) | 4 | partial data 4 | step limit 3, partial data 1 | step limit 4 | unavailable 3, partial data 1 |
| empty table (stop expected) | 4 | no data 4 | no data 3, step limit 1 | step limit 4 | unavailable 4 |
| two lookup errors (stop expected) | 4 | persistent error 4 | step limit 4 | step limit 4 | unavailable 3, partial data 1 |
| sum tool becomes unavailable (stop expected) | 4 | unavailable 4 | step limit 3, unavailable 1 | unavailable 2, partial data 1, step limit 1 | unavailable 3, partial data 1 |

Each cell lists how the episodes of that route actually ended; `step limit` means the model kept acting until the five-step budget ran out instead of stopping.

- **D3 mini** (28/32, test 10/12) reads the observation state: every clarification and stop route ends correctly (identifier missing, partial table, empty table, two lookup errors, tool unavailable), and every normal route reaches the computed total. Its four failures are all in French and identical: after the first transient lookup error it declares a persistent error instead of using the one permitted retry (twice on the one-retry route, where a total was reachable, twice on the two-error route, where the stop came one lookup too early). In English it retries.
- **D3 nano** (16/32) and **D3 lite** (14/32) chain lookup → sum → total correctly (10/12 and 9/12 task successes) but, after a partial or empty table or a persistent error, they mostly look the table up again until the step budget ends: they keep acting where the observation says to stop.
- **Vela 2.0 0.3B** (0/32) chose a terminal stop at the first step in every episode, mostly "tool unavailable", whatever the state: no tool was ever called. This is a collapse onto one option, not state reading.

## Execution

| Model / runtime | Model decisions | Tool calls executed | Inner statuses | Median / max call s | Worker RSS peak MiB | Restarts |
|---|---:|---:|---|---:|---:|---:|
| D3 mini · macOS CPU | 76 | 44 | 76 `ok` | 74.0 / 92.7 | 7,884 | 0 |
| D3 nano · macOS CPU | 118 | 53 | 118 `ok` | 31.3 / 46.4 | 3,452 | 0 |
| D3 lite · macOS CPU | 125 | 52 | 125 `ok` | 13.8 / 17.4 | 1,749 | 0 |
| Vela 2.0 0.3B · macOS CPU | 32 | 0 | 32 `ok` | 0.2 / 0.2 | 1,225 | 0 |

Every listed run completed all 32 episodes in a sealed archive. **D3 mini attempt 001** is kept and not ranked: 16 episodes ran, then the operator switched branches in the checkout while it ran; the D3 adapter's identity guard saw engine files change and closed, so the remaining 16 episodes are `d3_runtime_or_protocol_changed` errors caused by the operator, not by the model. Its aggregate is published ([attempt 001](evidence/choice-episodes-20261031/d3-mini-attempt-001.json)); attempt 002 reran all 32 episodes with nothing touched.

## Position check

The menu order is fixed by the harness (lookup, sum, success when available, then five terminal outcomes). The share of model decisions on each menu position shows whether a model reads the state or prefers a position.

| Model / runtime | Position 1 | Position 2 | Position 3 | Positions 4–8 | First-step choices |
|---|---:|---:|---:|---:|---|
| D3 mini · macOS CPU | 50% | 13% | 13% | 24% | call-lookup 28, finish-missing_information 4 |
| D3 nano · macOS CPU | 68% | 18% | 8% | 6% | call-lookup 28, finish-missing_information 2, finish-persistent_error 2 |
| D3 lite · macOS CPU | 62% | 29% | 7% | 2% | call-lookup 28, finish-missing_information 4 |
| Vela 2.0 0.3B · macOS CPU | 0% | 0% | 12% | 88% | finish-unavailable 28, finish-partial_data 4 |

Position 1 is the lookup whenever an identifier is supplied, the correct first action in 28 of 32 episodes, so a high share there is expected; repeating it after a partial, empty or failed lookup is the error pattern above.

## What this shows and does not show

- It answers the pilot question for these four models only: a 4.5B classifier drives this bounded loop from a harness menu almost entirely (one French retry pattern aside); the 0.85B and 2.2B ones follow the happy path but do not stop on adverse observations; the 0.3B model does not read the state.
- The menu offers the five terminal outcomes at every step, including "persistent error" before the retry budget is spent; that is a harness choice and it is what exposes the French early stop.
- It does not compare with the generated-JSON contract (Qwen3-4B, held-out 9/24): premature success and malformed actions are impossible here by construction.
- 32 correlated cases on seven fault routes, FR/EN pairs and repeated routes across sources; the TEST split has 12 cases. Menu wording and order are harness choices and part of every score.
- Two synthetic tools; no live service, product workflow or open tool generation.

## Reproduce

```bash
python3 -m deposium_bench run --profile profiles/d3-mini-macos-choice-episodes.json \
  --dataset datasets/tool-episodes-choice-v1/cases.jsonl --output results/d3-mini-macos-choice-episodes-NEXT
python3 scripts/export-choice-episodes.py --run D3miniMacos=results/d3-mini-macos-choice-episodes-NEXT=profiles/d3-mini-macos-choice-episodes.json \
  --output /tmp/choice-episodes.json
```
