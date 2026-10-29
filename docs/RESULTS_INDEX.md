# Campaign archive

**Start with [Full results](RESULTS.md)** for the complete English comparison:
28 model/runtime observations, all context-choice domains and task breakdowns,
provisional tool proposals, execution speed, and separate memory measurements.
The [other benchmark tables](leaderboard/other-benchmarks.md) cover passage
ranking, evidence, longer contexts, repeated timing, and the initial pilot.

This archive preserves dated protocols and source exports. Older eleven- and
nineteen-observation tables remain historical snapshots rather than the current
complete view. Most original campaign reports are in French.

| Campaign | Observations and boundaries | Reports and frozen evidence |
|---|---|---|
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
