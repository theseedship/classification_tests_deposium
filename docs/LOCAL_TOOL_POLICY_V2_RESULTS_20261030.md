# Local JSON policy, prompt v2: TRAIN re-run and partial held-out run

**30 October 2026.** Two new observations under the
[held-out protocol](LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md), executed in
its fixed order after the [prompt v1 TRAIN result](LOCAL_TOOL_POLICY_RESULTS_20261030.md)
(5/10):

| Observation | Prompt | Collection | Passed / scored | Eligible |
|---|---|---|---:|---:|
| TRAIN canary, second run | v2 | complete, 10 `ok` | **7 / 10** | 10 |
| Held-out pack, first attempt | v2 | **partial**, stopped by the RSS guard | **9 / 18** | 24 |

Reviewed aggregates: [TRAIN v2](evidence/local-tool-policy-v2-train-20261030/analysis.json)
and [held-out](evidence/local-tool-policy-heldout-20261030/analysis.json), produced by
`scripts/export-local-tool-policy.py` from the sealed private archives. Pure
rescores of both archives reproduced every per-case outcome without a model,
tool, clock or credential. Raw generations, templates, logs and local paths
stay outside Git. Same model, runtime, device and envelope as the first run:
Qwen3-4B-Instruct-2507 Q8 (`391c1e41…`), llama.cpp `efe3626b`, Metal 37/37,
4096 context, seed 42, temperature 0, 8 GiB RSS ceiling plus 8 GiB reserve.

## TRAIN canary with prompt v2: 7/10

| Measure | v1 | v2 |
|---|---:|---:|
| All cases | 5 / 10 | 7 / 10 |
| Discovery (final minimal set) | 0 / 2 | 1 / 2 |
| Arguments | 2 / 2 | 2 / 2 |
| Episodes, procedure | 3 / 6 | 4 / 6 |
| Episodes, task success | 3 / 4 | 4 / 4 |

Peak sampled RSS 6,450 MiB; per-case wall time 1.3–5.3 s (median 3.7 s).

- `tp001-fr` now passes: the shortlist contains the selected tool. `tp001-en`
  still fails, differently: the model pairs `decision: select` with
  `reason: no_capability`, a combination the contract rejects.
- Both transient-retry episodes now succeed. `tp005` (missing identifier) still
  fails in both languages: the model proposes `fixture.sum` without a lookup
  until the step limit instead of requesting clarification.

## Held-out pack with prompt v2: partial, 9/18 scored of 24

The owned server's sampled RSS grew monotonically across requests (about
5.6 → 6.0 → 6.7 → 7.6 → 8.2 GiB) and reached **8,193 MiB** during `th110-fr`,
the nineteenth case. The watcher stopped the owned process; that case is
retained as `error` (`local_json_transport_error`) and the five cases after it
as `missing`. The ceiling was not raised and the attempt was not repeated.
Statuses: 18 `ok`, 1 `error`, 5 `missing`; the six unobserved cases stay in
every eligible denominator and contribute zero.

| Measure | Correct / scored | Eligible |
|---|---:|---:|
| All cases | 9 / 18 | 24 |
| French / English | 5 / 9 · 4 / 9 | 12 · 12 |
| Discovery (decision and minimal set) | 2 / 8 | 8 |
| Discovery, select references (`th101`, `th102`) | 2 / 4 valid, 2 / 4 minimal | 4 |
| Arguments (tool, arguments, binding, execution, result) | 4 / 4 each | 4 |
| Episodes, procedure | 3 / 6 | 12 |
| Episodes, task success | 3 / 4 success-eligible observed | 4 |
| Episode stages: stopping, budget | 3 / 12 each | 12 |

Observed 19 case durations, 1.1–13.2 s (median 1.9 s; the 13.2 s case is the
transport error). The unobserved families are exactly `no_data`,
`partial_data` and `unavailable`: three of the four episode outcomes this pack
was meant to add remain **unobserved**, not failed.

### What the observed cases show

- **Discovery:** the shortlist rule is now respected everywhere. The remaining
  failures are the decision/reason pairing: `select` or `clarify` with
  `reason: no_capability` (`th101-en`, `th102-en`, `th103-fr`), `tool_ids` kept
  on a `clarify` (`th103`), and `no_capability` instead of `unavailable` on the
  unavailable-PDF family (`th104`). French two-tool and alternative selections
  passed; the same English cases did not.
- **Arguments:** 4/4, as in TRAIN.
- **Episodes:** both normal successes passed (`th107`). The retry family passed
  in English and failed in French (`th108-fr`): after the retried lookup the
  model proposed `fixture.sum` with an invalid binding until the step limit.
  Both persistent-error cases (`th109`) failed the same way instead of stopping
  with `persistent_error`.

These are model behaviors on synthetic cases under a frozen prompt. No
reference, guard or scorer was changed, and per the protocol no third prompt
revision follows a held-out outcome.

## Interpretation and limits

- Prompt v2 removed the contract-description failure of v1 (empty shortlist);
  the model's remaining discovery errors concern the reason vocabulary, and its
  episode errors concern stopping after an invalid or failed step.
- The RSS stop is an envelope outcome of the pinned runtime, not a quality
  result. Completing the 24-case collection requires a reviewed amendment of
  the session protocol (for example restarting the owned server between
  contracts under the same ceiling), proposed separately. A later attempt is
  a new archive; this partial archive is retained as recorded.
- One model, one runtime, one device, one temperature-0 pass; FR/EN pairs are
  correlated; references are agent-authored and pending human review. No
  ranking, held-out generalization claim beyond these 18 observed cases, live
  MCP or product qualification.
