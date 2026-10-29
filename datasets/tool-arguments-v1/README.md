# Executable argument and artifact-binding fixtures v1

**Four synthetic FR/EN training cases in two families.** This is the initial
offline execution slice for
[#11](https://github.com/theseedship/classification_tests_deposium/issues/11).
The first synthetic lookup actually runs and returns an artifact. A scripted
candidate then proposes one summation call, which must consume that exact
artifact with the matching column, unit and permitted scope. The guarded sum
actually runs when its arguments pass the checks.

This is **harness-control evidence**, with zero real-model cases and zero
held-out cases. It is neither a live MCP integration nor a complete adaptive
episode. References and translations are agent-authored pending human review;
expert forms are not a prerequisite for running these automatic checks.

## Cases and independently authored results

| Family | Supplied synthetic values | Unit | Authored result | Variants / split |
|---|---|---|---:|---|
| `tool-arguments-family-001` | 10, 15, 35 in column `amount` | EUR | 60 | FR/EN, train |
| `tool-arguments-family-002` | 2, 3, 7 in column `mass` | kg | 12 | FR/EN, train |

The reference literals follow the stated integer arithmetic:
`10 + 15 + 35 = 60` and `2 + 3 + 7 = 12`. They are declared separately from
the tool runtime and candidate outputs. A controlled tool never reads a case's
reference assertions to decide what value to return.

There are **four train, zero calibration and zero test cases**. A family's
translations, synthetic document/table identity and reference stay together.
Both families use the same lookup-to-sum operation pattern, which also appears
in earlier training controls. Two tables do not establish two independent
reasoning algorithms or generalization to unseen structures. No result on
these exposed fixtures may be reported as a held-out model score.

The data, dataset IDs and scope IDs are entirely synthetic. No private
documents, conversations, real tenant/user metadata, application source audit
or operational snapshot was copied into this pack. The
[manifest](manifest.json) records byte hashes, family identities, splits,
provenance, reference status and control-profile/recording hashes.

## Task input and recorded proposals

The contract is `bench.tool-arguments` in the existing `deposium.case/v1`
envelope, with pack `PRODUCT` as an existing grouping key. This grouping does
not qualify product quality. The source input contains a version, synthetic
request, permitted scope and bounded integer table. The execution adapter
projects the request, allowed interface and **actual lookup observation** to
the candidate. References, rationales, family/split labels and document
annotations remain outside that task content.

The control profile uses `adapter: fixture_arguments`,
`qualification: harness_control` and `model: null`. Its recordings contain only
the proposed `fixture.sum` call and literal arguments. They contain no
precomputed tool-execution receipts or candidate-supplied success flags.

The first artifact identifier is content-addressed:

```text
artifact: + SHA256(UTF8(canonical JSON of {scope_id, dataset}))
```

Canonical JSON sorts keys, uses compact `,` and `:` separators,
`ensure_ascii=true`, and rejects non-finite JSON. The recorded controls use
the resulting literal ID. The harness does not replace a symbolic placeholder
with an actual artifact on behalf of the candidate. FR/EN variants with the
same table and scope share their content ID; the runtime store remains local
to the case. Knowing an ID does not grant scope or access.

The [versioned contract](../../docs/TOOL_ARGUMENTS_CONTRACT_V1.md) defines the
input/output boundary, argument checks, receipt provenance and metric scope.

## What passes and fails

The shared exact scorer checks the selected tool, argument validity, artifact
binding, actual execution status, integer result and unit. Separate diagnostic
metrics retain tool, argument, dependency, execution and result denominators.
One total cannot hide a correct tool name with incorrect values or bindings.
Tool-call counts come only from validated retained receipts. Missing or
inconsistent traces stay explicit; they do not establish a zero-call execution.

Empty proposals, extra or missing fields, wrong column/unit/scope, invalid
types, invented or stale artifact IDs, and candidate-supplied execution claims
cannot certify a successful call. A failed guard blocks the summation. The
archive still retains the proposal and actual first-step observation;
unsuccessful cases are not removed from the total. Technical `unsupported`,
`missing`, `error`, `timeout` and `abstain` remain distinct.

The first operation is fixed by this fixture. This slice tests a response-to-
argument binding and one next-call proposal, not arbitrary workflow discovery,
retries or stopping. Bounded feedback is covered by the separate
[#12 episode fixture](../tool-episodes-v1/README.md).
Real-model structured-output paths remain separately unqualified.

## Validate and execute the control

Use Python 3.11+ from the repository root, without weights or services:

```bash
python3 -m deposium_bench validate-cases \
  --dataset datasets/tool-arguments-v1/cases.jsonl
python3 -m unittest discover -s tests -p 'test_tool_arguments.py' -v
python3 -m deposium_bench run \
  --dataset datasets/tool-arguments-v1/cases.jsonl \
  --profile profiles/tool-arguments-control.json \
  --output results/tool-arguments-control-001
```

Choose a new archive directory. Validation should report four valid training
cases without execution or inference. The explicit control run executes the
bounded local Python fixture tools, records their actual observations and
should pass all four cases as `harness_control`. It invokes no model, paid API,
network tool or application service. A synthetic execution receipt is not
evidence that a production tool or integration is available.

The standard campaign archive retains source/profile hashes, proposals,
actual receipts, input-projection hashes, scores and its integrity seal.
A derived rescore reads those retained records and must not run the tools
again. Preserve the original archive; changing source or fixture definitions
requires a new run or explicit derived rescore under the new fingerprint.
