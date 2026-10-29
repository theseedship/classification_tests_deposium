# Bounded tool-feedback episodes v1

**14 synthetic FR/EN training cases in seven families.** This is the initial
offline feedback-loop slice for
[#12](https://github.com/theseedship/classification_tests_deposium/issues/12).
The shared campaign path executes bounded local fixture tools and gives each
actual observation to the next policy step. The policy controls are scripted;
no real model or production MCP integration is qualified by these runs.

The [versioned contract](../../docs/TOOL_EPISODES_CONTRACT_V1.md) specifies
allowed input projections, action/finish schemas, independent budgets,
reference outcomes, trace checks and metric denominators. References and
translations are agent-authored pending human review. No expert form is
required to run the automatic controls.

## Scenario coverage

Each family has one French and one English case. The following counts describe
the supplied **scripted controls**, not every valid trajectory:

| Family | Actual observations and expected final handling | Policy steps | Tool executions | Task success |
|---|---|---:|---:|---|
| `tool-episode-family-001` | Full lookup, actual sum, success: 60 EUR | 3 | 2 | Yes |
| `tool-episode-family-002` | Transient lookup error, one retry, actual sum, success: 60 EUR | 4 | 3 | Yes |
| `tool-episode-family-003` | Two lookup errors, then stop with `persistent_error` | 3 | 2 | No |
| `tool-episode-family-004` | Empty lookup, then stop with `no_data` | 2 | 1 | No |
| `tool-episode-family-005` | Partial lookup, then clarify with `partial_data` | 2 | 1 | No |
| `tool-episode-family-006` | Missing supplied dataset ID, clarify without calling a tool | 1 | 0 | No |
| `tool-episode-family-007` | Lookup succeeds but the sum tool becomes unavailable; stop | 2 | 1 | No |

The two success families have independently authored arithmetic
`10 + 15 + 35 = 60 EUR`. In the other families, a numeric answer is not
justified under the task's explicit policy. The empty-source case does not
ask for the mathematical sum of a known empty collection: the request requires
complete, nonempty source data and prohibits inventing a zero result.

The controls therefore expect **14/14 correct procedure/outcome decisions**
but only **4/14 successful task results**, or **4/4 success-eligible cases**.
Correct failure handling is not renamed task success. The recorded positive
trajectories total 34 policy decisions and 20 actual tool executions: 14 `ok`
receipts and six controlled error receipts. Zero tool calls in the missing-ID
family still accompany a substantive scored clarification decision.

## Splits and provenance

There are **14 train, zero calibration and zero test cases**. Family
translations and synthetic table/document identities stay together. All seven
families share the lookup-to-sum operation pattern used by earlier training
fixtures; this is not fresh held-out evaluation or evidence of broad
generalization. The shared neutral request states every conditional rule in
both languages. Scenario names and fault schedules are not revealed to the
candidate policy.

Tables, IDs, scope strings and fault schedules are entirely synthetic. No
private documents, conversations, user/tenant metadata, application source
inventory or live operational snapshot was copied into this pack. The
[manifest](manifest.json) pins case and control bytes, family identities,
reference provenance and expected scripted-control usage. That usage is
diagnostic metadata, not a required exact sequence in the gold assertions.

## Actual feedback and independent bounds

`fixture.lookup` and `fixture.sum` execute local Python logic over bounded
tables and case-local artifacts. Controlled lookup errors, empty/partial
views and availability changes come from the fixture backend, not recordings
of expected observations. Every policy step receives the actual observation
history, current permitted tool state and remaining budgets through a
whitelisted projection. Source fault schedules, references, rationale, splits
and family labels remain outside that projection.

The fixed limits are five policy decisions, three tool-call attempts, two
lookup attempts and a 1,000 ms elapsed-time budget per case. The harness
enforces them independently of the policy. Attempts and actual executions are
separate counters; a refused call cannot be counted as a successful operation.
Sum requires an earlier, complete, nonempty and currently eligible artifact
with the correct unit, column and scope. Literal content IDs in the sum
controls must match what the actual lookup returned.

The policy recordings contain action lists only. They do not contain cached
tool observations, execution receipts, guard flags or success certifications.
A fixed script can receive real feedback while still failing to reason about
it; these controls test the loop's delivery and checking, not model adaptation.

## References and metrics

Eight mandatory assertions check valid procedure, stopping, budgets, whether
task success was achieved, and the final decision/reason/value/unit. A finish
claim alone cannot establish success: a matching actual full-data sum receipt
must exist. Premature success, invalid bindings, denied calls or exhausted
budgets cannot establish a successful task result.

Separate metrics retain selection, argument, dependency, result, stopping and
budget denominators, with technical failures and missing predictions kept.
Binding/result populations concern the four success-eligible cases; stopping
and budget assessment concern all 14. Inapplicable populations are explicit,
not silently scored as perfect. Exact counts or action order from one valid
control are not universal grading references: a further permitted lookup can
remain valid within budget, with its additional cost visible in the trace.

## Validate and execute the controls

Use Python 3.11+ from the repository root, without model assets or services:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-episodes-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_episodes.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-episodes-v1/cases.jsonl \
  --profile profiles/tool-episodes-control.json \
  --output results/tool-episodes-control-001
```

Use a new archive directory. Validation should report 14 valid training cases
without execution. The explicit `fixture_episode` control executes the bounded
synthetic tools and reports `qualification=harness_control`, with actual
per-step inputs, proposals, observations, usage and scores retained. It calls
no model, paid API, live network tool or application service.

The normal sealed archive preserves source/profile hashes and raw traces.
A derived rescore verifies retained state transitions and receipts without
executing tools, calling a policy or starting a new episode. It preserves the
original archive and creates no new inference or execution observation.
