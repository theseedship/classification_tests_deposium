# Tool discovery and selection contract v1

This is the initial catalogue-selection slice for
[#10](https://github.com/theseedship/classification_tests_deposium/issues/10).
It extends the shared engine with `bench.tool-discovery`, a constrained typed
selection task, and a [12-case synthetic FR/EN pack](../datasets/tool-discovery-v1/README.md).
It does not execute tools, generate arbitrary argument values or qualify an
application integration. All references remain agent-authored pending review.

## Allowed candidate input

The versioned input object contains exactly:

| Field | Meaning |
|---|---|
| `schema_version` | `deposium.tool-discovery-input/v1` |
| `request` | The synthetic task facts and request, without gold annotations |
| `catalogue` | Up to 32 cards with unique tool IDs |
| `shortlist_limit` | Positive integer, at most eight; the initial pack fixes it at four |

Each card contains exactly `plugin_id`, `capability_id`, `tool_id`,
`description`, `eligible` and `available`. Text is bounded; IDs in the three
namespaces remain distinct. A capability maps to one plugin. Multiple tools
may advertise the same capability, as the two equivalent filter interfaces do.
The initial pack supplies 12 cards in the question's language, with stable
identifiers and flags across translations.

Eligibility and availability are deterministic fixture inputs, independent of
candidate predictions. The candidate proposes IDs only; it cannot grant access,
widen scope or reactivate an unavailable tool. These synthetic flags are not
evidence of real service state or production authorization. Catalogue entries
contain no executable handles, application source paths or credentials.

The shared case envelope keeps `reference`, rationale, split, scenario and
translation-family metadata outside `input`. A recorded control also receives
transport `case_id` and `contract_id` for dispatch. A future model adapter must
audit its actual projection separately and exclude descriptive case identities;
the presence of a transport envelope does not make it a safe native prompt.

## Candidate output and independent reference

The output contains exactly `schema_version`, `shortlist` and `selection`:

```json
{
  "schema_version": "deposium.tool-discovery-output/v1",
  "shortlist": ["tool.tables.describe_columns", "tool.tables.count_rows"],
  "selection": {
    "decision": "select",
    "tool_ids": ["tool.tables.count_rows"],
    "reason": "ready"
  }
}
```

`shortlist` is a bounded unique list at **tool** level. `selection.tool_ids` is
an unordered unique subset of it. A plugin or capability ID is not a tool ID.
Unknown, ineligible or unavailable IDs invalidate either list. Empty `select`
sets and excess shortlist length fail rather than establishing a decision.

The allowed semantic outcome combinations are:

| Decision | Reason | Final tools |
|---|---|---|
| `select` | `ready` | A nonempty proposed set |
| `clarify` | `missing_information` | Empty |
| `no_suitable` | `no_capability` or `unavailable` | Empty |

An explicit correct nonselection outcome is not a runtime failure. It may have
an empty shortlist and still give a substantive decision. Technical `abstain`,
`unsupported`, `missing`, `error` and `timeout` retain their existing meanings
and do not substitute for a correct semantic outcome.

References use the existing case envelope and exactly one assertion:
`path=/selection`, `op=one_of`, with complete alternative selection objects.
No reference shortlist is supplied. The task scorer compares final tool IDs
as sets; array order cannot change correctness. Alternative gold sets must be
known, eligible, available, nonempty for select, and minimal: duplicate sets
or a strict superset of another valid route are refused as malformed references.
All alternatives for a case share a coherent outcome/reason.

## What the metrics measure

The existing `score_case`, `summarize`, CLI and sealed campaign archive are the
evaluation path. The task module supplies a scorer hook; it is not a second
runner or a notebook-only implementation. Legacy tasks keep their existing
typed exact rules. The new task adds separately versioned task metrics.

For a select reference, compare each candidate set with a reviewed sufficient
alternative. Choose the alternative with maximum recall, then maximum precision,
then lexicographic order of its sorted tool IDs. **Do not use the union of all
valid alternatives as a target**: one fully valid filter interface must obtain
full recall without requiring the other interface too.

| Metric | Interpretation |
|---|---|
| Shortlist recall | Fraction of a sufficient route's required tools present in the shortlist |
| Shortlist precision | Fraction of shortlisted IDs belonging to that matched route |
| Final recall/precision | The corresponding overlap for the proposed final tool set |
| Final sufficiency | The final set contains at least one complete allowed route |
| Final minimal-set correctness | The final set equals one allowed route, without unnecessary tools |
| Unnecessary tools | Proposed final tools outside the matched sufficient route |

These overlap metrics use **tool IDs**, not plugin-level or capability-level
recall. The shortlist's order does not imply a score-ranked list or nDCG. A
declared limit is a maximum size, not a requirement to fill every slot. Precision
is route-relative: another legitimate alternative in the shortlist can still
be additional to the matched minimal route. Interpret recall, precision, final
selection and resource limits together rather than as one pooled accuracy.

A final superset can be sufficient while failing minimal-set correctness and
the case verdict. A shortlist may retain eligible distractors within its limit;
that lowers precision but need not invalidate a correct minimal final selection.
Selecting every catalogue tool cannot establish success. The case must match
the semantic decision/reason and an exact minimal allowed final set.

Task summaries publish their eligible and observed counts. Missing, technically
unsuccessful and malformed outputs contribute zero to means over eligible select
cases; they are not dropped to improve a metric. A well-formed but wrong output
retains its measured overlap, while its final decision or minimal-set check can
still fail. `observed_select_cases` counts structurally valid outputs on select
references, including a wrong semantic nonselection; it does not count only
outputs whose candidate decision was `select`. Metrics based on sufficient sets are `null`
for nonselection gold, with separate decision correctness still scored. A group
with no eligible select case has undefined select metrics, not accuracy one.
Unnecessary-tool aggregates state their observed denominator so an error is not
misrepresented as an observed zero-extra selection. Language and split groups
remain separate. Technical status counts and ordinary all-case success retain
their shared denominators.

## Scenarios, controls and actual runtime boundary

The frozen pack contains six new scenario families, each with FR/EN variants,
two families per train/calibration/test split. It covers one tool, a necessary
lookup-plus-sum tool set, valid alternative filters, absent capability, missing
location information and an advertised but unavailable route solver. Shared
catalogue cards and operation patterns limit independence across splits.
Each split has one select family and one nonselection family, so the assigned
test split includes both positive selection and a no-suitable outcome.
Lookup-to-sum also occurs in the earlier #9 training fixture; this pack keeps
that related operation in train and does not claim a new held-out reasoning type.

The [recorded profile](../profiles/tool-discovery-control.json) supplies twelve
scripted positive outputs. Some shortlists contain distractors; the pair's final
IDs use different array orders; the filter cases choose different valid tools.
Case success is expected without asserting perfect shortlist precision.
Negative controls exercise wrong or insufficient sets, supersets, empty output,
unknown and wrong-level IDs, duplicates, forbidden/unavailable tools and budget
overflow. These are implementation checks, never model results.

Both profile runtime validation and the candidate schema restrict the new
capability to `recorded` / `harness_control`. Current native D3/Clef, GLiClass,
hosted decision APIs and legacy local choice adapters do not gain structured
selection support by editing a capability string. A future real campaign must
qualify the actual input/output path and pin its model, runtime, settings,
resource bounds and dataset/scorer versions before inference.

## Reproduce the offline fixture

Python 3.11+ and the standard library suffice:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-discovery-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_discovery.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-discovery-v1/cases.jsonl \
  --profile profiles/tool-discovery-control.json \
  --output results/tool-discovery-control-001
```

The replay requires a fresh output directory and produces the normal archived
raw outputs, task metrics and report. It invokes no model, paid API, live tool
or application service. The new scorer source changes source fingerprints;
retain original archives and use a new derived rescore when explicitly needed.
Rescoring creates neither fresh inference nor timing measurements.

## Boundary with later tasks

- [#11](https://github.com/theseedship/classification_tests_deposium/issues/11)
  adds actual argument values, units, deterministic permitted scope and bindings
  to real prior synthetic tool responses. This task selects identifiers only.
- [#12](https://github.com/theseedship/classification_tests_deposium/issues/12)
  executes bounded synthetic tools and feeds actual observations back through
  an episode. Static set sufficiency does not test order, retries or completion.

No existing choice references or model scores are rewritten. Agent-authored
references and translations remain qualified as such; optional human review
does not block the current offline checks or exploratory model comparisons.
