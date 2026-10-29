# First offline contribution

Start with Python 3.11+ and Git. The core needs no Python package installation,
model weights, API key, Docker service, or application checkout. Cloning needs
network access; the validation commands below run against the public files.

Read [the working instructions](AGENTS.md) and [evaluation protocol](docs/PROTOCOL.md)
first. [Current status](docs/CAMPAIGN_STATUS.md) separates dated observations from
unfinished work. Comment on the issue with the part you will take before editing,
so contributors can avoid duplicate work.

## Validate a clean clone

```bash
git clone https://github.com/theseedship/classification_tests_deposium.git
cd classification_tests_deposium
python3 --version
python3 -m deposium_bench validate-registry
python3 -m deposium_bench validate-cases \
  --dataset datasets/context-choice-v1/cases.jsonl
python3 -m deposium_bench validate-mastra-read
python3 -m deposium_bench.passage_dataset validate
python3 -m deposium_bench.passage_corpus --check
python3 -m deposium_bench.capability_corpus --check
python3 scripts/build-full-results.py --check
```

Run these from the repository root. Each command must exit with code 0. For a
first check, look for these signals; counts belong to the checked revision and
can change when a reviewed corpus changes.

| Command | Expected signal | What it checks |
| --- | --- | --- |
| `validate-registry` | `status: valid`, `evaluation_status: not_run` | Registry and contract consistency; no service was observed. |
| `validate-cases` | `status: valid`, case count and hash | Case structure and dataset integrity; no candidate was scored. |
| `validate-mastra-read` | `status: valid_review_corpus`, `cases_scored: 0` | The provisional tool-choice review pack; not human approval or executed tools. |
| `passage_dataset validate` | `status: valid`, `review: agent_only_pending_human` | Passage-case structure; not semantic truth of the references. |
| `passage_corpus --check` | `Dataset regeneration matches` | Frozen passage data matches its generator. |
| `capability_corpus --check` | `status: valid_frozen_corpus`, `cases_scored: 0` | Frozen capability choices match their source. |
| `build-full-results.py --check` | `views current` | Committed result views match the existing public aggregates; no new inference. |

If a check fails, record the command, public commit ID (`git rev-parse HEAD`),
Python version, operating system, exit code, and a short redacted diagnostic.
Do not regenerate references or result views just to make the check pass.

## Run implementation checks separately

Start with a small, dependency-free set of case and scorer controls:

```bash
python3 -m unittest tests.test_cases tests.test_scoring -v
```

An `OK` result checks implementation behavior, including rejection of empty and
deliberately wrong outputs. It does not test a model or review the references.
Then run the full offline suite and report its actual summary:

```bash
python3 -m unittest discover -s tests -v
```

Linux is the reference environment for that full suite. The
[dated macOS checkpoint](docs/CAMPAIGN_STATUS.md#offline-verification-at-this-checkpoint)
records existing failures and errors; a passing core command or focused test set
does not turn the full suite green. Compare failures at the same public base
before attributing them to your change, and retain any new failure in your report.

Some checks need Node, JSON Schema tooling, notebook packages, or an accessible
pinned application checkout. The test's skip reason identifies a missing
prerequisite. A skip means that check did not run; it does not qualify the
dependency or integration. Do not download weights, start application services,
or call paid APIs to replace an optional skip during this first contribution.

## Choose a small change

- **Documentation:** fix one unclear command or boundary, then run the command
  and check its local links.
- **Synthetic fixtures:** follow the relevant [dataset card](datasets/), keep
  family variants in one split, and add a validation case in
  [the case tests](tests/test_cases.py).
- **Negative scorer controls:** use [the scorer tests](tests/test_scoring.py) to
  show an empty or incorrect output cannot pass. Keep the shared engine; do not
  create a second scorer in an example or notebook.
- **Reference review:** discuss one bounded issue with the maintainer first.
  Agent-authored references remain pending human review. Explain any proposed
  correction without rewriting existing references, scores, or campaign archives.

## Prepare a public pull request

Create a topic branch and keep one logical change. Run the relevant checks again,
then stage only the public files you intend to submit:

```bash
git diff --check
git add CONTRIBUTING.md
git diff --cached
python3 scripts/check-public-content.py
```

The staging command is an example for a guide-only change; name your own changed
public files explicitly. The content check must report `status: passed` and empty
`findings`. It checks the index, so run it after staging and again if the staged
files change. It is a pattern check, not proof that no private data exists.

Describe the problem, changed files, checks, failures, skips, and remaining limits
in the PR. Disclose material AI assistance. Do not include personal paths, private
logs, credentials, model weights, installed environments, or raw campaign archives.
Never force-add ignored material. [AGENTS.md](AGENTS.md#public-repository-and-private-local-material)
defines the public-content boundary; [the README](README.md#reproducibility-and-contributions)
links the separate requirements for real inference and application replays.
