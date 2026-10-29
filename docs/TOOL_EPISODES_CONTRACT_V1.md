# Bounded actual-feedback episode contract v1

This is the initial controlled implementation of
[#12](https://github.com/theseedship/classification_tests_deposium/issues/12).
It reuses the synthetic lookup/sum tools and shared case, adapter, campaign,
scorer and sealed-archive path from the
[argument fixture](TOOL_ARGUMENTS_CONTRACT_V1.md). It adds an actual feedback
loop, independent resource bounds and verified stopping. It does not qualify
live services, product behavior or adaptation by a real model.

The [dataset](../datasets/tool-episodes-v1/README.md) has seven synthetic
FR/EN families, 14 training cases and no held-out cases. Scripted control
policies receive actual observations; their reasoning is not assessed as a
candidate model result. All references remain agent-authored pending review.

## Source fixture and hidden configuration

`bench.tool-episode` uses the generic `deposium.case/v1` envelope and the
existing `PRODUCT` grouping. The native task remains outside the application
component registry. Its source input has exactly:

| Field | Meaning |
|---|---|
| `schema_version` | `deposium.tool-episode-input/v1` |
| `request` | A bounded neutral task and its conditional rules, in FR or EN |
| `scope_id` | Independently permitted synthetic scope |
| `dataset` | Synthetic ID, column, unit and bounded integer values; empty values are permitted for this episode task |
| `known_dataset_id` | The supplied ID, or `null` when clarification is required |
| `faults.lookup_events` | Internal finite sequence of `ok`, `transient_error` or `partial` responses |
| `faults.disable_sum_after_lookup` | Internal availability change after lookup |
| `budgets` | Independent step, call-attempt, lookup-attempt and elapsed-time limits |

The initial budgets are `max_steps: 5`, `max_tool_calls: 3`,
`max_lookup_attempts: 2` and `max_elapsed_ms: 1000`. These are bounded fixture
settings, not universal budgets for future model inference. Empty-data support
does not relax the earlier argument task's nonempty input contract.

No field is interpreted as a filesystem path, shell command, network URL or
arbitrary executable handle. Source scope/availability facts remain outside
candidate authority. A guessed dataset or artifact ID cannot override them.

## Candidate-visible projection

Every policy decision receives a fresh projection containing the request,
permitted scope, supplied parameters, tool schemas/current eligibility,
actual observation history and remaining budgets. The source table values
are delivered only through actual lookup observations. The source fault
schedule, reference answers, rationale, split labels and family identity are
never part of this projection.

The archive retains each exact projected input and its hash. A failed lookup
really returns an error receipt; a subsequent policy input contains that
receipt. A successful retry returns its actual artifact. Partial lookup
creates a partial-data artifact with its own content ID and an explicit
incompleteness marker. Empty data stays visibly empty. A tool-state update
can make summation unavailable after a successful lookup.

The policy transport is initially a replay of fixed actions. It still receives
each actual projection through the step interface, but that does not prove it
uses the observation intelligently. A future model adapter must qualify that
same input/output boundary separately and exclude descriptive transport IDs.

## Allowed candidate actions

A tool action contains exactly the call type, permitted tool ID and arguments:

```json
{
  "action": "call",
  "tool_id": "fixture.lookup",
  "arguments": {
    "dataset_id": "episode-table-001",
    "scope_id": "episode-scope-001"
  }
}
```

The only tool IDs are `fixture.lookup` and `fixture.sum`. Summation uses the
argument schema already established by the argument fixture: actual
`artifact_id`, column, unit and permitted scope. The control stores the full
literal content ID. The harness does not replace symbolic placeholders on
behalf of the candidate.

A finish action contains exactly:

```json
{
  "action": "finish",
  "decision": "success",
  "reason": "complete",
  "value": 60,
  "unit": "EUR"
}
```

Allowed semantic combinations are:

| Decision | Reason | Claimed value/unit |
|---|---|---|
| `success` | `complete` | Must match an actual successful full-data sum receipt |
| `stop` | `persistent_error`, `no_data` or `unavailable` | `null` / `null` |
| `clarify` | `partial_data` or `missing_information` | `null` / `null` |

Unknown fields/actions/tools, malformed arguments, stale or foreign bindings,
wrong units or scopes, and candidate-supplied execution/guard records fail.
A finish claim without its required actual observations cannot certify the
outcome. In particular, guessing 60 EUR before summation is premature success.

## Actual operations and independent budgets

The fixture backend executes bounded local lookup/sum logic. Transient error
events are actual error returns; they are not cached expected observations.
Successful lookup returns a case-local content-addressed artifact. Summation
is independently blocked until a complete, nonempty, currently available
artifact exists and its arguments match the store and permitted scope.

Policy decisions, attempted calls, actual executions and lookup attempts are
distinct counters. A refused call does not become an execution. All limits
are enforced outside the policy, including a monotonic elapsed-time deadline.
Elapsed time is checked before and after synchronous policy/tool invocations;
this control does not hard-preempt an in-flight model or service call.
Budget exhaustion prevents further execution and cannot establish task success.
An invalid call leaves the procedure invalid even if a later response attempts
to claim a result. Tests use a controlled clock to exercise deadline refusal;
ordinary execution does not sleep or contact external services.

The seven positive scripts have different routes: success, one transient
retry, persistent failure, empty data, partial data, missing information and
tool unavailability after lookup. The exact script uses 34 decisions and 20
actual calls across 14 cases, with 14 `ok` and six error receipts. These are
observed-control expectations only. A different valid within-budget route can
pass while retaining its different cost; exact control counts are not gold.

## Reference outcomes and separate metrics

Every reference requires eight exact assertions:

| Path | Required value |
|---|---|
| `/checks/budgets_respected` | `true` |
| `/checks/stopping_valid` | `true` |
| `/checks/procedure_valid` | `true` |
| `/checks/task_success` | `true` only in normal/retry success families; otherwise `false` |
| `/outcome/decision` | The case's `success`, `stop` or `clarify` |
| `/outcome/reason` | The declared semantic reason |
| `/outcome/value` | Independently authored 60 for successful results; otherwise `null` |
| `/outcome/unit` | EUR for successful results; otherwise `null` |

The generic exact scorer applies these assertions after task-specific receipt
and state-transition consistency checks. It does not run the tools again.
References do not require one exact action order or usage count when another
legal trajectory satisfies the task, stopping rules and budgets.

Procedure/outcome agreement and actual task success remain separate. The
valid scripts may match all 14 case references, while four cases achieve a
numeric task result. The other ten cases handle a limitation correctly but do
not become successful RAG answers. Report both **4/14 all cases** and
**4/4 success-eligible cases**, with their meanings.

Selection/arguments/execution have a planned 12-case population excluding
the missing-input family. Binding/result have a four-case success-eligible
population. Stopping and budgets concern all 14. Metrics retain unsuccessful
and missing outcomes in the eligible denominators; inapplicable metrics stay
explicitly undefined instead of becoming a perfect score. Validated trace
counts and actual tool-status totals remain separate from absent/inconsistent
trace evidence. Zero observed operations do not imply zero scored decisions,
and zero scored cases cannot establish a pass.

The harness also records `tool_valid`, `arguments_valid`, `binding_valid` and
`execution_valid` checks alongside `procedure_valid`, `budgets_respected`,
`stopping_valid` and `task_success`. Stage populations are separate: tool and
arguments each have 12 eligible cases, binding four, execution 12, result four,
and stopping and budgets 14 each. These diagnostic checks do not replace the
eight mandatory final-outcome assertions or make an absent result successful.

## Control profile, archive and rescore

Only the `fixture_episode` adapter with `qualification=harness_control`,
`model=null` and `revision=null` is initially admitted. Recordings use the
existing envelope, with `output: {"actions": [...]}` for each opaque case ID.
They contain policy actions only, never observations or success receipts.
Normal recorded/model/application profiles cannot manufacture this execution
capability by changing their declared contract.

The wrapper constructs `deposium.tool-episode-output/v1` from actual policy
inputs, actions, guards, tool receipts, final outcome and usage. Runtime/source
fingerprints identify the executed implementation. Original traces and seals
remain in the ordinary campaign archive; public aggregates are separate.

A derived rescore validates retained transitions and receipts without calling
tools, invoking a policy, reading live services or starting a new episode.
Tampering with proposals, observations, hashes, counters or outcomes fails
archive/task checks. A seal establishes retained-byte integrity, not external
authentication or proof that synthetic behavior transfers to production.

## Reproduction

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-episodes-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_episodes.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-episodes-v1/cases.jsonl \
  --profile profiles/tool-episodes-control.json \
  --output results/tool-episodes-control-001
```

Use Python 3.11+ and a fresh output directory. The expected initial control
qualification is harness-only, with 14 correctly handled scenarios and four
successful task results. Optional schema tests skipped for a missing dependency
remain unqualified. No existing references, historical scores or raw archives
are rewritten. New model campaigns need a supported output adapter, pinned
runtime, fresh evaluation plan and explicit resource/cost budgets.
