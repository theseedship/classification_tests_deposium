# Held-out local JSON-policy evaluation protocol

**Fixed on 30 October 2026, before any held-out prediction.** This protocol
extends the [supervised TRAIN canary](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md)
to a frozen held-out pack and a revised candidate prompt. At freeze there are
**zero held-out model cases**. The [TRAIN result](LOCAL_TOOL_POLICY_RESULTS_20261030.md)
(5/10, prompt v1) stays as recorded; nothing in it is rescored or relabelled.

## What the TRAIN run showed, and what may change

The TRAIN discovery failures were a contract-description gap on the candidate
side: the v1 prompt never said that the selected tools must appear in the
shortlist, and the schema accepts an empty shortlist. The episode failures were
candidate behavior (calling tools until the step limit). Under the
[protocol](PROTOCOL.md#3-freeze-the-experiment-before-predictions), TRAIN
exposure may inform the **candidate** configuration, never a reference.

Therefore:

- The candidate prompt is revised to `deposium.local-tool-policy-prompt/v2`.
  It states the public rules of the discovery, argument and episode contracts
  and names no case, catalogue entry, table, identifier or expected answer.
  Its exact text is the module constant `PROMPTS[...]` in
  `deposium_bench/local_tool_policy.py`; v1 remains in the same table so a pure
  rescore of the TRAIN archive rebuilds its request bytes unchanged.
- The TRAIN canary cases, references and archive are **unchanged**.
- The held-out references were authored before any prediction and may not be
  revised to match a model. A disputed reference gets a new reviewed version.

## Frozen inputs

| Item | Fixed value |
|---|---|
| Held-out pack | [tool-policy-heldout-v1](../datasets/tool-policy-heldout-v1/README.md): 24 TEST cases, 12 FR/EN families (4 discovery, 2 arguments, 6 episodes); SHA-256 `7f7ed8f08fe15d5b897744fe71f2a5ed76344b5ccd7a0df43492b2dc3371bac7` |
| TRAIN pack (for the v2 re-run) | [tool-policy-canary-v1](../datasets/tool-policy-canary-v1/README.md), SHA-256 `6add6d14904e16cc39449368ff932316409c294dd43674f4fb9a1a1fcdbc2a6d` |
| Dataset binding | `--dataset-manifest` must name one of the two manifests whose SHA-256 is pinned in the launcher (`FROZEN_MANIFESTS`); an edited, untracked or self-consistent substitute is refused, as are case bytes, counts, splits or contracts that differ from the pinned manifest |
| Candidate | `unsloth/Qwen3-4B-Instruct-2507-GGUF` at `a06e946b…`, `Qwen3-4B-Instruct-2507-Q8_0.gguf`, SHA-256 `391c1e41…ef068`, unchanged |
| Runtime, envelope, controls | Identical to the TRAIN protocol: llama.cpp `efe3626b`, Metal, 4096 context, 256 output tokens, seed 42, temperature 0, one slot, 20 s per call, 600 s session, 8 GiB RSS plus 8 GiB reserve, 16 GiB admission, the same four technical controls |
| Episode budget | input/v2: 5 decisions, 3 tool calls, 2 lookup attempts, 60,000 ms including model time |

The held-out pack covers the discovery decisions `select` (a two-tool route and
two equivalent minimal alternatives), `clarify/missing_information` and
`no_suitable/unavailable`, and the episode outcomes `complete` (normal and one
transient retry), `persistent_error`, `no_data`, `partial_data` and
`unavailable`. `no_suitable/no_capability` is not covered; `missing_information`
episodes remain covered by TRAIN only.

## Order of execution

1. **TRAIN re-run with prompt v2** into a new archive
   (`results/local-tool-policy-<date>-00N`, default manifest). This measures the
   prompt change on the exposed cases and is reported as a second TRAIN
   observation, not as a held-out result.
2. **Held-out run with prompt v2** into another new archive, with
   `--dataset-manifest datasets/tool-policy-heldout-v1/manifest.json` and
   `--dataset datasets/tool-policy-heldout-v1/cases.jsonl`.
3. No third prompt revision, reference change or re-run after seeing held-out
   outcomes. A further candidate change requires a fresh held-out version.

```bash
python3 scripts/run-local-tool-policy-pilot.py \
  --source-root "$NATIVE_SOURCE" --binary "$NATIVE_BINARY" \
  --runtime-manifest "$NATIVE_MANIFEST" --model "$MODEL_FILE" \
  --assets-manifest profiles/qwen3-4b-instruct-q8-assets.json \
  --dataset datasets/tool-policy-heldout-v1/cases.jsonl \
  --dataset-manifest datasets/tool-policy-heldout-v1/manifest.json \
  --output results/local-tool-policy-heldout-NEXT
```

## Reporting

Report TRAIN v1, TRAIN v2 and held-out v2 as three separate observations with
their own archives, prompt versions and denominators. For the held-out pack:
24 eligible cases; discovery 8 (select-reference metrics over the 4 `select`
cases, decision correctness over all 8), arguments 4,
episodes 12 with 4 success-eligible cases; FR and EN separately. Retain every
`missing`, `unsupported`, `error`, `timeout` and `abstain` case in its
denominator. A pure rescore must reproduce each archive without a model, tool,
clock or credential.

Twenty-four correlated cases from one model establish whether the generated
JSON path handles each declared contract outcome at least once under fresh
identities. They do not rank models, qualify tool routing in general, qualify
live MCP or product behavior, or substitute for the pending human review of
the agent-authored references.
