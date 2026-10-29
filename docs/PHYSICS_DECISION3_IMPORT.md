# Physics choices and the opt-in D3 Turbo HTTP adapter

This import adds a separate [48-case physics pack](../datasets/physics-choice-v1/README.md)
and an optional hosted-model adapter. It does not add a scored public campaign,
change the historical 132-case references, or qualify application behavior.
Historical local reports and raw archives are not distributed by this import.

The separate [direct Flash Q8 baseline](PHYSICS_FLASH_RESULTS_20261029.md) now
records 39/48 physics choices, including 32/36 test, with its own pinned native
runtime and archives. The original gateway-backed protocol and hosted Turbo
path remain unexecuted; neither is qualified by that isolated observation.
See the [benchmark priorities](BENCHMARK_PRIORITIES_20261029.md) for the sequence.

## Physics pack

The pack contains 24 synthetic FR/EN families, with 12 calibration and 36 test
cases. Each input supplies the physical law and assumptions. Rational oracles
and independently listed expected values in tests check the authored choices;
scientific and linguistic human review remains pending. The versioned cases
and manifest are preserved byte for byte. They contain no customer documents,
operational snapshots, application source or production measurements.

The two related-contract identifiers already exist in the public benchmark.
They describe possible evaluation links; they neither execute a component nor
document the current private application architecture.

```bash
python3 -m deposium_bench validate-cases --dataset datasets/physics-choice-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_physics_corpus.py' -v
```

## Optional remote inference

The adapter requests `vllm-sr/d3-turbo` at the historical endpoint configured
in the three `profiles/decision3-turbo-api-*.json` profiles. Endpoint availability,
access requirements and pricing have not been requalified by this import.
Before a live campaign, review the provider's current terms and data handling,
prepare an explicit budget and supply `DECISION_API_KEY` through the environment.
Never place its value in a profile, command argument, notebook or report.

Profiles limit requests, reserved input tokens, request size, interval and
timeout. A durable local ledger survives relaunches; use a new ledger for a new
experiment. There are no retries, redirects or network calls on import or
initialization. Ordinary tests use a fake HTTPS transport, with no real API call.
Remote tool-proposal observations additionally require explicit `--allow-remote`.

Every successful response must identify the requested model, revision and
model SHA-256. These are provider declarations for a mutable service, not an
independent attestation or a guarantee of bitwise reproducibility. Choice
probabilities and confidence do not establish semantic truth.

The adapter shares the current bounded Jev transport, budget helper, candidate
input projection and campaign scorer. No application router is copied.
New scorer fingerprints include the physics oracle dependency; existing
archives and their fingerprints remain unchanged.
