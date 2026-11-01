# Facade routing v1

**80 synthetic closed-choice cases, 40 FR/EN request families, 8 options.**
Frozen on 31 October 2026 before any candidate prediction, for the
[facade routing comparison](../../docs/FACADE_ROUTING_DESIGN_20261031.md)
(issue #56). Cases SHA-256 `03f30a621298ecb45f78aefc50e048b6737024245a49a347dd982e28bca72c18`.

A case shows one request sent to a document assistant and asks which tool
category should handle it: search, analyse, visualise, graph, evaluate,
process, system, or none of these. Requests and references were written without
access to any router rule. References are agent-authored and pending human
review.

| Category | Families | Kinds |
|---|---:|---|
| Each of the seven tool categories | 5 | 2 direct, 2 paraphrases, 1 refused alternative or two-step request |
| None of these | 5 | 3 out of scope, 2 too vague |

Splits per category: one TRAIN, one calibration and three TEST families
(16 / 16 / 48 cases). Options are rotated so the reference is spread across
the eight positions. The specification is [`specs.json`](specs.json); the
cases are rebuilt deterministically:

```bash
python3 scripts/build-facade-routing-pack.py --check
python3 -m deposium_bench validate-cases --dataset datasets/facade-routing-v1/cases.jsonl
```

Harder tiers with the same categories: [advanced](../facade-routing-advanced-v1/README.md)
and [complex](../facade-routing-complex-v1/README.md).

A correct choice shows agreement with an authored category on short synthetic
requests. It does not qualify a production router, tool execution or answer
quality.
