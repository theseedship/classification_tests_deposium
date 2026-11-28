# Directional relation predicate choice

This synthetic pack contains 54 French and English `bench.context-choice`
cases in nine document families. Three families each belong to train,
calibration and test (18 cases per split). References and translations are
agent-authored and await human review.

For each language and family, the candidate sees three contrasts.

| Contrast | Candidate input | Reference |
|---|---|---|
| Forward | Excerpt and original endpoint order | A supported predicate from A to B |
| Reverse | Same excerpt, with A and B exchanged | A licensed inverse when it is offered, otherwise the explicit fallback |
| No evidence | Same original endpoints and menu, with a replacement excerpt | The explicit fallback |

The no-evidence excerpts use co-mentions, declined proposals, questions or
insufficiently grounded statements. Names, manuscripts and excerpts are invented.
All six views stay in the document family's split. Candidate option order and
IDs stay fixed within each family. Order rotates across families.

The candidate gets only the excerpt, the named and typed endpoints, the
instruction and the ordered option descriptions. Selecting the fallback is a
semantic answer with status `ok`. Empty outputs and technical abstention
cannot pass. Report exact scores by split, language and contrast, plus coverage
and the count of unsupported predicates accepted on no-evidence cases. Count
families separately from the correlated views.

Verify the frozen pack and the candidate projection offline.

```sh
python3 scripts/build-relation-predicate-pack.py --check
python3 -m deposium_bench validate-cases --dataset datasets/relation-predicate-choice-v1/cases.jsonl
python3 -m unittest discover -s tests -p test_relation_predicate_choice.py -v
```

The fixed menu contains three specific predicates and a fallback. This pack
checks selection given a shortlist. Shortlist recall, wider vocabularies,
confidence thresholds, model performance and graph integration require separate
evidence.
