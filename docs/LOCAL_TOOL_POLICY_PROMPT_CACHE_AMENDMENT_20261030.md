# Amendment: disable the native host prompt cache

**Fixed on 30 October 2026, after the partial held-out attempt and before any
further prediction.** Executed the same day; see the
[results](LOCAL_TOOL_POLICY_HELDOUT_RESULTS_20261030.md), which also qualify the
"byte-identical" wording below (generated content identical; volatile HTTP
metadata and the clock-derived episode budget differ). This amends the
[supervised session protocol](LOCAL_TOOL_POLICY_NATIVE_PROTOCOL_20261030.md) and
applies to every later attempt under the
[held-out protocol](LOCAL_TOOL_POLICY_HELDOUT_PROTOCOL_20261030.md). It changes
one native server argument. It changes no reference, dataset, prompt, scorer,
guard, memory ceiling or time budget.

## Observed cause

The first held-out attempt ([results](LOCAL_TOOL_POLICY_V2_RESULTS_20261030.md))
stopped at the RSS guard: sampled process-group RSS grew monotonically across
requests (about 5.6 → 6.0 → 6.7 → 7.6 → 8.2 GiB) and reached 8,193 MiB at the
nineteenth case. The owned server's log explains the growth. The pinned
llama.cpp `efe3626b` enables a **host prompt cache** by default
(`cache_ram_mib = 8192`); at startup it logs
`prompt cache is enabled, size limit: 8192 MiB` and, on each new task, saves
the idle slot's KV state to host memory (`updating prompt cache`, 40 times in
the held-out log, 26 times in the TRAIN v2 log). Its 8 GiB limit coincides with
the declared 8 GiB RSS ceiling, so the guard fires first.

The candidate never benefits from that cache: every request is sent with
`cache_prompt: false`, and each case's projection is a fresh prompt. The growth
is retained server state, not model work.

## Amendment

| Setting | Before | From this amendment |
|---|---|---|
| Native argument | default (`--cache-ram 8192`, implicit) | `--cache-ram 0` (host prompt cache disabled) |
| Verification | none | the owned log must contain `prompt cache is disabled` and must not contain `prompt cache is enabled`; otherwise the attempt fails before any quality call, as for partial Metal offload |
| Receipt | — | `envelope.host_prompt_cache_mib = 0` and `host_prompt_cache = "disabled_observed_in_native_log"` |
| Everything else | 4096 context, 256 output tokens, seed 42, temperature 0, one slot, 20 s per call, 600 s session, 8 GiB RSS plus 8 GiB reserve, 16 GiB admission, four technical controls, prompt v2 | unchanged |

Archives produced before this amendment (TRAIN v1 `…-001`, TRAIN v2 `…-002`,
held-out `…-heldout-…-001`) ran with the default cache and stay as recorded;
their receipts have no `host_prompt_cache_mib` field.

## Neutrality control, then attempt 002

1. **TRAIN v2 again under the amended launcher** (a third TRAIN archive). With
   seed 42 and temperature 0 on the same model, runtime and prompt, every
   generated response must be byte-identical to the second TRAIN archive and
   every per-case outcome must match. Any difference means the amendment is
   not generation-neutral and must be reported before step 2.
2. **Held-out attempt 002** on the unchanged 24-case pack and manifest. The
   first attempt's archive and aggregate are retained; the second attempt is
   reported beside it, with its own statuses and stop reason if any.
3. No prompt revision, reference change or further run after seeing the
   attempt 002 outcomes.

This amendment addresses a runtime envelope outcome. It does not predict the
candidate's quality on the six cases the first attempt never reached, and it
does not raise any ceiling.
