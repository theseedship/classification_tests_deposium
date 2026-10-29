# Capability and workflow choices v1

**192 synthetic closed-choice cases, 48 scenario families, FR/EN.** This
complementary pack evaluates capability and tool-set proposals, arguments and
dependencies, clarification, and next-step choices after fixed observations.
References are agent-authored and pending human review. The first
[D3 Flash Q8/Metal campaign](../../docs/CAPABILITY_FLASH_RESULTS_20261029.md)
reached **192/192, including 96/96 test cases**, on 29 October 2026.
**Zero cases are semantically qualified; no application or tool execution is tested.**

The perfect score is a ceiling on these four-proposal synthetic choices, not
evidence of general tool discovery or executable workflows. The dated report
keeps the fresh 132-case context anchor and 12-case technical canary separate.

The cases reflect generic document/RAG, geospatial, web and open-data workflows
useful in the Deposium context. They contain no private application inventory,
production conversation, document, tenant, user or operational snapshot. The
32 capability cards describe synthetic operations, not installed MCP tools or
a claim that a service is active. A synthetic path capability does not qualify
any application's graph implementation.

## Coverage

| Track | Families | Cases | Examples |
|---|---:|---:|---|
| Capability selection | 16 | 64 | Single capability, minimal tool sets, local versus external sources, geospatial and cross-source plans |
| Arguments and dependencies | 16 | 64 | Resource/format/year, CRS and units, geometry validity, key types, artifact bindings, missing arguments and scope |
| Next step after observations | 16 | 64 | Empty/partial results, retry and call budgets, unavailable tools, untrusted returned text, clarification and stopping |

Every family has four correlated variants: FR/EN × an **8-card compact** or
**32-card expanded** catalogue. Relevant card descriptions and proposal meanings
stay fixed; the expanded view adds distractors. Both views use the same reviewed
proposal reference. References have undergone an independent agent pass, which
is **not human approval** or proof of application correctness.

The family split is fixed before inference: **12 train / 12 calibration / 24
test families**, or **48 / 48 / 96 cases**. All translations, catalogue variants
and the scenario's synthetic document ID stay together. Answer positions are
balanced within split, language and catalogue variant. Shared capability cards
are reusable definitions, not independent held-out source documents. Similar
operations across families limit statistical independence.

## What a candidate receives and what the score means

The pack uses the existing `bench.context-choice` contract and
`deposium.case/v2` schema. The shared adapter projection exposes only the
catalogue and explicit scenario facts, the question, and four proposal
descriptions. The output is an opaque `choice_id`; references, explanations,
semantic answer keys, difficulty tags, family IDs and splits stay outside the
native model row. No new inference backend or notebook pipeline is needed.

The exact scorer measures agreement with the frozen authored choice. It rejects
empty, wrong, absent or malformed decisions; technical `abstain` is distinct
from choosing a semantic clarification/stop option. Failures remain in the total
denominator with their original `missing`, `unsupported`, `error` or `timeout`
status. Scored coverage and correct/all must accompany every result.

A correct proposal **does not establish** open-set discovery recall, free-form
tool generation, valid executable arguments, geometric computation, retrieved
evidence quality or end-to-end task success. Arguments and artifact dependencies
are described in choices rather than executed. Next-step cases expose a fixed
observation; they do not feed successive candidate calls back through a live
loop. Those are separate future harness tasks in the
[routing experiment](../../docs/INTENT_AND_MODEL_ROUTING.md).

D1/D2/D3 are authored context strata. They are not an empirical difficulty
reference or proof that a larger model helps. Permissions, activation, scope,
consent and budgets are deterministic constraints; no choice grants access.

## Validate without inference

Use Python 3.11+ from the repository root:

```bash
python3 -m deposium_bench.capability_corpus --check
python3 -m deposium_bench validate-cases \
  --dataset datasets/capability-choice-v1/cases.jsonl
python3 -m unittest discover -s tests -p test_capability_corpus.py -v
```

`catalogue.json` and the three `specs-*.json` files are the versioned source
definitions. The generator reproduces the JSONL and manifest exactly and never
overwrites an existing export. Validation checks canonical identities, content,
references, family splits and hashes. It is not a semantic or human review.
Change a reference only with an explanation, review and a new dataset version;
do not regenerate it to improve candidate scores.

The frozen `manifest.json` records the dataset's generation-time `not_run`
state and zero scored cases. Campaign executions belong in separate dated
reports and archives; their results do not rewrite that manifest or its sources.

## Run another complementary campaign

Prepare one existing pinned context-choice candidate and its assets/runtime
first. For supervised native execution, use the
[frozen Flash protocol](../../docs/CAPABILITY_NATIVE_PROTOCOL_20261029.md) and
the native pilot's explicit `--dataset` option. For another prepared CPU profile:

```bash
python3 -m deposium_bench run \
  --dataset datasets/capability-choice-v1/cases.jsonl \
  --profile profiles/d3-flash-cpu-context.json \
  --output results/capability-d3-flash-001
python3 -m deposium_bench analyze-context \
  --archive results/capability-d3-flash-001 \
  --output results/capability-d3-flash-001-analysis
```

These are explicit inference commands for a new archive; dataset validation never runs
them. The larger catalogue may exceed a candidate's native input limit.
Preserve its unsupported/overflow outcome; do not silently truncate cards or
increase a frozen profile's limits to make it appear compatible. Record actual
input lengths, model/runtime revisions, precision, initialization, latency and
resource scope. A valid but incorrect prediction can make `run` return code 1;
inspect completeness and coverage rather than discarding the archive.

The existing notebook uses the same engine: set its `dataset_path` parameter
to `datasets/capability-choice-v1/cases.jsonl` and `profile_path` to the prepared
context-choice profile. No separate notebook implementation is needed.

Keep a complementary campaign separate from the historical 132-case pack.
For a global series, run both packs per candidate with new archives and report
each dataset/track, test split, language and catalogue view separately. The
analysis retains `benchmark_pack`, `task_type`, `use_case` and
`catalogue_variant` breakdowns. Do not append the new cases to old archives,
reinterpret historical scores as measurements of these tasks, or merge unlike
scores into an unexplained leaderboard total.

The component links in annotations reference the dated public contract registry
only. Connecting the real application requires inventory synchronization and a
pinned real harness; this pack does not replace the application router.
