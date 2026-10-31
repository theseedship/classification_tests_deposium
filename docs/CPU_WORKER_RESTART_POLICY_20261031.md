# CPU worker restart policy after a per-call timeout

**Fixed on 31 October 2026, before any further CPU campaign.** Applies to the
`d3` and `vela2` adapters. It changes how the adapter continues after one case
exceeds the per-call timeout; it changes no reference, scorer, prompt,
projection, memory guard or timeout value.

## Before

A single inference timeout called the adapter's fail-closed path: the worker
was stopped and every later case of the campaign received a cached `timeout`
without being attempted. [D3 nano's first capability attempt](D3_NANO_MACOS_RESULTS_20261031.md)
shows the effect: one measured timeout, 149 unattempted cases.

## From this policy

| Event | Behavior |
|---|---|
| A case exceeds the per-call timeout | Its outcome is `timeout` with `raw_output.cached_failure = false` and `worker_restart_scheduled = n`; the worker process is stopped |
| Next case | The adapter relaunches the worker (same assets, pins and guards as at initialization; the host floor is checked again) and records `relaunch_ms`; successful cases carry `raw_output.worker_generation` (0 before any restart) |
| Fourth timeout in one campaign | The restart budget (`MAX_WORKER_RESTARTS = 3`) is exhausted: the adapter fails closed as before and later cases are cached `timeout` with `cached_failure = true` |
| Memory or protocol errors | Unchanged: fail closed immediately |

The adapter's provenance records `restart_policy` and the list of
`worker_restarts` (sequence, reason, relaunch time). The public CPU pack
exporter reports `attempts.worker_restarts` beside attempted and cached
counts, so a reader can tell measured timeouts from unattempted cases.

## What it does not change

- Denominators: every case keeps its archived status; a timeout is a
  retained unsuccessful outcome, not a dropped case.
- Identity: a restarted worker runs the same verified assets, runtime lock and
  profile; the campaign remains one observation. Restarts are reported.
- Timeouts themselves: each CPU protocol fixes its per-call value before the
  first prediction (60 s for context/tool/physics so far; 300 s for D3 nano's
  capability pack by amendment; D3 mini's protocol will fix its own value).
