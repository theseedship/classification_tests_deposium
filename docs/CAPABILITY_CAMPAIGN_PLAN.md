# Progressive capability-choice campaign

**Status: planned, not executed — 29 October 2026.** Start with seven selected
model/runtime candidates, rather than rerunning the entire historical inventory.
The [machine-readable sequence](../plans/capability-choice-v1-sequence.json)
pins the dataset, selection evidence, model identities, asset manifests, order
and calibration canary. Reading it performs no inference, download or service action.

The question is whether our strongest measured candidates retain their usefulness
on capability/tool-set proposals, arguments and fixed-observation next steps,
and how much smaller a useful candidate can be. These experiments do not qualify
free-form tool generation, executable arguments or a complete MCP loop.

## Initial cohort and order

Selection uses the highest **historical correct/132** within known recorded
size classes. Those totals mix train, calibration and test; separate test/66
and documentary/76 results are shown. They are exploratory observations with
agent-authored references, not general model rankings or predictions of new scores.
Unknown-size candidates are not silently assigned to a size class.

| Order | Wave | Size class | Selected observation | Historical all /132 | Test /66 | Text /76 | Purpose |
|---:|---|---|---|---:|---:|---:|---|
| 1 | A | 8–10B | D3 Flash, nominal 9B, Q8 Metal | 124 | 61 | 72 | Practical strong reference |
| 2 | A | ~27B | Historical D3, nominal 27B, Q4 Metal | 128 | 65 | 73 | Larger comparison under memory admission |
| 3 | A | 8–10B | GLiClass v4 9B BF16/MPS | 117 | 63 | 70 | Different-family challenger; stronger historical test count than Flash |
| 4 | B | 3–5B | D3 mini, 4.539B backbone, CPU | 119 | 60 | 71 | First reduction in size from the strong references |
| 5 | B | 1–3B | D3 nano, 2.213B backbone, CPU | 117 | 61 | 68 | Test whether the smaller candidate retains useful quality |
| 6 | B | 0.5–1B | D3 lite, 0.853B backbone, CPU | 95 | 50 | 64 | Strongest measured known-size sub-1B candidate |
| 7 | B | <0.5B | Vela 2.0 0.3B, 0.309B declared checkpoint, CPU | 65 | 37 | 52 | Smallest selected quality baseline |

Wave A establishes strong references and a family comparison. Wave B then
descends through the selected size classes. This order is fixed before new
predictions. Do not remove a technically admitted candidate because its test
score is disappointing. Diagnose technical failures separately; any later
cohort or profile change gets a new recorded version.

The historical 27B is **not D3 Ultra/Turbo**, and it is not a truth oracle.
Flash Q8 versus 27B Q4 changes checkpoint, size and quantization together;
their difference cannot isolate the causal effect of parameter count.

The D3 counts describe checkpoint/backbone scope, not text-only active parameters;
some include vision weights and exclude a separate readout. GGUF sizes are
nominal model classes rather than verified converted parameter counts. See the
[metadata](leaderboard/model-metadata.json) and [full results](RESULTS.md).
The [pinned Mini card](https://huggingface.co/vllm-sr/d3-mini/blob/a475367de0d8133a3c1a2a0dc12303d89cfa2ab4/README.md)
also identifies its vision-inclusive parameter scope. The
[GLiClass publisher card](https://huggingface.co/knowledgator/gliclass-v4-9b)
identifies its 9B label-scoring family; publisher benchmark scores are not
substitutes for this repository's observations.

## Resource context, not minimum requirements

| Observation | Historical measurement | Scope and limitation |
|---|---|---|
| D3 Flash Q8 | 9.39 GiB RSS | Sampled native process-group peak over context + tool session, Apple M5 Pro |
| Historical D3 27B Q4 | 18.81 GiB RSS | Same session scope; not total unified-memory use |
| GLiClass 9B | 16.75 GiB GPU allocation; 1.14 GiB RSS | Two different measurements from the context phase; **never add them** |
| D3 mini | 7.55 GiB RSS | Historical Linux/WSL CPU worker peak |
| D3 nano | 3.39 GiB RSS | Historical Linux/WSL CPU worker peak |
| D3 lite | 1.80 GiB RSS | Historical Linux/WSL CPU worker peak |
| Vela 2.0 0.3B | 1.17 GiB RSS | Historical Linux/WSL CPU worker peak |

These short-input observations are not memory floors, predictions for the new
catalogues or controlled CPU/Metal/MPS comparisons. The expanded inputs can
change both latency and memory. A 64 GiB host does not guarantee available
memory. Admit one candidate at a time, retain its fixed guards and at least the
existing 8 GiB reserve or any stricter profile requirement. Release workers
between phases and verify their termination.

Do not multiply old short-input medians into a promised campaign duration.
If a total-time envelope needs measurement, use calibration first, record its
derivation and freeze the numeric budget before full-pack predictions. Retain
per-call timeouts; never raise limits in response to test failures.

## Preparation before the first forward

1. Validate the corpus and hashes without weights. Freeze dataset, plan and
   code revisions; use the exact model revisions and asset manifests in the sequence.
2. Prepare the selected platform-specific runtime and observe its actual device,
   precision, helper, tokenizer/readout and binary/library hashes. A profile's
   presence or an old session manifest does not establish current readiness.
3. Prepare a supervised session for the new dataset. The
   [native pilot](../scripts/run-native-pilot.py) now accepts an explicit
   `--dataset` for one campaign and preserves its historical 132+Mastra default.
   It snapshots validated input bytes before model work. Validate the selected
   model/session and lifecycle guards before using it for a real campaign.
4. Prepare Wave B deliberately: the historical CPU locks contain Linux-specific
   requirements. A macOS port needs an isolated, newly pinned runtime and native
   helper/encoding checks. Alternatively, execute the original WSL environment
   and label that platform. Neither is a previously qualified Mac environment.
5. Validate native input encodings for **all 192 cases**, including the longest
   expanded inputs. No silent truncation or backend/model fallback is allowed.
   An unsupported input retains that status; do not shrink the benchmark.

The first Flash Q8 execution envelope and preparation method are fixed in the
[native protocol](CAPABILITY_NATIVE_PROTOCOL_20261029.md). Its 18 GiB RSS
ceiling is stricter than the historical 20 GiB ceiling, with the same 8 GiB
reserve; this is a recorded pre-prediction resource decision. The bounded
vocabulary-only helper reuses native preparation without a decode/forward.

A new GGUF conversion, quantization, model revision, helper/runtime build or
device is a separate observation. Keep it distinct from the historical CPU
selection anchor and rerun the old anchor as well as the new pack. Preserve
cross-platform portability in interfaces and profiles without assuming numeric
or performance parity between Mac and WSL.

## Per-candidate phases

Use a new archive for every attempt and phase. Keep annotations outside the
candidate-visible projection and preserve raw outputs, source hashes, native
encoding/forward evidence, timing boundaries and failures.

| Phase | Work | Gate or interpretation |
|---|---|---|
| Technical canary | 12 calibration cases: first lexical calibration family in each of the three tracks, all four language/catalogue variants | Correct identity/device, complete input and valid decision format; **no accuracy threshold** |
| Optional calibration | Up to all 48 calibration cases if needed to establish a resource envelope or freeze parameters | Never use test cases or change references to make a model pass |
| Historical anchor | New full 132-case run under the selected current runtime | Report test/66 separately; preserve the old archive and score |
| Complementary campaign | New full 192-case run | Report test/96, all-case coverage and every declared task/language/catalogue group |

The canary uses `ccv1-selection-02`, `ccv1-arguments-02` and
`ccv1-observations-02`; its twelve exact IDs are in the sequence file. It covers
only three families, not all task types, answer positions or maximum lengths.
A structurally valid wrong choice must not fail this technical gate.
Canary/calibration repeats never inflate the 192-case quality denominator.

Freeze prompts, profiles, order, budgets and analysis settings before full-pack
predictions. Start full phases with a fresh worker/session and record loading,
first-call and subsequent timings separately. Earlier phases may warm OS/GPU
caches, so a new process does not prove a completely cold machine.

Complete both full packs for each technically admitted candidate. Do not stop
based on test accuracy. A deterministic resource stop produces a partial archive
with missing cases retained in the full denominator. `unsupported`, `missing`,
`error`, `timeout` and technical `abstain` remain distinct from semantic
clarification or stopping choices. Resume/rescore retains the original archive;
older archives may require an explicit derived rescore after scorer changes.

The seven-candidate plan represents **1,344 new-pack decisions + 924 anchor
decisions**, plus 84 canary decisions if each canary is run once. These are
planned volumes, not executed calls. Calibration repeats and diagnostics are
additional archived work. No API or download budget is spent by this plan.

## Compare outcomes without overstating the evidence

- Pair different models on matching IDs **within the same pack**, retaining
  improvements, regressions and status changes. Old and new families are not
  paired with each other; do not convert 324 cases into one unexplained score.
- Pair compact/expanded outputs within each new family and language, and FR/EN
  outputs within each family and catalogue view. Retain correctness improvements,
  regressions and status transitions; group uncertainty by family.
- Keep all-case and held-out results separate: old test/66 and new test/96.
  Report selection, arguments/dependencies and observation-next-step tracks;
  include use cases, FR/EN, and compact/expanded views with their denominators.
- New-pack variants represent 48 families, including 24 test families, not 192
  independent tasks. Any interval/bootstrap must group by family. FR/EN
  agreement is separate from correctness, with translations still pending review.
- The expanded view changes length, distractors and absolute card positions.
  Call it a catalogue-view comparison, not a pure effect of tool count.
- Report initialization and inference latency separately, native input lengths,
  valid/scored coverage, RSS and GPU allocation with their actual scopes.
  Do not infer production latency or cross-hardware superiority.
- The 27B's agreement is not ground truth. Empirical difficulty and adaptive
  model assignment require independent task references and replay comparisons;
  this proposal-only corpus does not qualify end-to-end execution success.

## Optional additions after the initial cohort

Flash Q4 can test the quantization/memory tradeoff against Flash Q8 as a separate
arm. Vela3-fast can supply another small-family control, but its decision-only
backbone was not the historical class winner; specialized Vela span/router
adapters are not covered. Eos Q8 is an optional native technical control, not the
chosen sub-1B quality representative.

Keep Ultra/Turbo, GLiClass 27B and other new releases outside this initial queue
until their model/runtime/resource audits are complete. This avoids changing
weights, runtime and task coverage simultaneously while testing the initial
size/quality intuition. No new inference is claimed here.
