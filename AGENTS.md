# Working instructions

Read [README.md](README.md), [docs/PROTOCOL.md](docs/PROTOCOL.md), and the relevant
dataset cards and campaign reports before implementation. Reports are dated:
verify model revisions and actual source/runtime versions before treating an
observation as current. No global installation or expensive indexing is needed
to read this repository.

## Scope

- Work in this repository and preserve other contributors' changes and repositories.
- Study decisions, retrieval, and evidence within RAG. Keep isolated model
  capability, application integration, and end-to-end product quality separate.
- Distinguish a local implementation check, a real model campaign, a historical
  result, and an untested capability declared by a model publisher.
- The CLI, notebook, and automation share the same engine, datasets, adapters,
  and scorers. Do not implement another evaluation pipeline in notebook cells.
- Optional application integrations must call a real harness at a pinned
  revision. Do not copy application routing or replace an application component
  with benchmark code. An integration registry is not evidence of active services.
- For a requested integration, inspect the supplied checkout and its current
  component inventory. Distinguish parent gitlinks, local HEADs, uncommitted
  source changes, and the sources/images actually executed.

## Evaluation integrity

- Keep case identities unique, references versioned, and documents/scenarios,
  translations, and derived variants in their family's assigned split.
- Only the task-specific allowed input reaches the candidate. Never send gold
  answers, reference explanations or spans, split labels, or descriptive case IDs.
- Keep synthetic and agent-authored references visibly qualified as such.
  Dataset validation is not human review or proof of semantic truth.
- Verify that scorers reject empty and deliberately incorrect outputs. Zero
  scored cases, missing corpora, or empty assertions never establish a PASS.
- Keep `unsupported`, `missing`, `error`, `timeout`, and `abstain` distinct.
  Show coverage and every score's denominator; do not drop failures from totals.
- Record versions/hashes, settings, actual model/runtime/device, raw outputs,
  and scores. A resume or rescore preserves the original archive.
- Keep identity, access, consent, source eligibility, and resource controls
  deterministic and independent of candidate predictions.
- A seed does not guarantee bitwise reproduction of a remote API. Similarity
  or confidence is not evidence that a claim is true.
- Do not regenerate a reference to obtain a passing score. Explain and obtain
  review of any reference change; retain prior datasets and campaign results.

## Execution and publication

- A clean checkout must validate the core without weights or external services.
  Real campaigns state their models, datasets, costs, and runtime prerequisites.
- Do not download models, call paid APIs, or modify services on module import,
  notebook opening, or ordinary unit-test execution. Real inference is explicit.
- Keep secrets out of arguments, notebooks, logs, and commits. Keep weights,
  private documents, installed environments, and private raw archives outside Git.
- Clear source-notebook outputs and execution counts before publication.
- Review data provenance and release eligibility before publishing any output.
  Do not copy internal source audits, personal paths, private document metadata,
  or credentials into a release or history merely to preserve an old link.
- Inspect Git state and use narrowly scoped commits. Do not include another
  contributor's work in progress. State checks completed and material gaps.
- An optional dependency or integration skipped during validation is not a
  successful qualification. Never weaken a hash, identity, scorer, or resource
  check to make an unavailable dependency appear successful.

## Core checks

- Python 3.11+ and Git suffice for core validation; no external Python dependency
  is required. Runtime-specific environments and optional tooling are separate.
- `python3 -m deposium_bench validate-registry` validates contracts without a stack.
- `python3 -m deposium_bench validate-cases --dataset datasets/context-choice-v1/cases.jsonl`
  validates the context-choice pack without inference.
- `python3 -m deposium_bench.passage_dataset validate` and
  `python3 -m deposium_bench.passage_corpus --check` validate the passage pack.
- `python3 -m unittest discover -s tests -v` uses temporary Git repositories;
  optional Node, JSON Schema, notebook, and application checks have separate
  prerequisites. Linux is the reference environment for the full offline suite.
- A preflight is not a campaign: retain `not_run`, zero cases scored, and
  `not_observed` for services. Generated outputs under `results/` stay outside Git.

## Public repository and private local material

- This repository is public. The same working directory may also contain
  confidential Deposium files, application repositories, research notes, raw
  campaign archives, local configuration, and a backup of the old private Git
  history. They are intentionally ignored and must stay local.
- Preserve ignored files. Do not delete or clean them to make a checkout look
  tidy; never run `git clean -x` or `git clean -X` on this workspace.
- Never use `git add -f`, force-add an ignored path, remove a privacy ignore rule,
  or copy ignored/private content into a tracked file to bypass that rule.
- Do not publish private contents, document titles or identifiers, tenant/user
  metadata, operational snapshots, personal development paths, author emails,
  hostnames, credentials, or private Git history in code, commits, pull requests,
  issues, logs, notebook outputs, screenshots, or generated reports.
- Read private local material only when needed for the authorized task. Reading
  it locally does not authorize publication. Report categories and aggregate
  findings without exposing values. Public fixtures must be synthetic.
- Stage explicit public paths. Before each commit or push, inspect the staged
  diff and run `python3 scripts/check-public-content.py`. An ignored path in the
  index is a failure even if its contents look harmless.
- Do not rewrite or upload the former private repository's history. This public
  history starts separately. Private backups and results are not restored by a
  public clone and need separate local backup.

- Never attach the old private history to this public remote by only changing
  `origin`, merging private branches, or mirroring private refs/tags. Use a clean
  public clone and transfer reviewed public files; preserve private material
  separately under ignored paths.
