# Tool discovery and sufficient selection v1

**12 synthetic cases in six FR/EN families.** This pack is the initial offline
contribution for [issue #10](https://github.com/theseedship/classification_tests_deposium/issues/10).
It asks for a shortlist and a final tool set from a supplied catalogue, rather
than choosing one of four authored proposals. References and translations are
agent-authored and pending human review. No expert forms are required to run
the automatic checks or later exploratory comparisons.

The current candidate is a **recorded harness control only**. No model has
been qualified or evaluated on this contract; no tool is executed. See the
[contract and metric definitions](../../docs/TOOL_DISCOVERY_CONTRACT_V1.md).

## Coverage and family splits

| Family | Cases | Split | Reference outcome |
|---|---:|---|---|
| Row count of an already supplied table | 2 | calibration | One counting tool |
| Retrieve missing values, then sum them | 2 | train | Lookup and summation tool set |
| Equivalent row-filter interfaces | 2 | test | Either reviewed singleton alternative |
| Audio transcription and speaker turns absent from catalogue | 2 | train | `no_suitable / no_capability` |
| Location omitted for a flood-risk query | 2 | calibration | `clarify / missing_information` |
| Routing tool advertised but unavailable | 2 | test | `no_suitable / unavailable` |

There are **four cases per split**, six French and six English cases. Each
family's translation pair, synthetic fixture ID and reference alternatives
stay in one split. The six select cases and six nonselection cases remain
separate metric populations. Every split has one select family and one
nonselection family: two cases in each population. A semantic clarification or no-suitable outcome
is a substantive answer; it is not a technical `abstain` or `unsupported` result.

The shared catalogue and simple operation patterns are reused across splits.
Six families do not establish broad generalization or fresh unseen structural
coverage. The test labels are an assigned split, not evidence that any model
or expert reviewed them. No candidate predictions informed their construction.
The lookup-to-sum pattern also appears in the earlier #9 training fixture;
its #10 counterpart stays in train and is not a new independent reasoning type.
Existing choice packs, references and historical results are unchanged.

## Frozen synthetic catalogue

[catalogue.json](catalogue.json) defines 12 bilingual cards. Each input receives
one language's descriptions with the same identifiers and flags. The cards
cover table operations, a flood-layer lookup, graph routing, local passage
search, frozen web search and image resizing, plus a deliberately ineligible
table lookup. They describe synthetic interfaces, not installed Deposium
plugins, actual MCP tools or an observed service inventory.

Each card distinguishes `plugin_id`, `capability_id` and `tool_id`. Both filter
interfaces belong to one capability in one plugin; the output must name tools,
not plugin or capability IDs. `eligible` and `available` are fixed fixture
inputs. A candidate cannot change them or gain access by naming an identifier.
Unavailable or ineligible tools are invalid in either candidate list.

The [manifest](manifest.json) pins the case and catalogue byte hashes, counts,
family splits, provenance and review status. The bilingual catalogue is a
source definition; actual candidate inputs contain flat description strings.
No private documents, conversations, personal metadata, application source
inventory or live operational snapshot was copied into this pack.

## Inputs, references and outputs

The contract is `bench.tool-discovery` in the existing `deposium.case/v1`
envelope. Pack `PRODUCT` is an existing grouping key, not a product-quality
claim. The allowed input is the versioned request, catalogue and shortlist
limit. References, rationales, family/split labels and case identities are
excluded from task content. The recorded transport uses a case ID to dispatch
its fixed response; any future model adapter must separately qualify its
input projection and must not send descriptive case IDs to a model.

The structured output contains a tool-level shortlist of at most **four**
unique IDs and a final `selection` with decision, tool IDs and reason. The
final set is an unordered subset of the shortlist. For a select outcome it
must be one complete reviewed minimal sufficient set. Arguments, call order,
actual artifact bindings, tool returns and workflow completion are not scored.
Those are later tasks in #11 and #12.

Each reference uses exactly one `/selection` `one_of` assertion over complete
alternative decisions. It does not prescribe the shortlist. The two filters
are valid alternative routes: a candidate need not select or shortlist both.
An empty raw response or an empty `select` cannot pass. Correct explicit
nonselection outcomes have empty tool sets and may have an empty shortlist.

## Metrics and controls

The shared engine reports ordinary case success/coverage and keeps task metrics
separate: shortlist recall/precision at tool level and the declared limit,
final sufficiency, exact minimal-set correctness, and unnecessary tool count.
Alternative matching maximizes recall, then precision, then sorted-ID order;
it does not demand the union of all valid routes. Precision is relative to
that chosen sufficient route, not to every potentially useful catalogue card.

A sufficient superset can receive sufficiency credit, while failing minimal-set
success and retaining its extra-tool count. Selecting everything cannot win.
Permitted shortlist distractors can lower shortlist precision without making
a correct minimal final selection fail. Missing and failed outputs remain in
the eligible denominators. Invalid or missing outputs contribute zero to
means over eligible cases; a well-formed wrong selection retains its measured
overlap while failing the case verdict. Select metrics are `null` when no select reference
is eligible; this never becomes a fabricated perfect score for empty gold.

The positive control intentionally includes some shortlist distractors and a
reversed final pair. It covers both valid filter alternatives across languages.
It should pass all **12 case decisions**, while its shortlist precision is
below one. This is scripted scorer evidence, not perfect model performance.

## Validate and run the offline control

Use Python 3.11+ from the repository root, without weights or services:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-discovery-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_discovery.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-discovery-v1/cases.jsonl \
  --profile profiles/tool-discovery-control.json \
  --output results/tool-discovery-control-001
```

Choose a new output directory. Validation should report 12 valid cases without
inference. The explicit recorded replay should report `harness_control` and
12/12 successful case decisions, with separate task metrics in the shared
summary/report and original raw responses retained. A genuine campaign needs
a newly qualified output adapter, pinned model/runtime, plan and budget.

The new scorer source enters campaign fingerprints. Preserve old archives;
an explicit derived rescore creates neither inference nor a new timing result.
