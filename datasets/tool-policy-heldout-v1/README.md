# Local tool-policy held-out pack v1

**24 TEST cases, twelve FR/EN families, zero TRAIN or calibration cases.**
Frozen on 30 October 2026 before any candidate prediction, as the held-out
complement of the [ten-case TRAIN canary](../tool-policy-canary-v1/README.md)
for the shared discovery, argument-execution and episode contracts. References
and translations are agent-authored, pending human review.

At freeze: **zero real-model cases, zero scored model cases and zero human
judgments**. The [manifest](manifest.json) records the case hash, every family,
the literal references, the contract outcomes covered and the diagnostic ideal
trajectory counts. The TRAIN canary, its references and its archived result
are unchanged by this pack.

| Family | Cases | Task | Independent reference |
|---|---:|---|---|
| `th101` | 2 | Rows of a known dataset are absent; return a column total. | Select `fetch_rows` **and** `sum_column`; neither alone suffices. |
| `th102` | 2 | Remove fully identical rows from a supplied table. | Either `dedupe_rows` or `distinct_rows` alone; the union is not required. |
| `th103` | 2 | Convert prices into an unnamed target currency. | `clarify / missing_information`, no tools. |
| `th104` | 2 | Produce a PDF of a supplied table; the only eligible PDF tool is unavailable. | `no_suitable / unavailable`, no tools; the ineligible PDF service must not be proposed. |
| `th105` | 2 | Propose sum arguments after an actual lookup (`length`, m). | `7 + 15 + 22 + 31 = 75 m` bound to the actual artifact ID, column, unit and scope. |
| `th106` | 2 | Propose sum arguments after an actual lookup (`price`, USD). | `3 + 8 + 16 + 5 = 32 USD`. |
| `th107` | 2 | Normal lookup/sum episode. | `9 + 17 + 6 + 20 = 52 kg`, success only after the real sum receipt. |
| `th108` | 2 | One controlled transient lookup error, then success. | One retry; `13 + 2 + 27 = 42 EUR`. |
| `th109` | 2 | Both permitted lookups fail. | `stop / persistent_error`, null value and unit. |
| `th110` | 2 | Lookup returns a complete but empty table. | `stop / no_data`, null value and unit. |
| `th111` | 2 | Lookup returns an explicitly partial artifact. | `clarify / partial_data`, null value and unit. |
| `th112` | 2 | Sum becomes unavailable after a successful lookup. | `stop / unavailable`, null value and unit. |

The `ledger` catalogue, tables, scope/document identifiers, requests and
translations are entirely synthetic and new; none appears in the TRAIN canary.
Catalogue tools are advertised selection options, not live services. Only the
guarded Python `fixture.lookup` and `fixture.sum` functions execute in the
argument and episode paths. There is no Deposium tenant, private document,
production metadata, web request or live MCP operation in the cases.

## Held-out with respect to what

Every family, translation pair and source document is TEST, and the local
candidate has never seen these identities. The operation motifs (fetch then
sum, deduplication, conversion, export, lookup/sum episodes) belong to the same
three contracts as the TRAIN fixtures. This pack is therefore held-out with
respect to candidate exposure and prompt revision; it is not a new reasoning
domain and does not establish open-ended tool competence.

Covered outcomes: discovery `select` (two-tool route; two equivalent minimal
alternatives), `clarify/missing_information`, `no_suitable/unavailable`;
episodes `complete` (normal; one transient retry), `persistent_error`,
`no_data`, `partial_data`, `unavailable`. Not covered here:
`no_suitable/no_capability`; the `missing_information` episode stays in TRAIN.

## Projection, references and accounting

The candidate receives only the task-specific whitelist: request and catalogue
for discovery, the actual lookup observation for arguments, and the current
interfaces, remaining budgets and actual observations for an episode. Gold
assertions, rationales, family/split/document labels, fault schedules and
unexposed table values never reach the model.

Literal totals were authored before predictions and are not derived from any
candidate or runtime output. Discovery alternatives are minimal sufficient sets
over eligible, available tool IDs; a strict superset fails minimal-set success.
Episodes use `deposium.tool-episode-input/v2` (five decisions, three tool
calls, two lookup attempts, 60,000 ms including model time). A fully correct
ideal trajectory would use 44 generations and 28 actual tool calls (22 `ok`,
six controlled errors) with four numeric task successes; these are diagnostics,
not gold paths. Case caps permit at most 72 generations (five per episode even
after a call or retry limit is exhausted, one per discovery or argument case)
and 44 executed tool calls.

Report discovery, arguments and episodes separately with their eligible
denominators: 24 cases; select-reference discovery metrics over the 4 `select`
cases of 8 (`th101`, `th102`), with decision correctness over all 8; four
success-eligible episodes of twelve; FR and EN apart. A correct clarification
or stop is procedure handling, not task success. No accuracy threshold selects
or drops cases, and no exposed error is repaired by changing this version.

## Validation and execution

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-policy-heldout-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_policy_heldout.py' -v
```

A real attempt follows the dated
[held-out protocol](../../docs/LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md):
TRAIN re-run with prompt v2 first, then this pack, each in a new archive bound
to its frozen manifest. One model on 24 correlated cases is not a ranking.
