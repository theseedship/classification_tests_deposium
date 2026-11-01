# Facade routing, advanced tier

**96 synthetic closed-choice cases, 48 FR/EN request families, 8 options.**
Frozen on 1 November 2026 before any candidate prediction. Cases SHA-256
`42364fed544e842a02f68314242b767a7c3fae0dde8505bd66499063930337f3`.
Same categories, question and option rotation as the [easy tier](../facade-routing-v1/README.md);
the requests are harder to route.

| Category | Families | Kinds |
|---|---:|---|
| Each of the seven tool categories | 6 | 2 implicit (no category word, business jargon), 2 lexical traps (a word that evokes another category, such as "knowledge graphs" in a plain search), 1 near miss between neighbouring categories, 1 informal or misspelt request |
| None of these | 6 | 3 out of scope despite document vocabulary, 3 too vague |

Splits per category: one TRAIN, one calibration and four TEST families
(16 / 16 / 64 cases); each answer position holds 12 cases. Requests and
references were written without access to any router rule or keyword list.
References are agent-authored and pending human review.

```bash
python3 scripts/build-facade-routing-pack.py --check
python3 -m deposium_bench validate-cases --dataset datasets/facade-routing-advanced-v1/cases.jsonl
```
