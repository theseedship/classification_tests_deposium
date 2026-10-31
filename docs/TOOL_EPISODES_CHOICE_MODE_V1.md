# Closed-choice step policy for bounded tool episodes (pilot)

**Fixed on 31 October 2026, before any candidate prediction.** Executed the same day: [results](TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md) (D3 mini 28/32 (test 10/12), D3 nano 16/32, D3 lite 14/32, Vela 2.0 0.3B 0/32). A narrow pilot
that answers one architectural question: *can a small CPU classifier drive a
bounded tool loop of three to five steps when the harness enumerates the
candidate actions?* It reuses the [episode contract](TOOL_EPISODES_CONTRACT_V1.md)
unchanged: actual fixture tools, actual observations fed back, independent
budgets, retained transcripts and pure rescore. Only the policy changes.

## What the mode does

At each step the harness derives a **menu** from the candidate-visible
projection alone (`deposium_bench/choice_episodes.py`):

| Menu item | Offered when | Action |
|---|---|---|
| `call-lookup` | the table identifier is supplied | `fixture.lookup` on that identifier within the permitted scope |
| `call-sum` | an actual lookup artifact exists | `fixture.sum` bound to the latest artifact, declared column and unit |
| `finish-success` | an actual `fixture.sum` receipt exists | success with that receipt's value and unit |
| five terminal outcomes | always, fixed order | clarify (missing information, partial data), stop (no data, unavailable, persistent error) |

The projection and the menu are rendered as one bilingual `bench.context-choice`
input (state text, question, options), sent to an inner choice adapter (D3,
Vela 2.0 or any context-choice adapter), and the chosen option is executed by
the ordinary episode runtime. The model never writes an action or a value. Each
step's menu, rendered input, hash and inner response are retained; a rescore
re-derives every menu and input from the archived projection and refuses any
mismatch (`validate_trace`).

## What it measures and what it removes

- Measured: reading an observation state (complete, partial, empty, error,
  tool unavailable) and picking the next step or the right terminal outcome;
  executing the lookup → sum → report sequence under budgets.
- Removed by construction: the premature-success failure (no success option
  exists before the actual sum receipt) and malformed actions. The generative
  contract keeps both; scores between the two modes are not comparable.
- Confounded: part of any score reflects the menu wording and its fixed order
  (position bias is reported, see below), not only the model.
- Overlap: the observations track of the capability pack already tests state
  reading on single steps; this pilot adds the executed chain.

## Frozen pack

[`datasets/tool-episodes-choice-v1`](../datasets/tool-episodes-choice-v1/README.md):
32 cases, 16 FR/EN families, 20 TRAIN and 12 TEST, cases SHA-256
`f249752d4ab464a5…`, derived by `scripts/build-choice-episodes-pack.py` from the three
public episode sources (14 fixture training cases, 6 canary cases, 12 held-out
cases) with one change: input schema v3 and a ten-minute elapsed budget per
episode, so CPU classifier wall time fits. Faults, requests, fixtures and the
eight-assertion references are byte-identical to the sources. Twelve cases are
success-eligible; twenty end in a clarification or a stop.

## Pilot candidates and order

Inner profiles are the pinned macOS CPU identities already observed on the
other packs; the outer profiles mirror their revision:

| Order | Outer profile | Inner profile | Inner per-call timeout |
|---:|---|---|---:|
| 1 | `profiles/d3-lite-macos-choice-episodes.json` | `d3-lite-macos-cpu.json` | 60 s |
| 2 | `profiles/vela2-03-macos-choice-episodes.json` | `vela2-03-macos-cpu.json` | 30 s |
| 3 | `profiles/d3-nano-macos-choice-episodes.json` | `d3-nano-macos-cpu.json` | 60 s |
| 4 | `profiles/d3-mini-macos-choice-episodes.json` | `d3-mini-macos-cpu.json` | 120 s |

One archive per candidate, fresh worker, no other CPU campaign running on the
host at the same time. Inner timeouts end the episode as `candidate_timeout`
and keep the case in the denominator.

```bash
python3 -m deposium_bench run --profile profiles/d3-lite-macos-choice-episodes.json \
  --dataset datasets/tool-episodes-choice-v1/cases.jsonl --output results/d3-lite-macos-choice-episodes-NEXT
```

## Reporting

Report for each candidate: procedure-correct cases / 32 (TRAIN / 20 and TEST
/ 12 apart), task success / 12 success-eligible, the seven stage metrics with
their own denominators, FR/EN, policy steps and tool calls observed, inner
statuses, and a **position check**: the distribution of chosen option positions
against the distribution of correct positions, from the retained menus. Compare
with the scripted control (14 fixture cases, procedure 14/14) and with the
generative Qwen3-4B held-out result (9/24) only as different contracts, never
as a ranking. Publish reviewed aggregates; raw archives stay local.

## Limits

Thirty-two correlated cases on seven fault routes; menu and wording fixed by
the harness; two synthetic tools; no live service, product workflow or open
tool generation. A good score shows that a cheap selector can drive this
bounded loop; it does not qualify an agent.
