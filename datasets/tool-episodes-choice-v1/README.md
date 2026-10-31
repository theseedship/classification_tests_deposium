# Tool episodes for the closed-choice step policy v1

**32 cases, 16 FR/EN families, 20 TRAIN and 12 TEST.** Frozen on 31 October
2026 before any candidate prediction for the
[closed-choice step policy pilot](../../docs/TOOL_EPISODES_CHOICE_MODE_V1.md).
Cases SHA-256 `f249752d4ab464a50fd96c0b573f36adf54d59995856e0d872962f9fa6dafab9`.

Every case is a byte-faithful copy of a public episode case from
[tool-episodes-v1](../tool-episodes-v1/README.md) (14, TRAIN),
[tool-policy-canary-v1](../tool-policy-canary-v1/README.md) (6 episodes, TRAIN)
or [tool-policy-heldout-v1](../tool-policy-heldout-v1/README.md) (12 episodes,
TEST), with two field changes: `input.schema_version` is
`deposium.tool-episode-input/v3` and `budgets.max_elapsed_ms` is 600000, a
ten-minute envelope that admits CPU classifier wall time over five steps.
Requests, scopes, fixtures, fault schedules, identities, splits, languages and
the eight-assertion references are unchanged. The [manifest](manifest.json)
records the source hashes and case lists; `scripts/build-choice-episodes-pack.py --check`
verifies the freeze.

Twelve cases are success-eligible (normal and one-retry routes); the other
twenty end in a clarification (missing identifier, partial data) or a stop
(no data, tool unavailable, persistent error). References are agent-authored
and pending human review. The held-out sources were exposed once to the
generative Qwen3-4B policy; no closed-choice candidate has seen any case.

```bash
python3 -m deposium_bench validate-cases --dataset datasets/tool-episodes-choice-v1/cases.jsonl
python3 scripts/build-choice-episodes-pack.py --check
```
