# Facade routing, complex tier

**96 synthetic closed-choice cases, 48 FR/EN request families, 8 options.**
Frozen on 1 November 2026 before any candidate prediction. Cases SHA-256
`389d362dafa7696b3cb4fb18f0d44a1ae98569a1ae661133f7ec9db44b6930d6`.
Same categories and option rotation as the [easy tier](../facade-routing-v1/README.md),
with two differences: the question asks which category the assistant should
use **first**, and some cases show the previous exchange before the new request.

| Category | Families | Kinds |
|---|---:|---|
| Each of the seven tool categories | 6 | 2 multi-step requests (reference: the first step), 2 requests that only make sense with the previous exchange, 1 compound refusal ("no chart, no summary…"), 1 goal stated without the action |
| None of these | 6 | 2 genuinely ambiguous, 2 follow-ups the previous exchange does not resolve, 2 out of scope (one where only the first step is out of scope) |

Splits per category: one TRAIN, one calibration and four TEST families
(16 / 16 / 64 cases); each answer position holds 12 cases. Requests and
references were written without access to any router rule or keyword list.
References are agent-authored and pending human review. A router that only
reads the latest request cannot use the previous exchange; that is part of
what this tier measures.

```bash
python3 scripts/build-facade-routing-pack.py --check
python3 -m deposium_bench validate-cases --dataset datasets/facade-routing-complex-v1/cases.jsonl
```
