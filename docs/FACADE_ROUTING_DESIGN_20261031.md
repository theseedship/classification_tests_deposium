# Facade routing: a small classifier against the production router

**Fixed on 31 October 2026, before any prediction.** Issue #56, maintainer
decision **option B**: the production router is replayed privately; only its
aggregate scores on a public pack are published.

## Question

A document assistant exposes a few tool categories for each request (search,
analyse, visualise, graph, evaluate, process, system). Today a deterministic
router chooses the category. Would a small local classifier choose better,
worse or the same, and on which requests?

## Public pack

[`facade-routing-v1`](../datasets/facade-routing-v1/README.md): 40 request
families in French and English, **80 cases** (16 TRAIN, 16 calibration, 48
TEST), cases SHA-256 `03f30a621298ecb4…`. Each case is a closed choice among
**eight generic categories**: the seven above plus *none of these* (out of
scope or too vague: ask for clarification). Five families per category: two
direct requests, two paraphrases without the obvious word, one harder request
(a refused alternative such as "no chart needed", or a two-step request where
only one step is asked now). Answer positions are rotated across the eight
slots.

Requests and references were written **without access to any router rule or
keyword list**. Category descriptions are generic and contain nothing from the
application.

## Candidates

| Candidate | How it answers | Published |
|---|---|---|
| Production router, private replay | Its deterministic query-to-category function, run locally on each request text at a pinned private revision; its category is mapped to the matching option | aggregate scores, the revision hash, the scorer output; **no code, rule, keyword or configuration** |
| D3 lite / nano / mini, Vela 2.0 0.3B on macOS CPU | ordinary `bench.context-choice` adapters, existing profiles | as every other campaign |

The router's learning variant depends on live session feedback and is not
replayed. The router row is labelled *private replay, not externally
reproducible*, as the remote API rows are labelled remote. Its predictions
enter the shared engine as a harness-control recording kept under the ignored
`results/` directory; the recording is not published.

## Reporting

Per candidate: correct / 80, TEST / 48, by category, by request kind (direct,
paraphrase, refused alternative, two-step, out of scope, vague), FR/EN.
Paired with the router: cases both get right, only one gets right, neither,
and error overlap by category. A few-case difference on correlated FR/EN pairs
is not a general ranking. References are agent-authored and pending human
review.

## Order

1. This note, the pack and its tests (no prediction).
2. Router replay (private, seconds).
3. The four classifiers, one CPU campaign at a time, after the passage campaigns
   of issue #52 have finished.
4. One report and registration in the results generator.
