# Deposium RAG Decision Bench

An exploratory benchmark for **decisions and evidence inside
retrieval-augmented generation (RAG)**: understanding a request, proposing tools,
ranking retrieved passages, and assessing claim support and answerability.
Compare candidates on declared inputs while retaining missing, unsupported and
failed cases alongside quality, execution time and memory measurements.

The standalone Python engine provides synthetic datasets, candidate adapters,
task-specific scorers and versioned reports. **Core validation needs no model
weights, API keys, Docker or Deposium application stack.**

**Research status:** references and translations are agent-authored and pending
human review. Results are exploratory. A correct proposal does not establish
tool execution, a useful final answer or product qualification.
**Model grading is already automatic.** Human-review forms are an additional
reference audit, not a prerequisite for running exploratory model comparisons.
The main choice packs are bilingual FR/EN; passage evidence also covers DE/ES/IT/PT.

## Start here

| Page | What to find |
|---|---|
| **[Results and coverage](docs/RESULTS.md#coverage-overview)** | Every model/runtime observation, explicit untested cells, task-specific scores, split denominators, speed and memory; [CSV](docs/leaderboard/coverage.csv) and [JSON](docs/leaderboard/coverage.json) exports. |
| **[Campaign status and next steps](docs/CAMPAIGN_STATUS.md)** | Current issue order, dependencies, exit criteria, validation limits and what can proceed in parallel. |
| **[Evaluation protocol](docs/PROTOCOL.md)** | Allowed model inputs, task boundaries, scoring, versioning and evidence preservation. |
| **[Contributing offline](CONTRIBUTING.md)** | Copyable checks, expected signals, optional dependencies and a small first contribution. |

Dated reports remain in the [campaign archive](docs/RESULTS_INDEX.md). They are
evidence for their recorded revisions, rather than competing current roadmaps.
The [public issue roadmap](https://github.com/theseedship/classification_tests_deposium/issues/19)
tracks the work described by the status page.

## What the benchmark covers

| Application question | Current boundary |
|---|---|
| What does this request need? | Closed-choice context use, including documentary, mathematics and chemistry cases. |
| Which tool or capability should be proposed? | First-tool agreement and four-proposal capability/workflow choices; no executed tools. |
| Can tools execute with valid bindings and bounded feedback? | Synthetic argument/episode controls execute lookup/sum functions; real-model output and application integration remain unqualified. |
| Which retrieved passages matter? | Ranking and relevance over fixed synthetic passage pools. |
| Do the passages support the claim or answer? | Separate support and answerability tasks, with conflict and insufficient-evidence cases. |
| What changes with language, order, length or runtime? | Declared campaign-specific variants and resource measurements; no universal hardware speed ranking. |

The [coverage overview](docs/RESULTS.md#coverage-overview) shows which candidates
actually ran each task. Its [harness overview](docs/RESULTS.md#harness-coverage)
separates implemented scripted discovery, arguments and feedback fixtures from
untested real-model output paths, empirical model allocation, application replay,
and final answer/citation quality. Closed-choice success does not fill those cells.

Datasets have distinct denominators: context choices **132**, first-tool
proposals **24**, capability choices **192**, physics choices **48**, and passage
evidence **1,536 correlated variants**. Typed-decision fixtures contain 36 cases;
the 14 document-task cases overlap that pack. Graph and tool-selection review
packs are review material with no scored model results. See the
[dataset cards](datasets/) and [protocol](docs/PROTOCOL.md) for family counts,
splits, permitted inputs and each task's eligible denominator.

The experimental [bounded tool-plan contract](docs/TOOL_PLAN_CONTRACT_V1.md)
adds one synthetic family as two FR/EN training cases, with complete alternative
proposals and negative controls through the shared engine. This is a recorded
harness fixture: zero model cases, zero held-out cases and no executed tools.
The proposed 12-family expansion remains unmaterialized beyond that first family.

The separate [tool-discovery pack](datasets/tool-discovery-v1/README.md)
adds 12 FR/EN cases in six new families: shortlist tools from a synthetic
catalogue, select a minimal sufficient set, or explicitly request clarification
or report no suitable tool. Its [contract and metrics](docs/TOOL_DISCOVERY_CONTRACT_V1.md)
separate shortlist recall/precision from final-set sufficiency and unnecessary
selections. Only recorded controls are qualified so far: no model result,
argument execution or adaptive tool loop is established.

The [argument-execution fixture](datasets/tool-arguments-v1/README.md) adds four
FR/EN training cases with two bounded Python tools. A lookup actually returns
an artifact; a proposed sum must consume that exact artifact with the correct
column, unit and scope. The execution adapter retains actual receipts and
separate stage metrics. This is synthetic harness execution, with zero real
model cases or application integrations; adaptive episodes are a separate task.

The [bounded episode fixture](datasets/tool-episodes-v1/README.md) adds 14 FR/EN
training controls across success, transient/persistent errors, empty/partial
data, missing input and an unavailable tool. Each policy step receives actual
observations. Correct handling of all 14 scenarios includes **four successful
task results** and ten justified stops or clarification requests. The fixture
checks retry, call, step and elapsed-time limits; scripted replay does not
establish real-model adaptation or production MCP integration.

The [passage-order and retention extension](docs/PASSAGE_ORDER_RETENTION_V1.md)
plans the four existing rotations and both passage views: 5,632 logical test
decisions map to 920 distinct candidate inputs. It analyzes sealed observations
with the shared scorers, including sufficient-evidence and conflict retention.
Existing rotation-zero observations leave 192 additional inputs unobserved;
the extension performs no new inference or model-order qualification.

A separate [local JSON proposal path](docs/LOCAL_TOOL_POLICY_V1.md) and its
[supervised launch protocol](docs/LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md)
were run once on a frozen ten-case TRAIN canary with a generative Qwen
candidate outside the classifier cohort. The [first run](docs/LOCAL_TOOL_POLICY_RESULTS_20261030.md)
collected all ten cases and passed **5/10** (quality verdict `fail`; discovery 0/2,
arguments 2/2, episodes 3/6). It qualifies the runtime and scoring path, not
tool routing: the cases are TRAIN, correlated and synthetic. A frozen
[24-case held-out pack](datasets/tool-policy-heldout-v1/README.md) and a revised
candidate prompt are fixed by the [held-out protocol](docs/LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md);
at freeze it has zero model cases.

Synthetic scenarios represent workflow properties, rather than production
conversations. Translations, catalogue views and passage orders stay in their
family split; they are not independent users or facts. Identity, access,
consent and resource guards remain deterministic and outside model predictions.

## Quick start

Use **Python 3.11+ and Git**. The core has no external Python dependencies and
needs no package installation. From a fresh public clone:

```bash
git clone https://github.com/theseedship/classification_tests_deposium.git
cd classification_tests_deposium
python3 -m deposium_bench validate-registry
python3 -m deposium_bench validate-cases \
  --dataset datasets/context-choice-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/physics-choice-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-discovery-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-arguments-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-episodes-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-policy-canary-v1/cases.jsonl
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-policy-heldout-v1/cases.jsonl
python3 -m deposium_bench validate-mastra-read
python3 -m deposium_bench.passage_dataset validate
python3 -m deposium_bench.passage_corpus --check
python3 -m deposium_bench.capability_corpus --check
python3 -m deposium_bench.passage_order_retention plan
python3 scripts/build-full-results.py --check
python3 scripts/check-reference-grids.py
```

These checks validate data, contracts and generated views; they do not score a
real model. See [Contributing](CONTRIBUTING.md) for expected signals and tests.
The reference-grid command exercises fixed correct, incorrect and empty outputs
through the shared scorers. It checks application of the grading rules, not
the semantic truth of every authored answer. See
[automatic grading and reference checks](docs/PROTOCOL.md#automatic-grading-and-reference-checks).
Linux is the reference environment for the full offline suite. macOS core and
targeted checks are separate from a full-suite qualification; the
[validation matrix](docs/CAMPAIGN_STATUS.md#validation-matrix) records known
limitations. Optional skips do not establish successful integration.

## Run or add a real model

Read the [protocol](docs/PROTOCOL.md), the relevant dataset card, and a
[candidate profile](profiles/) with its dated setup and resource protocol.
Prepare only selected pinned assets in an isolated runtime, verify their hashes,
and write each campaign to a new archive. Imports and ordinary validation do
not download weights or start API experiments. Remote campaigns need explicit
credentials and budgets.

The [candidate inventory](docs/NEXT_CANDIDATES.md) distinguishes new checkpoints
from previously tested runtime identities. The
[frozen capability cohort](docs/CAPABILITY_CAMPAIGN_PLAN.md) remains separate
from additional candidates. Historical D3 27B is not D3 Ultra; Jev 1.13 is not
Jev 1.14. A publisher's result does not count as a result in this benchmark.

For `run`, exit code `0` requires all cases to pass. Code `1` can mean a complete
run with incorrect predictions; inspect `completion_status`, coverage and all
statuses. Code `2` signals invalid input/archive or zero scored cases.
Observation commands have separate qualification rules. `ok` means valid output,
not a correct answer, and a resource refusal is a preflight outcome.

Every new scored campaign must enter the shared result generator and its
regression checks. Refresh public tables and exports with
`python3 scripts/build-full-results.py --write`, then run `--check`. Linking
only a standalone report does not complete consolidation. The CLI and notebook
use the same engine; notebook cells must not implement another pipeline.

## Reproducibility and release boundaries

The public repository includes source, synthetic cases, relative profiles,
protocols, aggregates and hashes. **Weights, installed environments, private
documents and some historical raw archives are not included.** A clone can
validate code and read reports; rescoring requires its original raw archive,
and new inference also requires pinned assets and runtimes.

Application replay additionally requires an accessible pinned application
harness and its dependencies; a contract registry is not evidence of an active
service. Preserve original datasets and archives, record failures, and never
adjust references or tune on exposed test cases to improve a score.

When citing a result, identify its **report date/commit, dataset version,
model revision, runtime/precision, task, split, denominator and review status**.
Public contributions must contain reviewed synthetic material and aggregates.
Ignored local material stays local; see [Contributing](CONTRIBUTING.md),
[AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md).

## Licensing

Original public benchmark code, documentation and synthetic datasets are
licensed under [MIT](LICENSE), copyright 2026 The Seed Ship. Ignored local
Deposium files, application sources and private data are outside this release.
Models, native helpers and runtimes keep their own licenses. No weights are
included; a candidate profile grants no redistribution rights.
