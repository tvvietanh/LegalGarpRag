"""Synthetic curation/review tests; no fixture approval is used in corpus outputs."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

from test_rule_graph import fixture, workspace, write_inputs, REPO
sys.path.insert(0, str(REPO / "src"))
from legal_graph import ontology_graph as ontology
from legal_graph import rule_graph as rule


def prepare(root):
    data = write_inputs(root, fixture())
    result = rule.build(data)
    rule_dir = root / "rule"
    rule.export_graph(result, rule_dir, config_raw=rule.canonical(rule.CONFIG).encode(), code_hashes={"fixture": "SYNTHETIC_ONLY"})
    nodes = {n["id"]: n for n in result["nodes"]}
    def ev(key):
        node = nodes["rule:provision:" + key];props = node["properties"];text = props["source_properties"]["text"]
        return {"provision_node_id": node["id"], "rule_node_sha256": rule.digest(node), "provision_char_start": 0, "provision_char_end": len(text),
                "quote": text, "quote_sha256": rule.digest_bytes(text.encode()),
                "source_ref": {k: props[k] for k in ("source_path", "source_sha256", "source_record_id", "source_record_sha256")}}
    concepts = [{"concept_key": key, "label_vi": "SYNTHETIC " + key, "definition_vi": text,
                 "inclusion_criteria_vi": "Synthetic boundary only", "exclusion_boundary_vi": "Not real law",
                 "definition_provision_id": "rule:provision:" + provision, "evidence": [ev(provision)]}
                for key, provision, text in (("parent", "p1", "abc"), ("child", "p2", "bc"))]
    catalog = {"schema_version": "ontology-catalog-v1", "scope_vi": "SYNTHETIC_TEST_ONLY", "curator": "SYNTHETIC",
               "rule_manifest_sha256": rule.digest_bytes((rule_dir / "manifest.json").read_bytes()), "concepts": concepts,
               "taxonomy": [{"relation_key": "child_is_parent", "source_key": "child", "target_key": "parent", "type": "IS_A",
                             "classification_provision_id": "rule:provision:p1", "rationale_vi": "SYNTHETIC_TEST_ONLY", "evidence": [ev("p1"), ev("p2")]}]}
    path = root / "catalog.json"
    save(path, catalog)
    folder = data / "07_research_extensions/knowledge"
    (folder / "issues.jsonl").write_bytes(b'{"issue_id":"issue1","issue_key":"fixture","label_vi":"fixture"}\n')
    (folder / "issue_edges.jsonl").write_bytes(b'{"source_id":"p1","target_id":"issue1","type":"RELATES_TO_ISSUE","provenance_status":"VERIFIED","evidence_text":"abc"}\n')
    return data, rule_dir, path, catalog


def save(path, value):
    path.write_bytes((rule.canonical(value) + "\n").encode())


def approval(root, result):
    report = root / "review.md";report.write_bytes(b'SYNTHETIC_INDEPENDENT_REVIEW_FIXTURE_ONLY\n')
    path = root / "approval.json"
    row = {"schema_version": "ontology-review-v1", "decision": "APPROVED", "reviewer_role": "graph_reviewer", "reviewer": "SYNTHETIC_TEST_ONLY",
           "independent_review": True, "catalog_sha256": result["dependencies"]["catalog"]["sha256"],
           "rule_manifest_sha256": result["dependencies"]["rule_manifest_sha256"],
           "concept_ids": sorted(n["id"] for n in result["nodes"] if n["type"] == "LegalConcept"),
           "edge_ids": sorted(e["id"] for e in result["edges"]), "review_report_sha256": rule.digest_bytes(report.read_bytes())}
    save(path, row)
    return path, report, row


class OntologyTests(unittest.TestCase):
    def test_draft_has_evidence_grounding_without_self_approval(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            result = ontology.build(data, bundle, path)
            self.assertEqual((len(result["nodes"]), len(result["edges"])), (3, 3))
            self.assertEqual(result["coverage_report"]["independently_accepted_concepts"], 0)
            self.assertTrue(all(n["properties"]["verification"]["semantic"] == "UNVERIFIED" for n in result["nodes"] if n["type"] == "LegalConcept"))
            self.assertEqual(len(result["dependencies"]["external_rule_node_ids"]), 2)

    def test_missing_definition_boundaries_or_evidence_fails(self):
        for field in ("definition_vi", "inclusion_criteria_vi", "exclusion_boundary_vi", "evidence"):
            with workspace() as root:
                data, bundle, path, catalog = prepare(root)
                del catalog["concepts"][0][field];save(path, catalog)
                with self.assertRaises(rule.BuildError):ontology.build(data, bundle, path)

    def test_stale_rule_snapshot_and_node_snapshot_fail(self):
        for where in ("rule", "node"):
            with workspace() as root:
                data, bundle, path, catalog = prepare(root)
                if where == "rule":catalog["rule_manifest_sha256"] = "stale"
                else:catalog["concepts"][0]["evidence"][0]["rule_node_sha256"] = "stale"
                save(path, catalog)
                with self.assertRaisesRegex(rule.BuildError, "[Ss]tale"):ontology.build(data, bundle, path)

    def test_wrong_owner_quote_and_offsets_fail(self):
        for mutation in ("owner", "quote", "offset"):
            with workspace() as root:
                data, bundle, path, catalog = prepare(root)
                evidence = catalog["concepts"][0]["evidence"][0]
                if mutation == "owner":evidence["source_ref"]["source_record_id"] = "other"
                elif mutation == "quote":evidence["quote"] = "invented"
                else:evidence["provision_char_end"] = 999
                save(path, catalog)
                with self.assertRaises(rule.BuildError):ontology.build(data, bundle, path)

    def test_duplicate_concept_and_wrong_taxonomy_endpoint_fail(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            catalog["concepts"].append(deepcopy(catalog["concepts"][0]));save(path, catalog)
            with self.assertRaisesRegex(rule.BuildError, "Duplicate"):ontology.build(data, bundle, path)
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            catalog["taxonomy"][0]["target_key"] = "absent";save(path, catalog)
            with self.assertRaisesRegex(rule.BuildError, "endpoints"):ontology.build(data, bundle, path)

    def test_cycle_and_self_loop_are_rejected(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            reverse = deepcopy(catalog["taxonomy"][0]);reverse.update(relation_key="reverse", source_key="parent", target_key="child")
            catalog["taxonomy"].append(reverse);save(path, catalog)
            with self.assertRaisesRegex(rule.BuildError, "IS_A cycle"):ontology.build(data, bundle, path)
        with self.assertRaises(rule.BuildError):ontology.check_taxonomy([{"relation_key":"self","source_key":"a","target_key":"a","type":"IS_A"}], {"a"})

    def test_keyword_verified_provenance_does_not_create_axiom(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            result = ontology.build(data, bundle, path)
            self.assertEqual(result["coverage_report"]["keyword_axioms_published"], 0)
            self.assertEqual(result["candidates"][0]["primary_reason"], "KEYWORD_ASSOCIATION_NOT_SEMANTIC_AXIOM")
            issue = next(n for n in result["nodes"] if n["type"] == "LegalIssue")
            self.assertEqual(issue["properties"]["vocabulary_status"], "SOURCE_VOCABULARY")
            self.assertFalse(any(e["target_id"] == issue["id"] for e in result["edges"]))

    def test_approval_binds_catalog_rule_ids_and_report(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root);draft = ontology.build(data, bundle, path)
            ap, report, row = approval(root, draft)
            accepted = ontology.build(data, bundle, path, approval_path=ap, review_report=report)
            self.assertEqual(accepted["coverage_report"]["independently_accepted_concepts"], 2)
            self.assertTrue(all(e["properties"]["verification"]["semantic"] == "VERIFIED" for e in accepted["edges"]))
            catalog["concepts"][0]["label_vi"] += " changed";save(path, catalog)
            with self.assertRaisesRegex(rule.BuildError, "stale independent"):ontology.build(data, bundle, path, approval_path=ap, review_report=report)

    def test_incomplete_approval_and_modified_review_report_fail(self):
        for mutation in ("ids", "report", "coerced"):
            with workspace() as root:
                data, bundle, path, catalog = prepare(root);draft = ontology.build(data, bundle, path)
                ap, report, row = approval(root, draft)
                if mutation == "ids":row["edge_ids"] = [];save(ap, row)
                elif mutation == "coerced":row["independent_review"] = 1;save(ap, row)
                else:report.write_bytes(b'changed\n')
                with self.assertRaises(rule.BuildError):ontology.build(data, bundle, path, approval_path=ap, review_report=report)

    def test_taxonomy_requires_real_parent_classification_evidence(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            catalog["taxonomy"][0]["classification_provision_id"] = "rule:provision:p2";save(path, catalog)
            with self.assertRaises(rule.BuildError):ontology.build(data, bundle, path)

    def test_two_exports_are_lf_byte_identical_and_inputs_unchanged(self):
        with workspace() as root:
            data, bundle, path, catalog = prepare(root)
            before = {p: p.read_bytes() for p in data.rglob('*.jsonl')}
            one = ontology.build(data, bundle, path);two = ontology.build(data, bundle, path)
            for result, target in ((one, root / 'one'), (two, root / 'two')):
                ontology.export(result, target, {'fixture':'hash'})
            for p in (root / 'one').iterdir():
                self.assertEqual(p.read_bytes(), (root / 'two' / p.name).read_bytes())
                self.assertNotIn(b'\r\n', p.read_bytes())
            self.assertEqual(before, {p: p.read_bytes() for p in data.rglob('*.jsonl')})


if __name__ == '__main__':unittest.main()
