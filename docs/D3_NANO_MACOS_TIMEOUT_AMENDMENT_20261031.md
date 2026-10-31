# Amendment: per-call timeout for D3 nano's capability pack on macOS CPU

**Fixed on 31 October 2026, after the partial first capability attempt and
before any further prediction on that pack.** Executed the same day: attempt
002 collected all 192 cases, 188/192, no timeout, slowest case 64.1 s
([results](D3_NANO_MACOS_RESULTS_20261031.md)). This amends the
[D3 nano macOS CPU protocol](D3_NANO_MACOS_CPU_PROTOCOL_20261030.md) for one
pack of one candidate. It changes one envelope value (the per-call timeout)
and the adapter bound that admits it. It changes no reference, dataset,
prompt, projection, scorer, memory ceiling, thread count or host floor.

## Observed cause

[Attempt 001](D3_NANO_MACOS_RESULTS_20261031.md) used the historical D3 CPU
profile value of **60 seconds per call**, fixed before predictions. The first
42 capability cases answered in 14–53 s; the 43rd exceeded 60 s (60.1 s).
The D3 adapter then failed closed and returned a cached `timeout` for the 149
remaining cases without attempting them. The archive is retained as recorded:
42 scored, 150 `timeout` (one measured, 149 cached), coverage `partial`.

A 2.2B backbone on two CPU threads needs roughly two to four times D3 lite's
6–30 s on the same 4096-token inputs. The 60 s value was never calibrated for
this candidate on this pack; it is an envelope outcome, not a quality result.

## Amendment

| Setting | Attempt 001 | From this amendment |
|---|---|---|
| Per-call timeout, capability pack | 60 s (profile `d3-nano-macos-cpu-v1`) | **300 s** (profile [`d3-nano-macos-cpu-capability-v1`](../profiles/d3-nano-macos-cpu-capability.json), otherwise identical) |
| D3 adapter admitted bound | at most 60 s | at most 300 s; the worker RSS guard (12,288 MiB) and the host floor are checked on every call as before |
| Fail-closed behavior after a timeout | unchanged | **unchanged**: a case exceeding 300 s would again stop the worker and leave later cases unattempted; the aggregate's `attempts` block makes that visible |
| Context, physics, tool observations | 60 s profile | unchanged; they were complete under 60 s and are not rerun |

The 300 s value is a declared ceiling for this pack, chosen as about five
times the slowest completed case; it is not a measured requirement and is
not raised again after seeing attempt 002.

## Order

1. Synthetic control under the new profile (zero scored cases).
2. Capability attempt 002, new archive, same pack bytes and references.
3. Report attempt 002 beside attempt 001; attempt 001 stays published as a
   partial collection. If attempt 002 is also partial, it is reported as
   such; no third attempt follows without a new amendment.

Changing the adapter's fail-closed policy (restart the worker and continue
after a timeout) is a separate, reviewed change and is not part of this
amendment. The same timeout question will arise for D3 mini (4.5B); its
protocol should fix a calibrated per-call value before its first prediction.
