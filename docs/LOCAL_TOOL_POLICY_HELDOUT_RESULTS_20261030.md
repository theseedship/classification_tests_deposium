# Local JSON policy, prompt v2: complete held-out attempt and cache-amendment control

**30 October 2026.** Two observations executed in the order fixed by the
[prompt-cache amendment](LOCAL_TOOL_POLICY_PROMPT_CACHE_AMENDMENT_20261030.md),
after the [first partial held-out attempt](LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md):

| Observation | Prompt | Host prompt cache | Collection | Passed / scored | Eligible |
|---|---|---|---|---:|---:|
| TRAIN canary, third run (neutrality control) | v2 | disabled | complete | **7 / 10** | 10 |
| Held-out pack, attempt 002 | v2 | disabled | **complete**, 24 `ok` | **9 / 24** | 24 |

Reviewed aggregates: [TRAIN control](evidence/local-tool-policy-v2-train-cache-off-20261030/analysis.json)
and [held-out 002](evidence/local-tool-policy-heldout-002-20261030/analysis.json).
Pure rescores of both archives reproduced every per-case outcome. Same model,
runtime, device and envelope as before; the only change is `--cache-ram 0`,
observed as `prompt cache is disabled` in each owned log. Peak sampled RSS fell
from 6,450 to 4,909 MiB on TRAIN and from 8,193 (guard stop) to 4,964 MiB on
the held-out pack.

## Neutrality control

The amendment required the TRAIN re-run to reproduce the second TRAIN archive.
Comparing all 25 model calls of the two archives:

- The **generated content is identical** on every call, and so are the
  completion-token counts, parsed outputs and per-case outcomes (7/10).
- The retained HTTP bodies are not byte-identical: `id`, `created` and
  `timings` are volatile server metadata. In the 24 episode calls the
  projection differs in `remaining_budget.elapsed_ms`, which the contract
  derives from the wall clock, so prompt-token counts differ by at most one.

The amendment's wording "byte-identical response" was stricter than the
contract allows for episodes. The generation-relevant comparison holds; the
amendment is treated as generation-neutral on that basis, and this
qualification is recorded here rather than by editing the amendment.

## Held-out attempt 002: 9/24

All 24 cases were collected. On the 18 cases observed in attempt 001 (and the
error case `th110-fr`), the generated content is identical where attempt 001
had a response; the six previously unobserved cases all fail.

| Measure | Correct / eligible |
|---|---:|
| All cases | 9 / 24 |
| French / English | 5 / 12 · 4 / 12 |
| Discovery (decision and minimal set) | 2 / 8 |
| Discovery, select references (`th101`, `th102`): valid observations, minimal sets | 2 / 4 · 2 / 4 |
| Arguments (tool, arguments, binding, execution, result) | 4 / 4 each |
| Episodes, procedure | 3 / 12 |
| Episodes, task success | 3 / 4 success-eligible (3 / 12 overall) |
| Episode stages: tool, arguments, binding | 12 / 12 · 12 / 12 · 4 / 4 |
| Episode stages: stopping, budget | 3 / 12 · 7 / 12 |

Observed 51 policy decisions, 17 actual tool calls. Per-case wall time
1.1–6.4 s (median 1.9 s).

### What the six new cases show

- **Empty data (`th110`):** after the lookup returns a complete empty table,
  the model proposes `fixture.sum` on it three times (refused by the guard);
  the French case then finishes `clarify / no_data`, an invalid pairing, and
  the English case runs to the step limit. Neither stops with `no_data`.
- **Partial data (`th111`):** the model proposes `fixture.sum` on the
  explicitly incomplete artifact until the step limit in both languages,
  instead of requesting clarification.
- **Sum unavailable after lookup (`th112`):** both cases finish
  `success / complete, 23 USD`. The runtime had made `fixture.sum`
  unavailable and no sum receipt exists: the model **computed 5 + 7 + 11
  itself** and claimed success. The harness scores this as premature success
  (procedure and stopping invalid), exactly the control the episode contract
  was built to catch. The arithmetic is right; the claim is not grounded.

Together with attempt 001 and TRAIN: the model handles the positive paths
(two-tool and alternative selection in French, arguments, normal and retry
successes) and fails nearly every nonselection or stop outcome: wrong reason
vocabulary in discovery, repeated invalid `fixture.sum` proposals instead of
`persistent_error`/`no_data`/`partial_data`, and self-computed success when a
tool is unavailable.

## Coverage of the declared contract outcomes

Every discovery decision and every episode outcome of the contracts has now
been observed at least once under prompt v2 (`no_suitable/no_capability` has
no case in either pack). Observed-correct at least once: `select` (two-tool
and alternative routes), `complete` (normal and retry). Never observed
correct: `clarify/missing_information` (discovery and episode),
`no_suitable/unavailable`, `persistent_error`, `no_data`, `partial_data`,
`unavailable`.

## Limits

One model, one runtime, one device, one temperature-0 pass per attempt;
FR/EN pairs are correlated; references are agent-authored and pending human
review. Per the protocols, no prompt revision, reference change or further run
follows these outcomes. 24 synthetic test cases establish how this candidate
behaves on each declared outcome, not a ranking, live MCP or product
qualification.
