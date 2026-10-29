# Deposium RAG Decision Bench

An exploratory benchmark for **decision models and rerankers in
retrieval-augmented generation (RAG)**. Evaluate what a request needs, which
tool to propose, which passages matter, and whether they support a claim.
Compare candidates on the same visible inputs and retain failed or unsupported
cases alongside scores, actual runtimes, and resource measurements.

A standalone Python engine supplies synthetic datasets, candidate adapters,
task-specific scorers, and versioned reports. **No Deposium application stack is
needed for validation or isolated models.** Integration tests are separate.

**Research status:** references and translations are agent-authored and pending
human review. Results are exploratory. Routing agreement is not a validated
business decision, and a correct choice does not establish end-to-end answer
quality. The 132-case totals mix splits; test-only results are separate.

**[Full results: all models, tasks, speed and memory](docs/RESULTS.md)** ·
[Evaluation protocol](docs/PROTOCOL.md) · [Datasets](datasets/) ·
[Progressive campaign plan](docs/CAPABILITY_CAMPAIGN_PLAN.md) ·
[Tool/MCP and model-routing proposal](docs/INTENT_AND_MODEL_ROUTING.md)

## What is this useful for?

| Application | Question being evaluated | Boundary |
|---|---|---|
| Request understanding | Inventory, stored summaries, retrieved content, or clarification? | Closed-choice understanding; a prediction grants no document access. |
| First tool selection | Search, compute statistics, or fall back to a planner? | Candidate proposals; the 24-case observation does not execute tools. |
| Retrieval and reranking | Which passages are relevant, and in what order? | Fixed passage pools, separate from live search and final generation. |
| Evidence assessment | Does a passage support or refute a claim? Is the evidence sufficient? | Task-specific references; similarity or confidence alone does not prove support. |
| Robustness and resource tradeoffs | What changes with language, distractors, length, option order, or quantization? | Separate campaigns and runtime identities; no universal hardware speed ranking. |

Keep **model capability**, **application integration after deterministic guards**,
and **end-to-end RAG quality** separate. Identity, access, consent, and resource
checks remain outside candidate predictions.

The benchmark isolates steps inside RAG; it does not currently qualify a full
retrieval-to-answer system, citation fidelity, or user-visible product behavior.
The complementary [capability-choice pack](datasets/capability-choice-v1/README.md)
adds 192 synthetic choices about capability/tool sets, arguments, dependencies,
clarification, and next steps after fixed observations. It includes geospatial,
web, open-data and local-document scenarios, with compact and expanded catalogues.
The [first D3 Flash Q8/Metal campaign](docs/CAPABILITY_FLASH_RESULTS_20261029.md)
reached **192/192**, including **96/96 test cases**, on 29 October 2026.
This ceiling on four-proposal synthetic choices does not qualify tool execution
or product behavior. The [next harness stages](docs/INTENT_AND_MODEL_ROUTING.md)
cover free-form tool selection and complete execution loops. Difficulty prediction
and model assignment remain a separate axis.

## Quick start: no weights, API keys, Docker, or services

Use **Python 3.11+ and Git**. Run commands from the repository root; the core
has no external Python dependencies and needs no package installation.

```bash
git clone https://github.com/theseedship/classification_tests_deposium.git
cd classification_tests_deposium
python3 -m deposium_bench validate-registry
python3 -m deposium_bench validate-cases \
  --dataset datasets/context-choice-v1/cases.jsonl
python3 -m deposium_bench validate-mastra-read
python3 -m deposium_bench.passage_dataset validate
python3 -m deposium_bench.passage_corpus --check
python3 -m deposium_bench.capability_corpus --check
python3 scripts/build-full-results.py --check
```

These commands validate data, contracts, and implementation controls.
**They do not download or score a real model.** Optional Node, JSON Schema,
notebook, and application integration checks may be skipped when their
dependencies are unavailable. A skipped check is not a successful integration.

Linux is the reference environment for the full offline unit suite. Campaign
reports document model-specific macOS checks and inference qualifications.
The frozen campaign code was checked offline on 29 October 2026:
**817 tests, 786 passed, 31 optional skips**, no failures.
No model weights or external services were required. Run the unit suite separately:

```bash
python3 -m unittest discover -s tests -v
```

## Datasets and tasks

| Pack | Size and languages | Evaluation status |
|---|---|---|
| [Context choice](datasets/context-choice-v1/README.md) | 132 cases, 66 FR/EN families; documentary tasks, mathematics, chemistry | Scored exploratory decisions; 36 train / 30 calibration / 66 test cases. |
| [First tool choice](datasets/mastra-read-pilot-v0/README.md) | 24 cases, 12 FR/EN families; search / statistics / fallback | Provisional agreement; zero human-approved references and zero semantically qualified cases. |
| [Capability and workflow choices](datasets/capability-choice-v1/README.md) | 192 cases, 48 FR/EN families × 8/32-card catalogues; selection, arguments, fixed-observation next steps | [D3 Flash Q8/Metal: 192/192, test 96/96](docs/CAPABILITY_FLASH_RESULTS_20261029.md); agent references pending human review, no executed tools or product qualification. |
| [Passage evidence](datasets/passage-evidence-v1/README.md) | 1,536 cases from 24 synthetic families; FR, EN, DE, ES, IT, PT | Ranking, relevance, claim support, answerability; four passage orders and two views are correlated variants. |
| [Typed decisions](datasets/decisions-v1/README.md) | 36 cases, 18 FR/EN families | Contract and fixture controls; component replay needs application sources. |
| [Document tasks](datasets/document-task-v1/README.md) | 14 cases, seven families | Historical projection of the typed-decision pack, not another independent corpus. |
| [Graph review](datasets/graph-document-review-v0/DATASET.md) | 16 synthetic FR/EN templates, eight families | Unresolved references, zero cases scored; no captured graph or document collection included. |
| [Tool-selection review](datasets/tool-selection-review-v0/README.md) | 16 review cases, eight families | Review material only; no delivered runner or scorer for this pack. |

Synthetic cases represent workflow properties, not production conversations.
Translations, document/scenario variants, and passage orders stay in their family
split; they are not independent users, documents, or algorithms. Dataset cards
explain construction, oracles, review, and limits; most cards are in French.

## Evaluation protocol

1. **Fix the experiment before inference.** Version the dataset, profile,
   projection, scorer, and budgets; pin model/tokenizer/runtime revisions,
   precision, device, and prompts.
2. **Expose only allowed inputs.** Adapters use the task-specific input
   projection: context, question, options, passage pools, or structured fields
   as applicable. Expected answers, reference explanations, split labels,
   and descriptive case identities stay outside model inputs.
3. **Check the real inference path.** Audit native tokenization and forward
   inputs where supported. Refuse unsupported lengths instead of silently
   truncating; record the observed model/runtime.
4. **Keep outcomes distinct.** `ok` means valid output, not a correct answer.
   `unsupported`, `missing`, `error`, `timeout`, and `abstain` remain distinct.
   Empty outputs and zero scored cases cannot produce a passing evaluation.
5. **Report coverage and denominators.** Keep accuracy, passage nDCG, support,
   and routing agreement separate, with split/language/domain/family breakdowns.
6. **Preserve evidence.** Archive cases, profile, provenance, raw outputs, scores,
   and hashes. A resume or rescore writes a new archive and keeps the original.
   Hashes establish byte integrity, not independent certification.

The [CLI](deposium_bench/cli.py) and [notebook](notebooks/decision_bench.ipynb)
call the same engine, datasets, adapters, and scorers. Notebook cells do not
implement another pipeline. See the [English protocol](docs/PROTOCOL.md),
[campaign guide, French](docs/CAMPAIGNS.md), and [notebook guide, French](docs/NOTEBOOK.md).

## Selected observations

**29 October 2026:** the first complementary
[D3 Flash Q8/Metal campaign](docs/CAPABILITY_FLASH_RESULTS_20261029.md) reached
192/192 on capability choices (test 96/96); its separate fresh context anchor
reached 124/132 (test 61/66). These runs are reported separately from the
historical comparison below. Canary calls do not enter either denominator.

**[Open the full results](docs/RESULTS.md): 28 model/runtime observations**, with
complete quality, domain, language, complexity, speed and memory tables;
[every exported task breakdown](docs/leaderboard/task-breakdown.csv) and
[all other benchmark campaigns](docs/leaderboard/other-benchmarks.md) are linked
from the same page. Physics and general plugin/MCP execution remain untested.

These rows use the same 132-case context pack and 24 routing proposals, with
different revisions, precisions, and runtimes. They are **not a general
leaderboard or a controlled comparison of hardware latency**.

| Model observation | Actual runtime | All splits /132 | Test only /66 | Provisional routing agreement /24 |
|---|---|---:|---:|---:|
| Historical D3, class 27B Q4 | llama.cpp / Metal | 128 | 65 | 24 |
| D3 Flash Q8 | llama.cpp / Metal | 124 | 61 | 20 |
| GLiClass v4 9B BF16 | Official PyTorch pipeline / MPS | 117 | 63 | 20 |
| Vela3-fast, decision backbone only | Official DecisionEncoder / CPU FP32 | 57 | 28 | 18 |

Vela3-fast's specialized span and router adapters were not loaded. D3 Ultra and
Turbo are **not evaluated here**; the historical D3 row identifies neither.
A name alone does not identify the tested weights, readout, or runtime.

The English [full results](docs/RESULTS.md) retain coverage, revisions, and
resource scopes, and link to the dated [campaign archive](docs/RESULTS_INDEX.md).
Older campaign reports are primarily in French. The
[candidate inventory](docs/NEXT_CANDIDATES.md) distinguishes new checkpoints
from models already tested on another runtime.

## Run a real model

Read the installation and resource protocol for a [candidate profile](profiles/).
Download only selected, pinned assets, verify their hashes, and use an isolated
runtime. Core validation does not install runtimes or fetch weights. Remote APIs
require explicit credentials and budgets; imports never start API experiments.

For example, **after preparing Vela3-fast's assets and pinned environment**:

```bash
python3 -m deposium_bench run \
  --dataset datasets/context-choice-v1/cases.jsonl \
  --profile profiles/vela3-fast-cpu.json \
  --output results/vela3-fast-local-001/bases
python3 -m deposium_bench observe-mastra-read \
  --dataset datasets/mastra-read-pilot-v0/cases.jsonl \
  --profile profiles/vela3-fast-cpu.json --max-seconds 300 \
  --output results/vela3-fast-local-001/mastra
```

No stack root is needed for these isolated model commands. Every output folder
must be new. The Vela3-fast profile requires its exact Python/runtime pins and
admits the model only when its memory guard passes. See
[setup, measurements, and limitations](docs/VELA3_FAST_RESULTS_20261028.md).

For `run`, exit code `0` requires a complete campaign with all cases passing.
Unsupported or otherwise unscored cases prevent this success status. Code `1`
can mean a **complete run with incorrect predictions**; inspect
`completion_status`, coverage, and statuses in the summary. Code `2` signals
invalid input/archive or zero scored cases. Observation commands have their
own qualification rules; agreement is not a semantic PASS.

## Reproducibility and contributions

The repo includes source, synthetic cases, profiles, hashes, and aggregates.
**Weights, installed environments, private documents, and some historical raw
archives are not included.** A clone can validate the benchmark and read reports;
rescoring needs a campaign's raw archive, and inference needs its assets/runtime. See
[evidence preservation, French](docs/EVIDENCE_PRESERVATION.md).

To add a candidate, use the shared adapter interface and the model's actual
native helper. Add a pinned profile, explicit setup instructions, input and
failure checks, and a new archive. Report missing capabilities and negative
results. Do not adjust references to improve a score, tune on test cases,
or treat translations as independent samples.

Application replays additionally need an accessible, pinned Deposium checkout
and its dependencies. `--stack-root` is configurable; the benchmark does not
replace routing or start the stack. An integration registry lists contracts,
not qualified services. See [integration boundaries](docs/PROTOCOL.md#1-keep-evaluation-boundaries-separate).

When citing a result, identify the **report date/commit, dataset version, model
revision, runtime/precision, task, split, and denominator**. Keep reference-review
status with the score. Maintainer instructions are in [AGENTS.md](AGENTS.md);
the [protocol](docs/PROTOCOL.md) defines the reproducibility boundaries.

## Local-only material

An ignored private overlay may exist in a maintainer's local checkout; it is not
distributed by this public repository or required for the core benchmark.
[AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) explain how to keep shared
instructions and local-only material separate.

## Licensing

The original benchmark code, documentation, and synthetic datasets are
licensed under [MIT](LICENSE), copyright 2026 The Seed Ship. This covers the
public tracked benchmark content. Ignored local Deposium files, application
sources, and private data are outside this release and its license.

Models, native helpers, and runtimes keep their own licenses. No weights are
included; a candidate profile does not grant redistribution rights.
