# Every model, every task

[All results](../../RESULTS.md) · [At a glance](../../RESULTS.md#at-a-glance) · [Coverage overview](../../RESULTS.md#coverage-overview)

49 observations. One line per model/runtime observation; each cell is **correct / all cases** on that task with its competition rank in parentheses, `partial` when the campaign did not complete, and **—** when the task was not run on that runtime. Context observations come first, in context rank order; passage-only methods and the generative candidate follow. Click the model for its page with every task, execution outcomes, speed and reports.

| Model / runtime | Context /132 | Tool /24 | Capability /192 | Physics /48 | Episodes (choice) /32 | Facade routing /80 | Advanced /96 | Complex /96 | Relevance /512 | Relevance v2 /512 | Support /768 | Answerability /128 | Generated JSON (discovery, arguments, episodes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [D3 27B · Q4 Metal](D3Q4.md) | 128/132 (#1) | 24/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 flash · CPU](D3flash.md) | 124/132 (#2) | 20/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 flash · Q8 Metal](D3FlashQ8.md) | 124/132 (#2) | 20/24 | 192/192 (#1) | — | — | — | — | — | — | — | — | — | — |
| [D3 flash · Q8 direct Metal](D3FlashQ8Upstream.md) | 124/132 (#2) | — | — | 39/48 (#3) | — | — | — | — | 252/512 (#5) | — | 460/768 (#4) | 122/128 (#2) | — |
| [Jev 1.13 · HTTP API](Jev.md) | 123/132 (#5) | 20/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 flash · Q4 Metal](D3FlashQ4.md) | 122/132 (#6) | 21/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 flash · Q4 direct Metal](D3FlashQ4Metal.md) | 122/132 (#6) | — | 192/192 (#1) | 39/48 (#3) | — | 79/80 (#1) | 94/96 (#1) | 91/96 (#3) | 247/512 (#8) | 381/512 (#5) | 430/768 (#9) | 126/128 (#1) | — |
| [D3 mini · CPU](D3mini.md) | 119/132 (#8) | 20/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 mini · Q8 Metal](D3miniQ8Metal.md) | 119/132 (#8) | — | 192/192 (#1) | 39/48 (#3) | — | 79/80 (#1) | 94/96 (#1) | 92/96 (#2) | 266/512 (#2) | 406/512 (#1) | 517/768 (#3) | 102/128 (#5) | — |
| [D3 mini · macOS CPU](D3miniMacos.md) | 119/132 (#8) | 20/24 | 192/192 (#1) | 39/48 (#3) | 28/32 (#1) | 79/80 (#1) | — | — | 266/512 (#2) | — | 527/768 (#2) | 104/128 (#4) | — |
| [D3 flash · 4-bit Uzu](D3FlashMUzu.md) | 118/132 (#11) | — | 192/192 (#1) | 40/48 (#2) | — | 78/80 (#5) | 92/96 (#5) | 88/96 (#5) | — | 386/512 (#4) | — | — | — |
| [D3 mini · Q4 Metal](D3miniQ4Metal.md) | 117/132 (#12) | — | 192/192 (#1) | 36/48 (#7) | — | 79/80 (#1) | 94/96 (#1) | 93/96 (#1) | 272/512 (#1) | 406/512 (#1) | 540/768 (#1) | 100/128 (#6) | — |
| [D3 nano · CPU](D3nano.md) | 117/132 (#12) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 nano · Q8 Metal](D3nanoQ8Metal.md) | 117/132 (#12) | — | 187/192 (#10) | 27/48 (#11) | — | 75/80 (#9) | 86/96 (#6) | 79/96 (#7) | 252/512 (#5) | 371/512 (#6) | 366/768 (#10) | 94/128 (#7) | — |
| [D3 nano · macOS CPU](D3nanoMacos.md) | 117/132 (#12) | 18/24 | 188/192 (#9) | 28/48 (#9) | 16/32 (#2) | 76/80 (#7) | — | — | 252/512 (#5) | — | 366/768 (#10) | 93/128 (#8) | — |
| [GLiClass v4 9B · BF16 MPS](GLiClass9B.md) | 117/132 (#12) | 20/24 | — | — | — | — | — | — | — | — | — | — | — |
| [GLiClass v4 9B · BF16 MPS · all packs](GLiClass9BMps.md) | 117/132 (#12) | — | 192/192 (#1) | 30/48 (#8) | — | 77/80 (#6) | 93/96 (#4) | 91/96 (#3) | — | 388/512 (#3) | — | — | — |
| [Clef Flash · Q8 direct Metal](ClefFlashQ8.md) | 110/132 (#18) | — | 192/192 (#1) | 41/48 (#1) | — | — | — | — | 261/512 (#4) | — | 446/768 (#6) | 109/128 (#3) | — |
| [Vela 2.0 4B · CPU](Vela4.md) | 106/132 (#19) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Decision 2.0 Nox 4B · CPU](Nox.md) | 103/132 (#20) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [GLiClass v4 2B · BF16 MPS](GLiClass2BMps.md) | 103/132 (#20) | — | 186/192 (#11) | 28/48 (#9) | — | 76/80 (#7) | 85/96 (#7) | 86/96 (#6) | — | 359/512 (#7) | — | — | — |
| [Liquid d1-3B · CPU](Liquid3.md) | 101/132 (#22) | 16/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Noma · CPU](Noma.md) | 98/132 (#23) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 lite · CPU](D3lite.md) | 95/132 (#24) | 19/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 lite · Q8 Metal](D3liteQ8Metal.md) | 94/132 (#25) | — | 170/192 (#12) | 14/48 (#13) | — | 71/80 (#10) | 71/96 (#8) | 70/96 (#8) | 231/512 (#9) | 338/512 (#8) | 449/768 (#5) | 88/128 (#10) | — |
| [D3 lite · macOS CPU](D3liteMacos.md) | 94/132 (#25) | 19/24 | 168/192 (#13) | 14/48 (#13) | 14/32 (#3) | 71/80 (#10) | — | — | 229/512 (#10) | — | 439/768 (#8) | 88/128 (#10) | — |
| [Decision 2.0 Sol 2B · CPU](Sol.md) | 93/132 (#27) | 19/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Vela 2.0 0.8B · CPU](Vela08.md) | 79/132 (#28) | 14/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Decision 2.0 Eos 0.8B · CPU](Eos.md) | 77/132 (#29) | 19/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Decision 2.0 Eos 0.8B · Q8 Metal](EosQ8.md) | 77/132 (#29) | 19/24 | — | — | — | — | — | — | — | — | — | — | — |
| [D3 edge · CPU](D3edge.md) | 74/132 (#31) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Decision 2.0 Kai 0.6B · CPU](Kai.md) | 70/132 (#32) | 16/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Vela 2.0 0.3B · CPU](Vela03.md) | 65/132 (#33) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Vela 2.0 0.3B · macOS CPU](Vela03Macos.md) | 65/132 (#33) | 18/24 | 128/192 (#14) | 18/48 (#12) | 0/32 (#4) | 64/80 (#12) | 71/96 (#8) | 49/96 (#9) | 112/512 (#12) | 113/512 (#9) | 151/768 (#12) | 93/128 (#8) | — |
| [GLiNER2.5-multi-Decide · CPU](GLiNER.md) | 59/132 (#35) | 12/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Vela 3.0 fast · decision only · CPU](Vela3Fast.md) | 57/132 (#36) | 18/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Laya multilingual · CPU](Laya.md) | 56/132 (#37) | 10/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Julia-1 · CPU](Julia.md) | 52/132 (#38) | 11/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Liquid d1-omni-600M · CPU](Omni.md) | 51/132 (#39) | 16/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Indecis · untrained open mode · CPU](Indecis.md) | 44/132 (#40) | 11/24 | — | — | — | — | — | — | — | — | — | — | — |
| [ModernJEV-Decide-Preview · CPU](ModernJEV.md) | 42/132 (#41) | 8/24 | — | — | — | — | — | — | — | — | — | — | — |
| [Muose-50M-Decision · CPU](Muose.md) | 41/132 (#42) | 10/24 | — | — | — | — | — | — | — | — | — | — | — |
| [BGE v2-m3 · INT8 CPU](BGEPassage.md) | — | — | — | — | — | — | — | — | — | — | — | — | — |
| [D3 lite + BGE tie-break · CPU](D3liteBGE.md) | — | — | — | — | — | — | — | — | — | — | — | — | — |
| [D3 lite · CPU passage session](D3litePassage.md) | — | — | — | — | — | — | — | — | 229/512 (#10) | — | 443/768 (#7) | 88/128 (#10) | — |
| [Jev 1.14 + BGE tie-break](Jev114BGE.md) | — | — | — | — | — | — | — | — | — | — | — | — | — |
| [Jev 1.14 · HTTP API](Jev114.md) | — | — | — | — | — | — | — | — | — | — | 394/768 partial | 0/128 scored, attempted | — |
| [Production router · private replay](FacadeRouterReplay.md) | — | — | — | — | — | 28/80 (#13) | 24/96 (#10) | 24/96 (#10) | — | — | — | — | — |
| [Qwen3-4B Instruct 2507 · Q8 Metal · generated JSON, prompt v2](QwenToolPolicyV2.md) | — | — | — | — | — | — | — | — | — | — | — | — | 3/10, 6/6, 7/18 |

Tool /24 is provisional agreement with agent-authored first-tool proposals, not routing accuracy; it has no rank. Passage scores are rotation 0 (128 pools × decisions); the four-rotation Jev export and the ranking methods are on each model page and in [other benchmarks](../other-benchmarks.md). Generated regularly by `scripts/build-full-results.py`.
