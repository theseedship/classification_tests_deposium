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
python3 -m deposium_bench validate-mastra-read
python3 -m deposium_bench.passage_dataset validate
python3 -m deposium_bench.passage_corpus --check
python3 -m deposium_bench.capability_corpus --check
python3 scripts/build-full-results.py --check
```

Each command should exit `0`. The expected signals are:

| Check | Expected meaning |
|---|---|
| Registry | Contracts are structurally valid; this does not contact or qualify services. |
| Context / physics cases | Valid corpus, respectively 132 / 48 cases; no candidate inference. |
| First-tool cases | Valid 24-case proposal pack; references remain provisional. |
| Passage dataset / corpus | Valid 1,536-case corpus and no difference from the frozen generated corpus. |
| Capability corpus | No difference from the frozen 192-case corpus. |
| Full results | No difference between tracked generated tables/exports and their declared public sources. |

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

## A small first pull request

Choose one bounded issue from the
[roadmap](https://github.com/theseedship/classification_tests_deposium/issues/19),
describe the behavior being checked, and keep the change within the shared
engine or documentation. Useful first changes include an explicit untested
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
