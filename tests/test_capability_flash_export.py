"""Publication controls for aggregate exports; no private archive or model needed."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("capability_flash_export", ROOT / "scripts/export-capability-flash.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def count_fixture(total=4):
    from deposium_bench.context_analysis import _counts
    rows = [{"case_id":str(i),"translation_family":str(i),"scenario_id":str(i),"split":"test",
             "recorded":True,"supported":True,"scored":True,"passed":True,"status":"ok",
             "failure_kind":None,"error":None,"reference_actual_tokens":None,"reference_padded_tokens":None,
             "measurements":{field:None for field in ("adapter_duration_ms","decision_ms","inference_ms","http_ms",
                "native_tokens","native_padded_tokens","rss_mib","http_attempted","cached_failure",
                "provider_input_tokens","provider_output_tokens","state_truncated","options_truncated")}}
            for i in range(total)]
    return _counts(rows)


class AggregatePublicationTests(unittest.TestCase):
    def test_projection_never_recursively_copies_private_fields_paths_or_process_ids(self):
        source = count_fixture()
        secret = "/synthetic-private-sentinel/location"
        source.update(private_path=secret,pid=12345,adapter_provenance={"binary":secret})
        source["latency"]["adapter_duration_ms"].update(private_path=secret,pid=12345)
        source["resources"]["rss_mib"].update(private_path=secret)
        source["counts_by_split"]["test"].update(private_path=secret,pid=12345)
        projected = exporter.public_counts(source)
        rendered = json.dumps(projected)
        self.assertNotIn(secret, rendered)
        self.assertNotIn('"pid"', rendered)
        self.assertNotIn("adapter_provenance", rendered)
        self.assertEqual(projected["passed_cases"],4)
        self.assertIsNone(projected["per_response_resources"]["rss_mib"]["max"])

    def test_zero_scored_or_unexpected_denominators_do_not_qualify(self):
        good=count_fixture()
        exporter.validate_counts(good,4)
        for count,total in (({**good,"scored_cases":0,"passed_cases":0},4),
                            ({**good,"total_cases":3},4),(good,0)):
            with self.subTest(total=total),self.assertRaises(ValueError):
                exporter.validate_counts(count,total)
        bad=deepcopy(good);bad["counts_by_status"].update(ok=5,error=-1)
        with self.assertRaises(ValueError):exporter.validate_counts(bad,4)

    def test_nested_private_values_nonfinite_cells_and_untyped_preparation_are_rejected(self):
        for bad in ({"source_path":"/synthetic-private-sentinel/location"},"/synthetic-private-sentinel/location",float("inf"),True,-1):
            for target in ("status","split"):
                value=count_fixture()
                if target=="status":value["counts_by_status"]["ok"]=bad
                else:value["counts_by_split"]["test"]["passed_cases"]=bad
                with self.subTest(target=target,value=bad),self.assertRaises(ValueError):
                    exporter.public_counts(value)
        summary={"request_count":324,"within_limit":324,"unsupported":0,"errors":0,"min_tokens":128,
                 "max_tokens":1214,"cases_scored":0,"native_preparation_observed":True,
                 "live_forward_ids_compared":False,"negative_control":"native_prepare_overflow_refused"}
        self.assertEqual(exporter.preparation_summary(summary)["cases_scored"],0)
        for key,bad in (("negative_control",{"source_path":"/synthetic-private-sentinel/location"}),
                        ("native_preparation_observed",{"pid":42}),("max_tokens",float("inf"))):
            with self.subTest(key=key),self.assertRaises(ValueError):
                exporter.preparation_summary({**summary,key:bad})

    def test_invalid_seal_changed_bytes_and_unsafe_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);payload=root/"payload.json";payload.write_bytes(b"synthetic fixture\n")
            seal={"schema_version":"synthetic.test/v1","files":{"payload.json":hashlib.sha256(payload.read_bytes()).hexdigest()}}
            path=root/"seal.json";path.write_text(json.dumps(seal))
            exporter.verify_seal(root,"seal.json","synthetic.test/v1",exact=True)
            payload.write_bytes(b"changed fixture")
            with self.assertRaises(ValueError):exporter.verify_seal(root,"seal.json","synthetic.test/v1")
            seal["files"]={"../outside.json":"a"*64};path.write_text(json.dumps(seal))
            with self.assertRaises(ValueError):exporter.verify_seal(root,"seal.json","synthetic.test/v1")
            path.write_text(json.dumps({**seal,"schema_version":"wrong"}))
            with self.assertRaises(ValueError):exporter.verify_seal(root,"seal.json","synthetic.test/v1")

    def pair_fixture(self):
        cases=[];rows=[];records=[]
        for family in ("one","two","three"):
            for variant in ("compact","expanded"):
                key=family+"-"+variant
                cases.append({"case_id":key,"translation_family":family,"language":"en","split":"test",
                    "evaluation":{"oracle":{"params":{"catalogue_variant":variant}}}})
                missing=family=="two" and variant=="expanded"
                correct=family=="three" or (family=="two" and variant=="compact")
                rows.append({"case_id":key,"status":"missing" if missing else "ok","scored":not missing,"passed":correct})
                if not missing:records.append({"case_id":key,"status":"ok","output":{"choice_id":"a"}})
        return cases,rows,records

    def test_pairs_keep_missing_states_and_distinguish_agreement_from_correctness(self):
        cases,rows,records=self.pair_fixture()
        total=next(x for x in exporter.paired_views(cases,rows,records) if x["split"]==x["stratum"]=="all")
        self.assertEqual(total["total_pairs"],3)
        self.assertEqual(total["both_correct"],1)
        self.assertEqual(total["neither_correct"],1)
        self.assertEqual(total["any_unscored"],1)
        self.assertEqual(total["both_valid_choices"],2)
        self.assertEqual(total["same_choice"],2)
        self.assertIn({"first":"ok","second":"missing","pairs":1},total["status_pairs"])
        self.assertEqual(sum(total[k] for k in ("both_correct","first_only_correct","second_only_correct","neither_correct","any_unscored")),3)

    def test_language_pairs_and_family_totals_have_their_own_denominators(self):
        cases,rows,records=self.pair_fixture()
        for c in cases:
            variant=c["evaluation"]["oracle"]["params"]["catalogue_variant"]
            c["language"]="fr" if variant=="compact" else "en"
            c["evaluation"]["oracle"]["params"]["catalogue_variant"]="compact"
        total=next(x for x in exporter.paired_views(cases,rows,records,axis="language") if x["split"]==x["stratum"]=="all")
        self.assertEqual((total["first_view"],total["second_view"],total["total_pairs"]),("fr","en",3))
        family=exporter.family_groups(cases,rows)[0]
        self.assertEqual((family["families"],family["all_scored"],family["all_correct"],family["none_correct"],family["some_correct"]),(3,2,1,1,1))

    def test_preparation_fingerprints_drop_machine_paths_and_unrelated_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            study=Path(tmp)
            data={"native_source":"/synthetic-source","native_runtime_build":"/synthetic-build",
                  "helper_binary_sha256":"a"*64,"helper_source_sha256":"b"*64,"builder_sha256":"c"*64,
                  "native_revision":exporter.NATIVE_PIN,"private_path":"/private/sentinel","pid":42,
                  "dependency_files_sha256":{"/synthetic-source/tools/server/server-decision.h":"d"*64,
                    "/synthetic-build/tools/server/libserver-context.a":"e"*64,"/machine-only/compiler":"f"*64}}
            (study/"native-build.json").write_text(json.dumps(data))
            result=exporter.preparation_fingerprints(study)
            encoded=json.dumps(result)
            for private in ("/synthetic-source","/synthetic-build","/machine-only","/private/sentinel",'"pid"'):
                self.assertNotIn(private,encoded)
            self.assertEqual(len(result["public_dependency_fingerprints"]),2)
            self.assertEqual(result["external_compiler_sdk_fingerprints"],["f"*64])

    def test_divergent_reference_bytes_code_scorer_and_qualification_are_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bench=root/"bench";study=root/"study";phase=study/"anchor-002"
            phase.mkdir(parents=True);(phase/"pilot-seal.json").write_text('{"files":{}}')
            dataset=bench/exporter.DATASETS['anchor'][0];dataset.parent.mkdir(parents=True);dataset.write_bytes(b"frozen reference fixture")
            cases=[{"case_id":str(i)} for i in range(132)]
            manifest={"bench":{"git":{"head":exporter.HEAD,"dirty":False}},"qualification":"model_isolated",
                      "input_protocol":"context_choice","scorer":{"sha256":"a"*64},"dataset_sha256":exporter.DATASETS['anchor'][2]}
            analyzer=Mock(side_effect=AssertionError("analysis must not run for divergent sources"))
            mutations=[lambda m,p:p.update({"cases.jsonl":b"different reference bytes"}),
                       lambda m,p:m['bench']['git'].update(head="0"*40),
                       lambda m,p:m.update(scorer={"sha256":"b"*64}),
                       lambda m,p:m.update(qualification="harness_control")]
            for mutate in mutations:
                current=deepcopy(manifest);payload={"cases.jsonl":dataset.read_bytes()};mutate(current,payload)
                campaigns=SimpleNamespace(_archive=Mock(return_value=(phase,current,cases,[],{"sealed":True},payload)),
                                          _scorer_fingerprint=Mock(return_value={"sha256":"a"*64}))
                with self.subTest(mutation=mutate),patch.object(exporter,"verify_seal",return_value="c"*64),self.assertRaises(ValueError):
                    exporter.phase_export(bench,study,"anchor-002","anchor",root/"output",{},(campaigns,analyzer,None))
            analyzer.assert_not_called()


if __name__=="__main__":unittest.main()
