"""M3 source-policy tests using synthetic case identity records only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from test_rule_graph import REPO, fixture, workspace, write_inputs
sys.path.insert(0, str(REPO / "src"))
from legal_graph import rule_graph as rule
from legal_graph import fact_graph as fact


def cases_fixture():
    rows = fixture()
    rows["documents"][0].update(source_group="JUDICIAL", case_extracted_facts_enabled=False)
    base = {"case_id": "case1", "document_id": "d1", "graph_status": "ACTIVE", "graph_eligible": True,
            "graph_import_policy": {"allow": True, "allow_document_and_source_nodes": True, "allow_unreviewed_case_facts": False},
            "case_extracted_facts_enabled": False, "case_sections_review_status": "LEGACY_UNREVIEWED",
            "record_classification": "COURT_JUDGMENT", "title": "SYNTHETIC dismissed worker title",
            "facts": "Party allegation only", "reasoning": "UNREVIEWED", "decision": "UNREVIEWED",
            "features": [{"type": "UNREVIEWED"}], "court": "LEGACY COURT", "decision_date": "1900-01-01",
            "full_text": "SYNTHETIC_FULL_TEXT_ONLY"}
    blocked = deepcopy(base);blocked.update(case_id="case2", graph_status="QUARANTINE", graph_eligible=False)
    rows["cases"] = [base, blocked]
    return rows


def prepare(root, rows=None):
    data = write_inputs(root, rows or cases_fixture())
    result = rule.build(data);folder = root / "rule"
    rule.export_graph(result, folder, config_raw=rule.canonical(rule.CONFIG).encode(), code_hashes={"fixture": "test"})
    return data, folder


class FactGraphTests(unittest.TestCase):
    def test_only_eligible_case_identity_no_synthetic_facts(self):
        with workspace() as root:
            data, bundle = prepare(root);result = fact.build(data, bundle)
            self.assertEqual([n["id"] for n in result["nodes"]], ["fact:case:case1"])
            self.assertEqual(result["edges"], [])
            self.assertEqual(len(result["review_queue"]), 2)
            self.assertEqual(result["quality_report"]["coverage"]["FactAssertion"], 0)

    def test_missing_false_or_wrong_boolean_flags_deny_case(self):
        for field, value in (("graph_eligible", None), ("graph_eligible", False), ("graph_eligible", "true"), ("graph_status", "QUARANTINE")):
            rows = cases_fixture()
            if value is None:rows["cases"][0].pop(field)
            else:rows["cases"][0][field] = value
            with workspace() as root:
                data, bundle = prepare(root, rows);self.assertEqual(fact.build(data, bundle)["nodes"], [])
        rows = cases_fixture();rows["cases"][0]["graph_import_policy"] = {}
        with workspace() as root:
            data, bundle = prepare(root, rows);self.assertEqual(fact.build(data, bundle)["nodes"], [])

    def test_metadata_policy_and_source_group_gate(self):
        for mutation in ({"graph_eligible": False}, {"source_group": "SUPPLEMENTARY"}):
            rows = cases_fixture();rows["documents"][0].update(mutation)
            with workspace() as root:
                data, bundle = prepare(root, rows);self.assertEqual(fact.build(data, bundle)["nodes"], [])

    def test_legacy_header_and_sections_are_not_published_as_facts(self):
        with workspace() as root:
            data, bundle = prepare(root);props = fact.build(data, bundle)["nodes"][0]["properties"]
            for key in ("facts", "reasoning", "decision", "features", "court", "decision_date"):
                self.assertNotIn(key, props["source_properties"])
                self.assertNotIn(key, props["source_identity"])
            self.assertFalse(props["legacy_sections_imported_as_facts"])
            self.assertEqual(props["verification"]["court_and_decision_date"], "UNVERIFIED")
            self.assertFalse(props["temporal"]["verified_applicability"])

    def test_enabled_flags_still_require_reviewed_extraction(self):
        rows = cases_fixture();rows["documents"][0]["case_extracted_facts_enabled"] = True
        rows["cases"][0].update(case_extracted_facts_enabled=True, case_sections_review_status="REVIEWED")
        with workspace() as root:
            data, bundle = prepare(root, rows);result = fact.build(data, bundle)
            self.assertEqual(len(result["nodes"]), 1)
            self.assertEqual(result["nodes"][0]["properties"]["fact_extraction_status"], "PENDING_REVIEWED_EXTRACTION")
            self.assertIn("REVIEWED_EXTRACTION_ARTIFACT_REQUIRED", result["nodes"][0]["properties"]["extraction_pending_reasons"])
            self.assertEqual(result["edges"], [])

    def test_duplicate_cases_fail_before_hash_reuse(self):
        with workspace() as root:
            rows = cases_fixture();data, bundle = prepare(root, rows)
            rows["cases"].append(deepcopy(rows["cases"][0]));write_inputs(root, rows)
            with self.assertRaisesRegex(rule.BuildError, "DUPLICATE_ID"):fact.build(data, bundle)

    def test_stale_case_snapshot_and_metadata_snapshot_fail(self):
        for table in ("cases", "documents"):
            with workspace() as root:
                rows = cases_fixture();data, bundle = prepare(root, rows)
                rows[table][0]["extra"] = "changed same source ID";write_inputs(root, rows)
                with self.assertRaisesRegex(rule.BuildError, "Stale"):fact.build(data, bundle)

    def test_missing_external_document_reference_never_published(self):
        with workspace() as root:
            data, bundle = prepare(root)
            nodes = [json.loads(line) for line in (bundle / "nodes.jsonl").read_text(encoding="utf-8").splitlines()]
            raw = b''.join((rule.canonical(n)+'\n').encode() for n in nodes if n['type']!='Document')
            (bundle/'nodes.jsonl').write_bytes(raw)
            manifest=json.loads((bundle/'manifest.json').read_bytes());manifest['artifacts']['nodes.jsonl'].update(sha256=rule.digest_bytes(raw),bytes=len(raw))
            (bundle/'manifest.json').write_bytes((rule.canonical(manifest)+'\n').encode())
            result=fact.build(data,bundle)
            self.assertEqual(result['nodes'],[])
            self.assertTrue(all('DOCUMENT_ENDPOINT_NOT_PUBLISHED' in r['reason_codes'] for r in result['rejects']))

    def test_full_text_is_hashed_reference_not_extracted_content(self):
        with workspace() as root:
            data,bundle=prepare(root);node=fact.build(data,bundle)['nodes'][0]
            ref=node['properties']['full_text_reference']
            self.assertEqual(ref['sha256'],rule.digest_bytes(b'SYNTHETIC_FULL_TEXT_ONLY'))
            self.assertEqual(ref['char_end'],len('SYNTHETIC_FULL_TEXT_ONLY'))
            self.assertNotIn('SYNTHETIC_FULL_TEXT_ONLY',rule.canonical(node))

    def test_missing_full_text_preserves_identity_with_explicit_pending(self):
        rows=cases_fixture();rows['cases'][0].pop('full_text')
        with workspace() as root:
            data,bundle=prepare(root,rows);node=fact.build(data,bundle)['nodes'][0]
            self.assertEqual(node['properties']['full_text_reference']['status'],'MISSING_SOURCE_TEXT')
            self.assertIn('FULL_TEXT_SOURCE_REVIEW_REQUIRED',node['properties']['extraction_pending_reasons'])

    def test_two_builds_lf_and_input_immutability(self):
        with workspace() as root:
            data,bundle=prepare(root);before={p:p.read_bytes() for p in data.rglob('*.jsonl')}
            for folder in (root/'one',root/'two'):fact.export(fact.build(data,bundle),folder,{'fixture':'hash'})
            for path in (root/'one').iterdir():
                self.assertEqual(path.read_bytes(),(root/'two'/path.name).read_bytes());self.assertNotIn(b'\r\n',path.read_bytes())
            self.assertEqual(before,{p:p.read_bytes() for p in data.rglob('*.jsonl')})


if __name__=='__main__':unittest.main()
