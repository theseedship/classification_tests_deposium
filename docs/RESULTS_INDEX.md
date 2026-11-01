# Campaign archive

**This page is the archive, not the current work queue.** Start with
[Results and coverage](RESULTS.md#coverage-overview) for the English model/task
matrix, explicit untested cells, task-specific rankings, speed and memory.
[Campaign status](CAMPAIGN_STATUS.md) holds current issue dependencies and exit
criteria; the [protocol](PROTOCOL.md) defines method and evaluation boundaries.
The [other benchmark tables](leaderboard/other-benchmarks.md) retain passage
ranking, evidence, longer-context and timing observations.

This archive preserves dated protocols and source exports. Older eleven- and
nineteen-observation tables remain historical snapshots rather than the current
complete view. Most original campaign reports are in French.

The first [capability-choice campaign](CAPABILITY_FLASH_RESULTS_20261029.md)
and its fresh context anchor are separate observations from the 28-row
historical exports; their results are included in the current task tables.
Their 192- and 132-case denominators are never pooled. The 30 October 2026
entries add a sub-1B CPU candidate on the complementary packs and the first
generative tool-policy observations; see the
[cohort execution-order revision](CAPABILITY_CAMPAIGN_PLAN.md#initial-cohort-and-order).

| Campaign | Observations and boundaries | Reports and frozen evidence |
|---|---|---|
| D3 lite on macOS CPU, 30 October 2026 | New runtime identity (pinned macOS arm64 CPU, BF16 backbone): context 94/132 (test 49/66), tool 19/24, capability 168/192 (test 80/96), physics 14/48 (test 12/36); complete coverage, human review pending | [Results](D3_LITE_MACOS_RESULTS_20261030.md), [protocol](D3_LITE_MACOS_CPU_PROTOCOL_20261030.md), aggregates: [context/tool](evidence/d3-lite-macos-20261030/analysis.json), [capability](evidence/d3-lite-macos-20261030/capability.json), [physics](evidence/d3-lite-macos-20261030/physics.json) |
| Vela 2.0 0.3B on macOS CPU, 30 October 2026 | New runtime identity (pinned macOS arm64 CPU, FP32): context 65/132 (test 37/66), tool 18/24, capability 128/192 (test 62/96), physics 18/48 (test 14/36); complete coverage, human review pending | [Results](VELA2_03_MACOS_RESULTS_20261030.md), [protocol](VELA2_03_MACOS_CPU_PROTOCOL_20261030.md), aggregates: [context/tool](evidence/vela2-03-macos-20261030/analysis.json), [capability](evidence/vela2-03-macos-20261030/capability.json), [physics](evidence/vela2-03-macos-20261030/physics.json) |
| D3 nano on macOS CPU, 30–31 October 2026 | New runtime identity (pinned macOS arm64 CPU, BF16 backbone): context 117/132 (test 61/66), tool 18/24, physics 28/48 (test 22/36); capability attempt 001 partial (one 60 s timeout, then 149 unattempted), attempt 002 complete **188/192** (test 92/96) under the 300 s amendment | [Results](D3_NANO_MACOS_RESULTS_20261031.md), [protocol](D3_NANO_MACOS_CPU_PROTOCOL_20261030.md), [timeout amendment](D3_NANO_MACOS_TIMEOUT_AMENDMENT_20261031.md), aggregates: [context/tool](evidence/d3-nano-macos-20261031/analysis.json), [capability 001](evidence/d3-nano-macos-20261031/capability.json), [capability 002](evidence/d3-nano-macos-20261031/capability-002.json), [physics](evidence/d3-nano-macos-20261031/physics.json) |
| D3 mini on macOS CPU, 31 October 2026 | New runtime identity (pinned macOS arm64 CPU, BF16 backbone): context 119/132 (test 60/66), tool 20/24 (attempt 002; attempt 001 stopped by the 300 s observation wall budget), capability **192/192** (test 96/96), physics **39/48** (test 32/36); per-call timeouts 120 s / 300 s fixed before the run, no timeout | [Results](D3_MINI_MACOS_RESULTS_20261031.md), [protocol](D3_MINI_MACOS_CPU_PROTOCOL_20261031.md), aggregates: [context/tool](evidence/d3-mini-macos-20261031/analysis.json), [context](evidence/d3-mini-macos-20261031/context.json), [capability](evidence/d3-mini-macos-20261031/capability.json), [physics](evidence/d3-mini-macos-20261031/physics.json) |
| Closed-choice tool episodes pilot, 31 October 2026 | Executed fixture tools, harness-listed next actions, four macOS CPU classifiers on 32 episodes (20 TRAIN, 12 TEST): D3 mini 28/32 (test 10/12), D3 nano 16/32, D3 lite 14/32, Vela 2.0 0.3B 0/32 procedure-correct; D3 mini attempt 001 interrupted by an operator checkout and kept unranked | [Results](TOOL_EPISODES_CHOICE_PILOT_RESULTS_20261031.md), [mode and protocol](TOOL_EPISODES_CHOICE_MODE_V1.md), [aggregate](evidence/choice-episodes-20261031/analysis.json), [mini attempt 001](evidence/choice-episodes-20261031/d3-mini-attempt-001.json), [frozen pack](../datasets/tool-episodes-choice-v1/README.md) |
| Generated JSON tool policy, Qwen3-4B Q8, 30 October 2026 | Generative candidate outside the classifier cohort; TRAIN canary prompt v1 5/10, prompt v2 7/10 (identical with the host prompt cache disabled); held-out 24 TEST cases: attempt 1 partial 9/18 (RSS guard), attempt 2 complete 9/24 | [TRAIN v1](LOCAL_TOOL_POLICY_RESULTS_20261030.md), [TRAIN v2 and partial held-out](LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md), [complete held-out and cache control](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md); protocols: [supervised canary](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md), [held-out](LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md), [prompt-cache amendment](LOCAL_TOOL_POLICY_PROMPT_CACHE_AMENDMENT_20261030.md); aggregates under `evidence/local-tool-policy-*` |
| Small CPU passage evidence, 31 October–1 November 2026 | Four macOS CPU rows on the same 128 rotation-0 test pools as D3/Clef Flash, 728/728 calls `ok` each: D3 mini relevance 266/512, support 527/768, answerability 104/128; D3 nano 252/366/93; D3 lite 229/439/88; Vela 2.0 0.3B 112/151/93. Imbalanced classes: constant majority scores 224/584/88, so macro class accuracy is reported. D3 lite attempt 001 unranked (engine changed mid-run) | [Results, costs and limits](PASSAGE_SMALL_CPU_RESULTS_20261031.md), [protocol](PASSAGE_SMALL_CPU_PROTOCOL_20261031.md), [aggregates](evidence/passage-small-cpu-20261031/) |
| Clef Flash matched passage evidence, 29 October 2026 | Same 128 test pools as D3 Flash: relevance 261/512, support 446/768, answerability 109/128; complete coverage and paired class errors | [Comparison and limits](PASSAGE_CLEF_RESULTS_20261029.md), [public aggregate](evidence/passage-clef-flash-20261029/analysis.json), [frozen Clef protocol](PASSAGE_CLEF_PROTOCOL_20261029.md) |
| D3 Flash passage evidence, 29 October 2026 | Direct upstream Metal, 128 rotation-zero test pools: relevance 252/512, support 460/768, answerability 122/128; 728/728 physical calls valid | [Results, confusions and limits](PASSAGE_FLASH_RESULTS_20261029.md), [public aggregate](evidence/passage-flash-20261029/analysis.json), [frozen protocol](PASSAGE_FLASH_PROTOCOL_20261029.md) |
| Clef Flash Q8, 29 October 2026 | Direct upstream Metal: context 110/132 (test 59/66), capability 192/192 (test 96/96), physics 41/48 (test 31/36); complete scored coverage, human review pending | [Results and paired comparison](CLEF_FLASH_RESULTS_20261029.md), [public aggregate](evidence/clef-flash-20261029/analysis.json), [frozen protocol](CLEF_NATIVE_PROTOCOL_20261029.md) |
| Physics choices, 29 October 2026 | D3 Flash Q8/direct upstream Metal: 39/48, test 32/36; separate fresh context anchor 124/132, test 61/66; human review pending | [Results and limits](PHYSICS_FLASH_RESULTS_20261029.md), [public aggregate](evidence/physics-flash-20261029/analysis.json), [direct protocol](PHYSICS_FLASH_UPSTREAM_PROTOCOL_20261029.md) |
| Capability choice, 29 October 2026 | D3 Flash Q8/Metal: 192/192, test 96/96; fresh context anchor 124/132, test 61/66; separate 12-case technical canary | [English results and limits](CAPABILITY_FLASH_RESULTS_20261029.md), [reviewed aggregate](evidence/capability-flash-20261029/analysis.json), [frozen protocol](CAPABILITY_NATIVE_PROTOCOL_20261029.md) |
| Historical CPU/API context choice | 22 observations, including remote Jev 1.13; different model-specific precisions | [Summary](LARGER_CPU_RESULTS_20261011.md), [D3 mini/flash](D3_LARGER_CPU_RESULTS.md), [22-observation overview](evidence/model-comparison-larger-cpu-overview-20261011/report.md), [manifest](evidence/model-comparison-larger-cpu-overview-20261011/manifest.json) |
| Native Apple Metal | Eos Q8, D3 Flash Q8/Q4, historical D3 27B Q4; pinned llama.cpp | [Results and resources](NATIVE_DECISION_RESULTS_20261016.md), [aggregate](evidence/native-model-comparison-20261016/report.md), [session identities](evidence/native-model-comparison-20261016/native-sessions.json) |
| GLiClass v4 9B | Official PyTorch pipeline, MPS/BF16; native models repeated in the export are deduplicated in Full results | [Results](GLICLASS_V4_RESULTS_20261017.md), [reproduction](GLICLASS_V4_REPRODUCTION.md), [aggregate](evidence/gliclass-model-comparison-20261017/report.md), [session](evidence/gliclass-model-comparison-20261017/gliclass-session.json) |
| Vela 3.0 Fast | Decision backbone only, official CPU FP32/SDPA; specialized span/router adapters not loaded | [Results and reproduction](VELA3_FAST_RESULTS_20261028.md), [Ultra/Vela review](DECISION3_VELA3_REVIEW_20261028.md), [aggregate](evidence/vela3-fast-20261028/report.md), [session](evidence/vela3-fast-20261028/vela3-fast-session.json) |
| Passage ranking and evidence | Separate passage corpus; BGE, D3-lite projections, Jev 1.14, and order controls | [English tables](leaderboard/other-benchmarks.md#passage-ranking-and-evidence), [BGE/D3](PASSAGE_CPU_RESULTS_20261015.md), [Jev partial coverage](PASSAGE_JEV_RESULTS_20261015.md), [order controls](evidence/passage-order-control-20261015/report.md), [dataset](PASSAGE_EVIDENCE_DATASET.md) |
| Longer contexts | Four historical models; unsupported lengths and memory errors retained | [English tables](leaderboard/other-benchmarks.md#longer-contexts), [original report](evidence/length-comparison-20261004/report.md) |
| Repeated timing and stability | Separate repeated runs; no repeated native/MPS campaign inferred | [English tables](leaderboard/other-benchmarks.md#repeated-timing-and-stability), [original report](evidence/timing-comparison-20261004/report.md) |

The 132-case context pack contains 66 FR/EN families and includes train,
calibration, and test splits; test-only counts are separate. The 24 first-tool
proposals contain 12 families, zero human-approved references, and zero
semantically qualified cases. Agreement does not establish tool execution or
business correctness. See the [protocol](PROTOCOL.md).

Git shares source, synthetic cases, relative profiles, reports, aggregate JSON,
and hashes. It does not transfer model weights, installed environments, private
raw archives, or local configuration. Reading these public results and running
offline validation needs none of those private files. Rescoring requires the
original raw archive; new inference also requires pinned assets and runtimes.
The generated Full results join does neither. Initial archives remain preserved,
including the incomplete GLiClass envelope and its separate resumed tool phase.

No application deployment or integration qualification follows from these
isolated-model reports. The [proposed feature evaluation](INTENT_AND_MODEL_ROUTING.md)
separates capability discovery, tool sets, execution loops, and model assignment.
