# Deployment variants: D3 mini Q4 on Metal and D3 Flash 4-bit on Uzu

**1 November 2026 — how to serve a small D3 decision model on the Mac with
less memory.** Three deployments on the same nine packs, every answer `ok`:

- **D3 mini Q8** (5.2 GB file) and **D3 mini Q4_K_M** (3.7 GB) as ggml-org GGUF
  on upstream llama.cpp Metal ([protocol](D3_SMALL_GGUF_GPU_PROTOCOL_20261101.md));
- **D3 Flash 4-bit** (9B, INT4 YAQA, 4.3 GB), Mirai's
  [`trymirai/d3-flash-M`](https://huggingface.co/trymirai/d3-flash-M) pack on the
  official Uzu 0.6.15 engine ([protocol](UZU_D3_FLASH_M_PROTOCOL_20261101.md)).

[Aggregate](evidence/deployment-variants-20261101/analysis.json) · [All results](RESULTS.md#deployment-variants-q4-and-uzu)

## Scores, speed and memory

Correct / all (TEST); median call time on the same host.

| Pack | D3 mini Q8 · Metal | D3 mini Q4 · Metal | D3 Flash 4-bit · Uzu | D3 Flash Q8 · Metal (published) |
|---|---:|---:|---:|---:|
| Facade routing, easy /80 | 79 (47) · 161 ms | 79 (47) · 167 ms | 78 (46) · 110 ms | — |
| Facade routing, advanced /96 | 94 (62) · 162 ms | 94 (62) · 170 ms | 92 (61) · 111 ms | — |
| Facade routing, complex /96 | 92 (60) · 164 ms | 93 (61) · 169 ms | 88 (56) · 112 ms | — |
| Context /132 | 119 (60) · 104 ms | 117 (59) · 107 ms | 118 (61) · 74 ms | 124 (61) |
| Capability /192 | 192 (96) · 325 ms | 192 (96) · 338 ms | 192 (96) · 263 ms | 192 (96) |
| Physics /48 | 39 (32) · 104 ms | 36 (30) · 111 ms | 40 (32) · 73 ms | 39 |
| Passage relevance v2 /512 | 406 (200) · 110 ms | 406 (200) · 112 ms | 386 (189) · 85 ms | — |
| Human confirmation, 9 options /90 | 71 (47) · 168 ms | 69 (46) · 173 ms | 71 (47) · 120 ms | — |
| Human confirmation, 8 options /90 | 83 (55) · 162 ms | 81 (54) · 165 ms | 85 (58) · 107 ms | — |
| **Sampled process RSS** | **5.3–5.4 GiB** | **3.9–4.0 GiB** | **4.2 GiB** | ~9.4 GiB |

## Reading

- **D3 mini Q4 keeps D3 mini Q8's answers** (identical on 94–100% of cases per
  pack; 507/512 on relevance) and scores the same within 0–3 cases, for
  **1.4 GiB less memory**. It is not faster on Metal.
- **D3 Flash 4-bit on Uzu is the fastest** (about 30% shorter calls than D3
  mini on llama.cpp) in about the same memory as D3 mini Q4. It matches or beats
  D3 mini on context, capability, physics and the human-confirmation packs,
  and is a little weaker on facade routing (−1 to −4 cases) and passage
  relevance (386 vs 406).
- **The 4-bit Flash pack costs Flash some accuracy on context** (118 vs 124/132
  for D3 Flash Q8 on Metal) while matching it on capability and physics.
- For on-device routing with limited memory, D3 mini Q4 and D3 Flash 4-bit on
  Uzu are both viable at about 4 GiB; the choice depends on whether routing
  accuracy (D3 mini) or call latency (Uzu) matters more.

## Boundaries

A deployment comparison: model size, quantization method and engine change
together, so no single factor is isolated. Uzu does not report its compute
backend (Metal requested, not observed), and its stock CLI fetches an online
catalogue at start (`egress_isolated:false`). Uzu inputs were prepared by the
pinned `hanashi` encoder; on the easy facade pack their token counts equal the
llama.cpp preparation of the same requests. One pass per case; RSS is the
sampled process group, unified memory, not a GPU allocation. References are
agent-authored and pending human review.
