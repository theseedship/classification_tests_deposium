# Every model, every task

[All results](../../RESULTS.md) · [At a glance](../../RESULTS.md#at-a-glance) · [Coverage overview](../../RESULTS.md#coverage-overview)

40 observations. One line per model/runtime observation; each cell is **correct / all cases** on that task with its competition rank in parentheses, `partial` when the campaign did not complete, and **—** when the task was not run on that runtime. Context observations come first, in context rank order; passage-only methods and the generative candidate follow. Click the model for its page with every task, execution outcomes, speed and reports.

| Model / runtime | Context /132 | Tool /24 | Capability /192 | Physics /48 | Episodes (choice) /32 | Relevance /512 | Support /768 | Answerability /128 | Generated JSON (discovery, arguments, episodes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [D3 27B · Q4 Metal](D3Q4.md) | 128/132 (#1) | 24/24 | — | — | — | — | — | — | — |
| [D3 flash · CPU](D3flash.md) | 124/132 (#2) | 20/24 | — | — | — | — | — | — | — |
| [D3 flash · Q8 Metal](D3FlashQ8.md) | 124/132 (#2) | 20/24 | 192/192 (#1) | — | — | — | — | — | — |
| [D3 flash · Q8 direct Metal](D3FlashQ8Upstream.md) | 124/132 (#2) | — | — | 39/48 (#2) | — | 252/512 (#2) | 460/768 (#1) | 122/128 (#1) | — |
| [Jev 1.13 · HTTP API](Jev.md) | 123/132 (#5) | 20/24 | — | — | — | — | — | — | — |
| [D3 flash · Q4 Metal](D3FlashQ4.md) | 122/132 (#6) | 21/24 | — | — | — | — | — | — | — |
| [D3 mini · CPU](D3mini.md) | 119/132 (#7) | 20/24 | — | — | — | — | — | — | — |
| [D3 mini · macOS CPU](D3miniMacos.md) | 119/132 (#7) | 20/24 | 192/192 (#1) | 39/48 (#2) | 28/32 (#1) | — | — | — | — |
| [D3 nano · CPU](D3nano.md) | 117/132 (#9) | 18/24 | — | — | — | — | — | — | — |
| [D3 nano · macOS CPU](D3nanoMacos.md) | 117/132 (#9) | 18/24 | 188/192 (#4) | 28/48 (#4) | 16/32 (#2) | — | — | — | — |
| [GLiClass v4 9B · BF16 MPS](GLiClass9B.md) | 117/132 (#9) | 20/24 | — | — | — | — | — | — | — |
| [Clef Flash · Q8 direct Metal](ClefFlashQ8.md) | 110/132 (#12) | — | 192/192 (#1) | 41/48 (#1) | — | 261/512 (#1) | 446/768 (#2) | 109/128 (#2) | — |
| [Vela 2.0 4B · CPU](Vela4.md) | 106/132 (#13) | 18/24 | — | — | — | — | — | — | — |
| [Decision 2.0 Nox 4B · CPU](Nox.md) | 103/132 (#14) | 18/24 | — | — | — | — | — | — | — |
| [Liquid d1-3B · CPU](Liquid3.md) | 101/132 (#15) | 16/24 | — | — | — | — | — | — | — |
| [Noma · CPU](Noma.md) | 98/132 (#16) | 18/24 | — | — | — | — | — | — | — |
| [D3 lite · CPU](D3lite.md) | 95/132 (#17) | 19/24 | — | — | — | — | — | — | — |
| [D3 lite · macOS CPU](D3liteMacos.md) | 94/132 (#18) | 19/24 | 168/192 (#5) | 14/48 (#6) | 14/32 (#3) | — | — | — | — |
| [Decision 2.0 Sol 2B · CPU](Sol.md) | 93/132 (#19) | 19/24 | — | — | — | — | — | — | — |
| [Vela 2.0 0.8B · CPU](Vela08.md) | 79/132 (#20) | 14/24 | — | — | — | — | — | — | — |
| [Decision 2.0 Eos 0.8B · CPU](Eos.md) | 77/132 (#21) | 19/24 | — | — | — | — | — | — | — |
| [Decision 2.0 Eos 0.8B · Q8 Metal](EosQ8.md) | 77/132 (#21) | 19/24 | — | — | — | — | — | — | — |
| [D3 edge · CPU](D3edge.md) | 74/132 (#23) | 18/24 | — | — | — | — | — | — | — |
| [Decision 2.0 Kai 0.6B · CPU](Kai.md) | 70/132 (#24) | 16/24 | — | — | — | — | — | — | — |
| [Vela 2.0 0.3B · CPU](Vela03.md) | 65/132 (#25) | 18/24 | — | — | — | — | — | — | — |
| [Vela 2.0 0.3B · macOS CPU](Vela03Macos.md) | 65/132 (#25) | 18/24 | 128/192 (#6) | 18/48 (#5) | 0/32 (#4) | — | — | — | — |
| [GLiNER2.5-multi-Decide · CPU](GLiNER.md) | 59/132 (#27) | 12/24 | — | — | — | — | — | — | — |
| [Vela 3.0 fast · decision only · CPU](Vela3Fast.md) | 57/132 (#28) | 18/24 | — | — | — | — | — | — | — |
| [Laya multilingual · CPU](Laya.md) | 56/132 (#29) | 10/24 | — | — | — | — | — | — | — |
| [Julia-1 · CPU](Julia.md) | 52/132 (#30) | 11/24 | — | — | — | — | — | — | — |
| [Liquid d1-omni-600M · CPU](Omni.md) | 51/132 (#31) | 16/24 | — | — | — | — | — | — | — |
| [Indecis · untrained open mode · CPU](Indecis.md) | 44/132 (#32) | 11/24 | — | — | — | — | — | — | — |
| [ModernJEV-Decide-Preview · CPU](ModernJEV.md) | 42/132 (#33) | 8/24 | — | — | — | — | — | — | — |
| [Muose-50M-Decision · CPU](Muose.md) | 41/132 (#34) | 10/24 | — | — | — | — | — | — | — |
| [BGE v2-m3 · INT8 CPU](BGEPassage.md) | — | — | — | — | — | — | — | — | — |
| [D3 lite + BGE tie-break · CPU](D3liteBGE.md) | — | — | — | — | — | — | — | — | — |
| [D3 lite · CPU passage session](D3litePassage.md) | — | — | — | — | — | 229/512 (#3) | 443/768 (#3) | 88/128 (#3) | — |
| [Jev 1.14 + BGE tie-break](Jev114BGE.md) | — | — | — | — | — | — | — | — | — |
| [Jev 1.14 · HTTP API](Jev114.md) | — | — | — | — | — | — | 394/768 partial | 0/128 scored, attempted | — |
| [Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2](QwenToolPolicyV2.md) | — | — | — | — | — | — | — | — | 3/10, 6/6, 7/18 |

Tool /24 is provisional agreement with agent-authored first-tool proposals, not routing accuracy; it has no rank. Passage scores are rotation 0 (128 pools × decisions); the four-rotation Jev export and the ranking methods are on each model page and in [other benchmarks](../other-benchmarks.md). Generated regularly by `scripts/build-full-results.py`.
