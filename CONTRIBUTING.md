# Contributing offline

Start with the [README](README.md), [protocol](docs/PROTOCOL.md) and
[current issue order](docs/CAMPAIGN_STATUS.md). Small offline contributions are
welcome: clarify a task's limits, add a scorer negative control, or implement a
fixture for an agreed contract. You do not need model weights, API keys, Docker,
the application stack or an external Python package to validate the core.

## First validation

Use Python 3.11+ and Git. Check `python3 --version` first; if your macOS system
Python is older, select a supported Python environment before these commands.
Run this from the repository root:

```bash
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
python3 -m deposium_bench validate-mastra-read
python3 -m deposium_bench.passage_dataset validate
python3 -m deposium_bench.passage_corpus --check
python3 -m deposium_bench.capability_corpus --check
python3 -m deposium_bench.passage_order_retention plan
python3 scripts/build-full-results.py --check
python3 scripts/check-reference-grids.py
```

Each command should exit `0`. The expected signals are:

| Check | Expected signal | Expected meaning |
|---|---|---|
| Registry | `status: valid`, `evaluation_status: not_run` | Contracts are structurally valid; this does not contact or qualify services. |
| Context / physics cases | `status: valid`, case count and hash | Valid corpus, respectively 132 / 48 cases; no candidate inference. |
| Tool-discovery cases | `status: valid`, `cases: 12` | FR/EN catalogue-selection pack; recorded controls only, no qualified model or executed tool. |
| Tool-argument cases | `status: valid`, `cases: 4` | Checks the bounded training fixture without executing its tools. Run its explicit control profile for actual lookup/sum receipts. |
| Tool-episode cases | `status: valid`, `cases: 14` | Validates the training episode pack without executing tools. Its explicit control profile executes a bounded feedback loop; zero model cases. |
| Local-policy canary | `status: valid`, `cases: 10` | Checks frozen TRAIN inputs/references without a model or tools; the prepared generated-JSON route still needs actual runtime qualification. |
| First-tool cases | `status: valid_review_corpus`, `cases_scored: 0` | Valid 24-case proposal pack; references remain provisional. |
| Passage dataset / corpus | `status: valid`; `Dataset regeneration matches` | Valid 1,536-case corpus and no difference from the frozen generated corpus. |
| Capability corpus | `status: valid_frozen_corpus`, `cases_scored: 0` | No difference from the frozen 192-case corpus. |
| Passage-order plan | `status: offline_prepared_no_new_inference`, `distinct_physical_calls: 920` | Plans 5,632 logical test decisions across existing rotations/views; executes no model. |
| Full results | `views current` | Tracked generated tables/exports match their declared public sources. |
| Reference grids | `status: implementation_checks_passed` | Shared validators and scripted controls pass with explicit denominators; no inference or proof that every authored answer is true. |

A failing `--check` is a discrepancy to inspect. Do not regenerate a frozen
corpus or change a reference merely to clear a failure. For intentional result
generator changes, run `python3 scripts/build-full-results.py --write`, inspect
the diff and rerun `--check`.

## Tests and platform limits

For a small example that exercises the physics corpus and its controls:

```bash
python3 -m unittest discover -s tests -p 'test_physics_corpus.py' -v
```

Expect a nonzero test count and final `OK`; read any skips. Choose targeted
tests for the code you change and include empty and deliberately wrong outputs
when changing a scorer. A mock or oracle fixture is an implementation check,
rather than a measured model result or human reference approval.

The full offline suite is a separate command:

```bash
python3 -m unittest discover -s tests -v
```

Linux is the reference environment. Some checks require optional Node, JSON
Schema, notebook or application dependencies; their skip messages identify the
missing prerequisite. Imports and ordinary tests must not download weights,
call paid APIs or start services. A skipped dependency is not qualified.

The [validation matrix](docs/CAMPAIGN_STATUS.md#validation-matrix) records the
macOS checkpoint: core and targeted checks succeeded, while the full suite had
known failures/errors also present on its compared public base. Do not present
that as a full macOS PASS or reuse a historical test count as current evidence.
Report your OS, Python version, commands, failures and skips with your change.

For a failing check, include the public commit SHA, exact command and exit code,
plus a short redacted diagnostic. Compare full-suite failure identifiers on the
same public base before attributing a platform failure to a patch. Exclude local
paths, credentials and private data from diagnostics; a successful validation
still does not mean a real model campaign ran.

## A small first pull request

Choose one bounded issue from the
[roadmap](https://github.com/theseedship/classification_tests_deposium/issues/19),
describe the behavior being checked, and keep the change within the shared
engine or documentation. Read its discussion and existing pull requests before
editing to avoid overlapping work. Useful first changes include an explicit untested
capability label, a malformed-output scorer control, or one deterministic
success/failure fixture for a reviewed contract. Human reference review is a
distinct contribution tracked by
[#8](https://github.com/theseedship/classification_tests_deposium/issues/8).

Keep source families and translations in their existing splits. New scenarios
need a new version and fresh families; do not rewrite v1 after seeing model
errors. Real campaigns need separate setup, resources and authorization.

## Check public contents before sharing

This repository is public. Preserve ignored local material and the ignore
rules; do not force-add ignored paths or copy private content into public files.
Fixtures must be synthetic. Never publish credentials, private documents or
metadata, personal development paths, raw private archives or private Git
history. Clear notebook outputs and execution counts.

Stage only the public paths you reviewed. For example, for a README-only change:

```bash
git status --short
git add README.md
git diff --cached --stat
git diff --cached --check
git diff --cached
python3 scripts/check-public-content.py
```

The final command should report `"status": "passed"` and empty `findings`.
It checks **Git's index only**, including ignored paths and common secret/path
patterns; it is not proof that content is safe. Unstaged changes and untracked
files are outside its scope. Review provenance and the actual staged diff as
well, then include the relevant validation results and limits in the PR.
State any material AI assistance alongside the checks and their limitations.

The expected-output signals and diagnostic guidance incorporate the external
contribution in [PR #23](https://github.com/theseedship/classification_tests_deposium/pull/23)
by [ungaaaabungaaa](https://github.com/ungaaaabungaaa), adapted to the current guide.
