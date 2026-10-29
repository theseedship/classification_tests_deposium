from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from deposium_bench.cases import candidate_request, load_cases, validate_cases
from deposium_bench.physics_corpus import build_cases, solve, validate_oracle, write_dataset
from deposium_bench.scoring import score_case

ROOT=Path(__file__).resolve().parents[1]
try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    Draft202012Validator=None
    ValidationError=ValueError


class PhysicsCorpusTests(unittest.TestCase):
    def setUp(self):
        self.cases=build_cases()

    def test_all_families_have_independently_checked_exact_answers(self):
        known={'uniform-distance':'60','accelerated-velocity':'11','accelerated-distance':'32',
               'opposed-forces':'4','kinetic-energy':'18','potential-energy':'140',
               'lift-efficiency':'160','inelastic-collision':'4/3','spring-energy':'1',
               'series-current':'2','parallel-resistance':'2','electrical-power':'18',
               'joule-energy':'96','capacitor-energy':'1/5','wave-speed':'30','period':'1/8',
               'echo-distance':'51','thin-lens':'30','isobaric-gas':'3','heat-energy':'1200',
               'thermal-mixing':'35','hydrostatic-pressure':'15000',
               'missing-mass':None,'missing-capacity':None}
        for case in self.cases:
            oracle=case['evaluation']['oracle'];kind=oracle['kind']
            expected=None if known[kind] is None else Fraction(known[kind])
            self.assertEqual(solve(kind,oracle['params']),expected,kind)
            answer=case['reference']['assertions'][0]['value']
            semantic=oracle['choices'][answer]
            self.assertEqual(None if semantic=='insufficient' else Fraction(semantic),expected)

    def test_counts_partition_families_and_positions(self):
        validate_cases(self.cases)
        self.assertEqual(len(self.cases),48)
        self.assertEqual(Counter(x['language'] for x in self.cases),{'fr':24,'en':24})
        self.assertEqual(Counter(x['evaluation']['difficulty'] for x in self.cases),{'D1':16,'D2':16,'D3':16})
        self.assertEqual(Counter(x['split'] for x in self.cases),{'calibration':12,'test':36})
        families=defaultdict(list)
        for c in self.cases:families[c['translation_family']].append(c)
        self.assertEqual(len(families),24)
        for pair in families.values():
            self.assertEqual(len(pair),2)
            self.assertEqual(pair[0]['split'],pair[1]['split'])
            self.assertEqual(pair[0]['reference']['assertions'],pair[1]['reference']['assertions'])
        for language in ('fr','en'):
            self.assertEqual(Counter(c['reference']['assertions'][0]['value'] for c in self.cases if c['language']==language),dict.fromkeys('abcd',6))

    def test_changed_facts_reference_oracle_and_metadata_are_rejected(self):
        mutations=[lambda c:c['input'].update(context='Altered physical law.'),
                   lambda c:c['reference']['assertions'][0].update(value='z'),
                   lambda c:c['evaluation']['oracle']['params'].update(v='99'),
                   lambda c:c['input']['options'].reverse(),
                   lambda c:c.update(split='train'),
                   lambda c:c['evaluation'].update(difficulty='D3')]
        for mutate in mutations:
            changed=deepcopy(self.cases[0]);mutate(changed)
            with self.assertRaises(ValueError):validate_cases([changed])

    def test_wrong_empty_and_abstaining_responses_cannot_pass(self):
        for c in self.cases:
            gold=c['reference']['assertions'][0]['value']
            wrong=next(o['id'] for o in c['input']['options'] if o['id']!=gold)
            for status,output in [('ok',{'choice_id':wrong}),('ok',{}),('ok',None),('abstain',None)]:
                self.assertFalse(score_case(c,{'status':status,'output':output})['passed'])
            self.assertTrue(score_case(c,{'status':'ok','output':{'choice_id':gold}})['passed'])

    def test_annotations_are_absent_from_candidate_visible_input(self):
        for c in self.cases:
            request=candidate_request(c)
            self.assertEqual(request['input'],c['input'])
            self.assertEqual(set(request['input']),{'context','question','options'})
            self.assertNotIn('reference',request)
            self.assertNotIn('oracle',request)

    def test_dataset_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'physics';m=write_dataset(p)
            cases,digest=load_cases(p/'cases.jsonl')
            self.assertEqual(cases,self.cases)
            self.assertEqual(digest,m['cases_sha256'])
            with self.assertRaises(FileExistsError):write_dataset(p)

    def test_existing_132_case_reference_is_unchanged(self):
        p=ROOT/'datasets/context-choice-v1/cases.jsonl'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'767e239c4d40573e0ffa0744bce0f6c6dfc5570604c1f02a6fae6138ea7d5616')
        self.assertEqual(len(load_cases(p)[0]),132)

    def test_versioned_physics_dataset_matches_frozen_builder_and_manifest(self):
        root=ROOT/'datasets/physics-choice-v1'
        cases,digest=load_cases(root/'cases.jsonl')
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(cases,self.cases)
        self.assertEqual(digest,manifest['cases_sha256'])
        self.assertEqual(manifest['case_count'],48)

    @unittest.skipUnless(Draft202012Validator, 'jsonschema is optional')
    def test_physics_schema_requires_its_version_and_domain_specific_oracles(self):
        schema=json.loads((ROOT/'schemas/case-v2.schema.json').read_text())
        validator=Draft202012Validator(schema)
        for case in self.cases:validator.validate(case)
        for operation in (lambda c:c['evaluation']['oracle'].pop('version'),
                          lambda c:c['evaluation'].update(domain='mathematics'),
                          lambda c:c['evaluation']['oracle'].update(kind='human_reference')):
            changed=deepcopy(self.cases[0]);operation(changed)
            with self.assertRaises(ValidationError):validator.validate(changed)


if __name__=='__main__':unittest.main()
