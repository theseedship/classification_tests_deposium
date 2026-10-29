# Campaign status and next steps

**Checkpoint: 29 October 2026.** This page describes the public implementation
and reports. References and translations remain agent-authored, pending human
review. Offline checks, model preparation and real campaigns are separate.

| Roadmap item | Completed | Remaining |
|---|---|---|
| Physics baseline | Versioned 48-case pack, exact rational controls, shared analysis, optional Decision3 HTTP adapter; [D3 Flash Q8/Metal](PHYSICS_FLASH_RESULTS_20261029.md) scored 39/48, test 32/36 | Human scientific/linguistic review and cross-model comparisons; hosted Turbo and application-gateway paths have not run |
| Capability cohort | [D3 Flash Q8/Metal](CAPABILITY_FLASH_RESULTS_20261029.md) scored 192/192, test 96/96 | Six candidates in the [frozen seven-candidate sequence](CAPABILITY_CAMPAIGN_PLAN.md); next is historical D3 27B Q4, subject to resource admission |
| Evidence assessment | [Matched Flash comparison](PASSAGE_CLEF_RESULTS_20261029.md): D3 relevance/support/answerability 252/512, 460/768, 122/128; Clef 261/512, 446/768, 109/128; 728/728 physical calls valid per candidate, separate fresh anchors | Human semantic review and new held-out scenarios; rotation controls, ranking/composition and final answers remain separate |
| Executable arguments and episodes | [Experiment design](INTENT_AND_MODEL_ROUTING.md) | Contracts, controlled tool execution, bounded feedback loops, negative controls and real observations are not implemented |
| Clef addition | [Clef Flash Q8/Metal campaign](CLEF_FLASH_RESULTS_20261029.md): context 110/132 (test 59/66), capability 192/192 (test 96/96), physics 41/48 (test 31/36), plus [passage evidence](PASSAGE_CLEF_RESULTS_20261029.md), complete scored coverage | Clef 27B preparation and campaigns need resource admission and a dedicated executable envelope; publisher BF16/PyTorch path remains untested |

The Clef Flash Q8 GGUF route is a separate observation from Cloudflare's
BF16/PyTorch runtime. Clef 27B requires its own admitted execution envelope.
The addition does not reorder or replace the original capability cohort.

## Offline verification at this checkpoint

Python 3.13 on macOS validated the registry, context and physics cases, frozen
capability and passage corpora, and generated public result views. The targeted
native/campaign/scoring suite ran 182 tests: 180 passed and two optional checks
were skipped. No model inference or paid API was part of these checks.

The full macOS suite ran 858 tests with 62 failures, six errors and 75 skips.
A separate snapshot of public base `8b164b8` ran 828 tests with the same 62
failures and six errors, and 74 skips. The failure/error identifiers match;
there is no newly failing identifier. This is not a global PASS or a successful
qualification of skipped dependencies. Linux remains the full-suite reference.

## Resume from this checkpoint

1. Read [the protocol](PROTOCOL.md), [priorities](BENCHMARK_PRIORITIES_20261029.md)
   and the relevant dataset card and dated campaign protocol. Verify the actual
   model, source, binary and helper hashes; the current helper extends the one
   used for the completed physics observation.
2. Validate the public checkout with Python 3.11+ using the README's core
   commands. A core check needs neither weights nor external services.
3. Preserve the completed [Clef Flash observation](CLEF_FLASH_RESULTS_20261029.md)
   and its [original frozen plan](../plans/clef-native-v1.json). The plan retains
   its pre-inference state; results do not rewrite it. No score-based adjustment
   of references, budgets or phase order. Clef 27B remains a separate future run.
4. Continue the original capability sequence only when its next candidate is
   admitted. Resource refusal is a preflight outcome, not a scored model failure.
5. Preserve the completed [D3/Clef matching passage observations](PASSAGE_CLEF_RESULTS_20261029.md)
   and both original frozen plans. Review insufficient-versus-refuted support,
   thematic relevance and conflicting-evidence decisions with human annotators.
   New labels/scenarios require a separate reviewed version, not a rewrite of v1.

There is no need to repeat all 28 historical model/runtime observations.
New dataset/runtime pairs require new campaigns and a fresh context anchor
under their declared protocol. Preserve previous archives; rescoring is a
separate derived operation and does not create new inference or timing.

Weights, runtime installations, budgets and raw archives remain outside Git.
A public clone contains the code, synthetic datasets, protocols and reviewed
aggregates; it does not restore local execution assets or private material.
