# Facade routing: easy, advanced and complex tiers

**1 November 2026 — the production router (private replay), Vela 2.0 0.3B on
CPU and D3 lite, nano and mini as Q8 on Metal, on three frozen tiers of the
same eight-category routing task.** Every answer was `ok`. References are
agent-authored, written without access to any router rule, and pending human
review.

[Easy tier results](FACADE_ROUTING_RESULTS_20261101.md) ·
Packs: [easy](../datasets/facade-routing-v1/README.md),
[advanced](../datasets/facade-routing-advanced-v1/README.md),
[complex](../datasets/facade-routing-complex-v1/README.md) ·
Aggregates: [easy, Metal rows](evidence/facade-routing-tiers-20261101/easy-metal.json),
[advanced](evidence/facade-routing-tiers-20261101/advanced.json),
[complex](evidence/facade-routing-tiers-20261101/complex.json) ·
[All results](RESULTS.md#facade-routing-harder-tiers)

## Scores by tier

Correct / all (TEST).

| Candidate | Easy /80 (48) | Advanced /96 (64) | Complex /96 (64) |
|---|---:|---:|---:|
| D3 mini · Q8 Metal | 79 (47) | 94 (62) | 92 (60) |
| D3 nano · Q8 Metal | 75 (44) | 86 (59) | 79 (49) |
| D3 lite · Q8 Metal | 71 (40) | 71 (51) | 70 (41) |
| Vela 2.0 0.3B · macOS CPU | 64 (34) | 71 (53) | 49 (24) |
| Production router · private replay | 28 (10) | 24 (20) | 24 (17) |

The tiers separate the candidates where the easy tier could not: D3 mini stays
above 92/96, D3 nano loses ground on the complex tier, and Vela 2.0 0.3B drops
to half on it. The router stays near a quarter on every tier.

## Where each candidate breaks

Advanced tier, correct / cases per kind:

| Candidate | Implicit /28 | Lexical trap /28 | Near miss /14 | Informal /14 | Out of scope /6 | Too vague /6 |
|---|---:|---:|---:|---:|---:|---:|
| D3 mini | 28 | 28 | 14 | 14 | 6 | 4 |
| D3 nano | 23 | 25 | 14 | 14 | 6 | 4 |
| D3 lite | 16 | 24 | 7 | 14 | 6 | 4 |
| Vela 2.0 0.3B | 14 | 23 | 12 | 12 | 6 | 4 |
| Router | 0 | 6 | 4 | 7 | 4 | 3 |

Complex tier:

| Candidate | First step /28 | Previous exchange /28 | Compound refusal /14 | Goal only /14 | Ambiguous /4 | Vague follow-up /4 | Out of scope /4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D3 mini | 28 | 27 | 13 | 13 | 4 | 3 | 4 |
| D3 nano | 27 | 22 | 11 | 9 | 3 | 4 | 3 |
| D3 lite | 25 | 18 | 10 | 5 | 4 | 4 | 4 |
| Vela 2.0 0.3B | 21 | 14 | 4 | 4 | 4 | 2 | 0 |
| Router | 5 | 8 | 1 | 2 | 2 | 4 | 2 |

- **Requests without the category word** (implicit, goal only) are where the
  small models differ most: D3 mini gets them, D3 lite gets about half, the
  router none on the advanced tier.
- **Refusals** ("no chart, no summary…") need language understanding: the
  router scores 1/14 on compound refusals.
- **Previous exchange**: the router reads only the latest request, as in the
  application, so it cannot use it; the classifiers can, and D3 mini resolves
  27/28 of those follow-ups.
- **Too vague** requests (asking for clarification) stay hard for everyone on
  the advanced tier (at most 4/6).

## Cases to review

Four references are missed by all three D3 models, each in one language only:
`fra1-none-04-fr` ("Le dossier Martin, tu t'en occupes ?", reference *none*),
`frc1-analyze-06-en`, `frc1-graph-04-en` and `frc1-system-05-fr`. A
language-specific miss shared by three models may point to a translation or
reference problem; they are flagged for the human review of
[#8](https://github.com/theseedship/classification_tests_deposium/issues/8).
No reference was changed after predictions.

## Boundaries

The router row is a private replay, not externally reproducible; only its
aggregates, revision hash and recording hash are public. Its role in the
application is narrower than this pack, and a low score does not mean the
application fails on these requests. D3 rows ran as Q8 GGUF on Metal (same
weights as their CPU rows; easy-tier answers match the CPU rows on 79–80 of 80
cases); Vela ran on the macOS CPU runtime. Correlated FR/EN pairs and six
families per category do not support a general ranking.
