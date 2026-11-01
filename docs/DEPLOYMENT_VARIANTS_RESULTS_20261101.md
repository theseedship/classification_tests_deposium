# Deployment variants: Q4 on Metal and D3 Flash on Uzu

**1 November 2026 — how to serve a D3 decision model on the Mac, and how much
the engine matters.** Four deployments on the same nine packs, every answer
`ok`:

- **D3 mini Q8** (5.2 GB file) and **D3 mini Q4_K_M** (3.7 GB), ggml-org GGUF
  on upstream llama.cpp Metal ([protocol](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md));
- **D3 Flash Q4_K_M** (9B class, 6.6 GB), ggml-org GGUF on the same llama.cpp
  Metal runtime (dated amendment of the same protocol);
- **D3 Flash 4-bit** (INT4 YAQA, 4.3 GB), Mirai's
  [`trymirai/d3-flash-M`](https://huggingface.co/trymirai/d3-flash-M) pack on the
  official Uzu 0.6.15 engine ([protocol](UZU_D3_FLASH_M_PROTOCOL_20261101.md)).

All four are full observations in [RESULTS.md](RESULTS.md) (context,
capability, physics, routing tiers, relevance v2, human confirmation; passage
evidence for the GGUF rows) with their own
[model pages](leaderboard/by-model/README.md).

[Aggregate](evidence/deployment-variants-20261101/analysis.json) · [All results](RESULTS.md#deployment-variants-q4-and-uzu)

## Speed: same model, two engines

Three interleaved timing rounds after the main passes; each round starts
every variant once, in a rotated order, with a fresh server per pass. Median
call time (loopback HTTP), median of the three round medians:

| Pack | D3 mini Q8 · Metal | D3 mini Q4 · Metal | D3 Flash Q4 · Metal | D3 Flash 4-bit · Uzu |
|---|---:|---:|---:|---:|
| Context | 106 ms | 109 ms | 199 ms | **75 ms** |
| Facade routing, easy | 163 ms | 167 ms | 291 ms | **111 ms** |
| Sampled process RSS | 5.3 GiB | 3.9 GiB | 6.6 GiB | 4.2 GiB |

- **Uzu runs D3 Flash about 2.6× faster than llama.cpp Metal** (75 vs 199 ms,
  111 vs 291 ms) in **2.4 GiB less memory**, both at 4 bits.
- Round medians stay within 2% of each other, and every round gives exactly
  the same answers as the main pass, for all four variants.
- Uzu Flash is also faster than D3 mini, half its size, on llama.cpp
  (75 vs 106 ms; 111 vs 163 ms).

## Scores

Correct / all (TEST); median call time of the main pass.

| Pack | D3 mini Q8 · Metal | D3 mini Q4 · Metal | D3 Flash Q4 · Metal | D3 Flash 4-bit · Uzu |
|---|---:|---:|---:|---:|
| Facade routing, easy /80 | 79 (47) · 161 ms | 79 (47) · 167 ms | 79 (47) · 292 ms | 78 (46) · 110 ms |
| Facade routing, advanced /96 | 94 (62) · 162 ms | 94 (62) · 170 ms | 94 (62) · 290 ms | 92 (61) · 111 ms |
| Facade routing, complex /96 | 92 (60) · 164 ms | 93 (61) · 169 ms | 91 (59) · 294 ms | 88 (56) · 112 ms |
| Context /132 | 119 (60) · 104 ms | 117 (59) · 107 ms | 122 (59) · 198 ms | 118 (61) · 74 ms |
| Capability /192 | 192 (96) · 325 ms | 192 (96) · 338 ms | 192 (96) · 584 ms | 192 (96) · 263 ms |
| Physics /48 | 39 (32) · 104 ms | 36 (30) · 111 ms | 39 (32) · 197 ms | 40 (32) · 73 ms |
| Passage relevance v2 /512 | 406 (200) · 110 ms | 406 (200) · 112 ms | 381 (187) · 205 ms | 386 (189) · 85 ms |
| Human confirmation, 9 options /90 | 71 (47) · 168 ms | 69 (46) · 173 ms | 73 (49) · 300 ms | 71 (47) · 120 ms |
| Human confirmation, 8 options /90 | 83 (55) · 162 ms | 81 (54) · 165 ms | 86 (58) · 291 ms | 85 (58) · 107 ms |

Human confirmation on TEST: with the explicit ninth option, both D3 Flash rows
ask before 11/12 irreversible actions (D3 mini Q8 and Q4: 9/12), with 0/38
(llama.cpp) and 2/38 (Uzu) false alarms; none asks on hesitation (0/12). With
their own confidence, both detect 22/24 (D3 mini: 18–19/24), AUC 0.88
(llama.cpp) and 0.90 (Uzu).

## Reading

- **Engine.** On the same D3 Flash, Uzu gives the same answer as llama.cpp
  on 1297/1336 cases (97.1%) and is about 2.6× faster. Its losses are small:
  context 118 vs 122, complex routing 88 vs 91; it gains on relevance v2 (386
  vs 381) and physics (40 vs 39). The two 4-bit methods differ (Mirai INT4 YAQA
  vs Q4_K_M), so part of the gap is the weights, not the engine.
- **Quantization.** D3 mini Q4 keeps D3 mini Q8's answers (identical on
  94–100% of cases per pack; 507/512 on relevance) within 0–3 cases, for
  1.4 GiB less memory. It is not faster on llama.cpp Metal.
- **Model size.** D3 Flash is not better than D3 mini on facade routing or
  relevance v2 here, but is better at asking for human confirmation and on
  context (Q4: 122 vs 119).
- **For on-device use with about 4 GiB,** D3 mini Q4 on llama.cpp keeps the
  best routing and relevance scores; D3 Flash on Uzu gives the shortest calls
  and the best human-confirmation detection.

## Boundaries

A deployment comparison: model size, quantization method and engine change
together between columns, except in the engine comparison, where only the
4-bit method also differs. Uzu does not report its compute backend (Metal
requested, not observed), and its stock CLI fetches an online catalogue at
start (`egress_isolated:false`). Uzu inputs were prepared by the pinned
`hanashi` encoder; on the easy facade pack their token counts equal the
llama.cpp preparation of the same requests. Timing covers each engine's local
HTTP call on one Mac, not throughput or batching. RSS is the sampled process
group, unified memory, not a GPU allocation. Two earlier timing launches are
kept locally and not used (see the protocol amendment). References are
agent-authored and pending human review.
