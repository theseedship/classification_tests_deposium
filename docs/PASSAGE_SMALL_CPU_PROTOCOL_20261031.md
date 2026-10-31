# Passage evidence for the small macOS CPU rows: protocol

**Fixed on 31 October 2026, before any passage prediction by these runtimes.**
Issue #52. Fills the passage columns (relevance, claim support,
answerability, rotation 0) of the four macOS CPU rows that already have
context, tool, capability and physics observations: D3 lite, Vela 2.0 0.3B,
D3 nano and D3 mini. References and translations are agent-authored and
pending human review. This measures closed choices about supplied passages; it
does not qualify retrieval, generated answers or an application.

## Inputs and denominators

Unchanged `passage-evidence-v1`, SHA-256 `35a8b898…e476`, and the shared
`select_pilot(test)`: rotation 0, eight held-out families, eight language
directions, both `full` and `head_384` views, **128 pools**, exactly as the
[D3 Flash](PASSAGE_FLASH_PROTOCOL_20261029.md) and
[Clef Flash](PASSAGE_CLEF_PROTOCOL_20261029.md) passage campaigns.

| Axis | Logical decisions | Distinct physical calls | Choices |
|---|---:|---:|---|
| Relevance | 512 | 264 | grades 0–3 |
| Claim support | 768 | 392 | supports / refutes / insufficient |
| Answerability | 128 | 72 | answerable / insufficient / conflicting |

728 physical calls serve 1,408 logical decisions; exact-input reuse is not
extra evidence. Every `missing`, `unsupported`, `error`, `timeout` and
`abstain` stays in the logical and physical denominators.

## Runtimes

Each candidate uses its existing macOS CPU profile, the same identity as its
other packs, with the per-call timeout already fixed there. No profile,
prompt, projection or reference changes.

| Order | Profile | Model | Per-call timeout | Wall budget |
|---:|---|---|---:|---:|
| 1 | `profiles/d3-lite-macos-cpu.json` | `vllm-sr/d3-lite` @ `a8d25a91` | 60 s | 2 h |
| 2 | `profiles/vela2-03-macos-cpu.json` | `vllm-sr/Vela-2.0-0.3B` @ `d6f03aa9` | 30 s | 1 h |
| 3 | `profiles/d3-nano-macos-cpu.json` | `vllm-sr/d3-nano` @ `3aeb1c22` | 60 s | 3 h |
| 4 | `profiles/d3-mini-macos-cpu.json` | `vllm-sr/d3-mini` @ `a475367d` | 120 s | 6 h (amended, see below) |

Code change fixed with this protocol: `deposium_bench/passage_observation.py`
admits D3 lite/nano/mini and Vela 2.0 0.3B profiles bound to
`runtimes/d3-macos/runtime.lock` (the historical D3-lite profile stays
admitted), and allows local CPU sessions a wall budget up to six hours; remote
and native sessions keep one hour. A run stopped by its wall budget is reported
as partial with its remaining decisions `missing`; it is not extended after the
fact. The [worker restart policy](CPU_WORKER_RESTART_POLICY_20261031.md) applies.

```bash
python3 -m deposium_bench.passage_observation choice \
  --profile profiles/d3-lite-macos-cpu.json --max-seconds 7200 \
  --output results/d3-lite-macos-passage-NEXT
```

One run at a time, no other CPU campaign, and no checkout or branch change in
the working copy while a run is active.

## Amendment, 31 October 2026, before any D3 mini passage prediction

The first minutes of the D3 lite run measured 3.5 s per passage call against
3.1 s per context call on the same runtime. Scaled to D3 mini's context
latency (17.2 s median), its 728 calls need about 3.9 hours, too close to the
four-hour budget fixed above. Mini's wall budget is raised to six hours and the
local bound in `passage_observation.py` with it. No D3 mini passage prediction
existed when this was fixed; D3 lite's run was already under way and is
unchanged (2 h budget); Vela 2.0 0.3B and D3 nano keep their budgets.

## Reporting

Per axis: correct/all, scored/all, macro class accuracy, statuses, by
language direction and view; confusions for support and answerability; call
latency and worker RSS with their scopes. Comparisons with D3 Flash Q8, Clef
Flash Q8 and the historical Linux D3-lite rotation-0 observation use the same
pools; they are different runtimes. Register each run in the consolidated
results so the coverage matrix, rankings, At a glance and model pages update.
