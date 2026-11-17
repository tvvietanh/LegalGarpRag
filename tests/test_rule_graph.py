"""Adversarial synthetic fixtures for M1; no fixture is a legal source/review."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import unittest
import uuid


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from legal_graph import rule_graph as graph


@contextmanager
def workspace():
    parent = REPO / "outputs/milestone_1/test_tmp"
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / ("fixture_" + uuid.uuid4().hex)
    path.mkdir()  # Avoid Python 3.13 mode=0700 Windows sandbox ACL behavior.
    try:
        yield path
    finally:
        if not path.resolve().is_relative_to(parent.resolve()):
            raise RuntimeError("Unsafe fixture cleanup path")
        shutil.rmtree(path)


def fixture() -> dict:
    rows = {table: [] for table in graph.TABLES}
    rows["documents"] = [{"document_id": "d1", "instrument_id": "instrument1", "title": "Synthetic fixture",
                          "graph_status": "ACTIVE", "graph_eligible": True, "temporal_verified": True,
                          "source_url": " https://example.invalid/source ",
                          "graph_import_policy": {"allow": True, "allow_document_and_source_nodes": True,
                                                  "allow_provision_hierarchy": True,
                                                  "allow_unreviewed_temporal_edges": False}}]
    rows["texts"] = [{"document_id": "d1", "text": "abc"}]
    rows["segments"] = [{"segment_id": "segment1", "document_id": "d1", "text": "abc"}]
    for key, level, parent, start, text in (("p1", "ARTICLE", "d1", 0, "abc"), ("p2", "CLAUSE", "p1", 1, "bc")):
        row = {"provision_id": key, "document_id": "d1", "level": level, "parent_id": parent,
               "text": text, "canonical_path": "d1/" + key, "segment_id": "segment1",
               "coordinate_space": "SEGMENT_TEXT", "segment_char_start": start, "segment_char_end": 3,
               "document_char_start": start, "document_char_end": 3, "provenance_status": "RESOLVED",
               "provision_identity_id": "identity_" + key, "provision_version_id": key,
               "source_document_version_id": "d1", "temporal_status": "INHERITED_DOCUMENT",
               "provision_temporal_verified": False, "valid_from": "2020-01-01", "valid_to": None}
        rows["provisions"].append(row)
        rows["spans"].append({k: row[k] for k in ("provision_id",) + graph.SPAN_KEYS if k in row})
        rows["identities"].append({"provision_identity_id": "identity_" + key, "instrument_id": "instrument1", "temporal_status": "UNKNOWN"})
        rows["versions"].append({k: row[k] for k in ("provision_version_id", "provision_identity_id", "source_document_version_id") + graph.TEMPORAL_KEYS if k in row})
    return rows


def relation(rows, *, source="p1", target="p2", kind="REFERENCES"):
    record = {"edge_id": "relation1", "source_id": source, "target_id": target, "type": kind,
              "evidence_text": "bc", "evidence_status": "RESOLVED", "resolution_scope": "PROVISION",
              "evidence_span": {"coordinate_space": "SEGMENT_TEXT", "segment_id": "segment1",
                                "segment_char_start": 1, "segment_char_end": 3},
              "method": "synthetic_fixture", "confidence": 1.0}
    rows["relations"].append(record)
    return record


def write_inputs(root, rows):
    data = root / "Data"
    for table, (relative, _) in graph.TABLES.items():
        path = data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join((graph.canonical(row) + "\n").encode("utf-8") for row in rows[table]))
    return data


def reviewed(root, data, rows, **overrides):
    relative, key = graph.TABLES["relations"]
    source = graph.load_source(data, "relations", relative, key)
    original = source.records[0]
    indexes = {table: graph.unique_index(graph.load_source(data, table, relative, key))
               for table, (relative, key) in graph.TABLES.items() if table != "quarantine"}
    def endpoint(raw):
        for table, kind in (("documents", "document"), ("provisions", "provision"), ("identities", "identity"), ("cases", "case")):
            if raw in indexes[table]:
                return kind, indexes[table][raw]
        return None
    dependencies = graph.review_dependencies(original, endpoint(original.row["source_id"]), endpoint(original.row["target_id"]), indexes)
    row = {"review_id": "fixture_review", "source_path": relative, "source_record_id": original.source_record_id,
           "source_record_sha256": original.source_record_sha256, "source_input_sha256": original.source_sha256,
           "source_id": rows["relations"][0]["source_id"], "target_id": rows["relations"][0]["target_id"],
           "relation_type": rows["relations"][0]["type"], "decision": "APPROVED", "evidence_verified": True,
           "semantic_verified": True, "target_resolution_verified": True, "reviewer": "SYNTHETIC_TEST_ONLY",
           "reviewed_at": "2026-11-17", "dependency_snapshots": dependencies, **overrides}
    path = root / "synthetic_reviews.jsonl"
    path.write_bytes((graph.canonical(row) + "\n").encode("utf-8"))
    return path


class RuleGraphTests(unittest.TestCase):
    def build(self, rows=None):
        with workspace() as root:
            return graph.build(write_inputs(root, rows or fixture()))

    def test_baseline_structural_graph_has_required_envelopes_and_refs(self):
        result = self.build()
        self.assertEqual(len(result["nodes"]), 7)
        self.assertEqual(len(result["edges"]), 6)
        self.assertTrue(all(value == 0 for value in graph.validate_graph(result["nodes"], result["edges"]).values()))
        for node in result["nodes"]:
            self.assertTrue(node["properties"]["provenance"])
            self.assertIn("source_record_sha256", node["properties"])
        self.assertIn("rule:provision:p1", {n["id"] for n in result["nodes"]})
        self.assertIn("rule:version:p1", {n["id"] for n in result["nodes"]})

    def test_id_namespace_encoding_preserves_source(self):
        self.assertEqual(graph.qid("document", "a:b/c"), "rule:document:a%3Ab%2Fc")
        self.assertNotEqual(graph.qid("provision", "same"), graph.qid("version", "same"))
        with self.assertRaises(graph.BuildError):
            graph.qid("document", " padded ")

    def test_valid_article_clause_point_with_child_before_parent(self):
        rows = fixture()
        point = deepcopy(rows["provisions"][1])
        point.update(provision_id="p3", parent_id="p2", level="POINT", text="c", segment_char_start=2,
                     document_char_start=2, provision_identity_id="identity_p3", provision_version_id="p3", canonical_path="d1/p3")
        rows["provisions"].insert(0, point)
        rows["spans"].append({k: point[k] for k in ("provision_id",) + graph.SPAN_KEYS if k in point})
        rows["identities"].append({"provision_identity_id": "identity_p3", "instrument_id": "instrument1", "temporal_status": "UNKNOWN"})
        rows["versions"].append({k: point[k] for k in ("provision_version_id", "provision_identity_id", "source_document_version_id") + graph.TEMPORAL_KEYS if k in point})
        result = self.build(rows)
        self.assertEqual(len(result["nodes"]), 10)
        self.assertEqual(len(result["edges"]), 9)
        edge = next(e for e in result["edges"] if e["type"] == "CONTAINS" and e["target_id"] == "rule:provision:p3")
        self.assertEqual(edge["source_id"], "rule:provision:p2")

    def test_exact_duplicate_id_fails_closed(self):
        rows = fixture()
        rows["documents"].append(deepcopy(rows["documents"][0]))
        with self.assertRaisesRegex(graph.BuildError, "DUPLICATE_ID"):
            self.build(rows)

    def test_conflicting_duplicate_fails_closed_without_last_write(self):
        rows = fixture()
        duplicate = deepcopy(rows["provisions"][0])
        duplicate["text"] = "conflict"
        rows["provisions"].append(duplicate)
        with self.assertRaisesRegex(graph.BuildError, "CONFLICTING_DUPLICATE"):
            self.build(rows)

    def test_raw_endpoint_collision_across_types_fails(self):
        rows = fixture()
        rows["cases"] = [{"case_id": "p1", "document_id": "d1"}]
        with self.assertRaisesRegex(graph.BuildError, "RAW_ENDPOINT_NAMESPACE_COLLISION"):
            self.build(rows)

    def test_unrelated_version_raw_collision_fails(self):
        rows = fixture()
        rows["versions"][0]["provision_version_id"] = "d1"
        with self.assertRaisesRegex(graph.BuildError, "VERSION_NAMESPACE_COLLISION"):
            self.build(rows)

    def test_policy_defaults_deny_and_string_true_does_not_pass(self):
        for mutation in ({"graph_import_policy": {}}, {"graph_eligible": "true"}, {"graph_status": "QUARANTINE"}):
            rows = fixture()
            rows["documents"][0].update(mutation)
            result = self.build(rows)
            self.assertEqual(result["nodes"], [])
            self.assertEqual(result["edges"], [])

    def test_hierarchy_denied_keeps_only_document(self):
        rows = fixture()
        rows["documents"][0]["graph_import_policy"]["allow_provision_hierarchy"] = False
        result = self.build(rows)
        self.assertEqual([n["type"] for n in result["nodes"]], ["Document"])
        self.assertEqual(result["quality_report"]["accounting"]["provisions"]["primary_reasons"], {"HIERARCHY_POLICY_DENIED": 2})

    def test_quarantine_overlap_never_promoted_and_duplicate_records_counted(self):
        rows = fixture()
        rows["quarantine"] = [deepcopy(rows["provisions"][0])] * 2
        result = self.build(rows)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["quality_report"]["quarantine"], {"records": 2, "distinct_ids": 1, "duplicate_extra_records": 1})
        self.assertEqual(sum(r["record_count"] for r in result["rejects"] if r["table"] == "quarantine"), 2)

    def test_orphan_and_wrong_endpoint_parent_are_rejected(self):
        for parent in ("missing", "identity_p1"):
            rows = fixture()
            rows["provisions"][1]["parent_id"] = parent
            result = self.build(rows)
            self.assertEqual(sum(n["type"] == "Provision" for n in result["nodes"]), 1)
            reject = next(r for r in result["rejects"] if r["source_record_id"] == "p2" and r["table"] == "provisions")
            self.assertIn("PARENT_MISSING_OR_WRONG_TYPE", reject["reason_codes"])

    def test_self_loop_blocks_parent_and_child(self):
        rows = fixture()
        rows["provisions"][0]["parent_id"] = "p1"
        result = self.build(rows)
        self.assertEqual(len(result["nodes"]), 1)
        p1 = next(r for r in result["rejects"] if r["table"] == "provisions" and r["source_record_id"] == "p1")
        self.assertIn("PARENT_SELF_LOOP", p1["reason_codes"])
        self.assertEqual(result["quality_report"]["closure"]["parent_closure_excluded"], 1)

    def test_cycle_is_detected_and_never_published(self):
        rows = fixture()
        rows["provisions"][0]["parent_id"] = "p2"
        result = self.build(rows)
        provision_rejects = [r for r in result["rejects"] if r["table"] == "provisions"]
        self.assertEqual(len(provision_rejects), 2)
        self.assertTrue(all("PARENT_CYCLE" in r["reason_codes"] for r in provision_rejects))
        self.assertEqual(result["edges"], [])

    def test_wrong_level_and_cross_document_parent_are_detected(self):
        rows = fixture()
        rows["provisions"][1]["level"] = "POINT"
        self.assertIn("PARENT_WRONG_LEVEL", next(r for r in self.build(rows)["rejects"] if r["table"] == "provisions")["reason_codes"])
        rows = fixture()
        other = deepcopy(rows["documents"][0]);other["document_id"] = "d2"
        rows["documents"].append(other)
        rows["provisions"][1]["document_id"] = "d2"
        result = self.build(rows)
        self.assertIn("PARENT_WRONG_DOCUMENT", next(r for r in result["rejects"] if r["table"] == "provisions")["reason_codes"])

    def test_mismatch_queues_direct_record_and_blocks_child_closure(self):
        rows = fixture()
        rows["provisions"][0]["text"] = "changed source extraction"
        result = self.build(rows)
        self.assertEqual(len(result["provision_review_queue"]), 1)
        self.assertEqual(result["provision_review_queue"][0]["source_record_id"], "p1")
        reasons = result["quality_report"]["accounting"]["provisions"]["primary_reasons"]
        self.assertEqual(reasons, {"EVIDENCE_TEXT_MISMATCH": 1, "PARENT_NOT_PUBLISHED": 1})
        self.assertEqual(len(result["nodes"]), 1)

    def test_span_bounds_owner_and_provenance_disagreement(self):
        rows = fixture();rows["provisions"][0]["segment_char_end"] = 999
        r = self.build(rows)
        self.assertIn("EVIDENCE_INVALID_BOUNDS", next(x for x in r["rejects"] if x["table"] == "provisions" and x["source_record_id"] == "p1")["reason_codes"])
        rows = fixture();rows["segments"][0]["document_id"] = "different"
        self.assertEqual(sum(n["type"] == "Provision" for n in self.build(rows)["nodes"]), 0)
        rows = fixture();rows["spans"][0]["segment_char_start"] = 1
        r = self.build(rows)
        self.assertIn("PROVENANCE_SPAN_DISAGREEMENT", next(x for x in r["rejects"] if x["table"] == "provisions" and x["source_record_id"] == "p1")["reason_codes"])

    def test_version_identity_document_join_conflict_blocks_closure(self):
        rows = fixture();rows["versions"][0]["provision_identity_id"] = "identity_p2"
        result = self.build(rows)
        self.assertEqual(len(result["nodes"]), 1)
        p1 = next(r for r in result["rejects"] if r["table"] == "provisions" and r["source_record_id"] == "p1")
        self.assertIn("VERSION_IDENTITY_DOCUMENT_MISMATCH", p1["reason_codes"])

    def test_temporal_source_flags_are_preserved_without_verified_applicability(self):
        rows = fixture()
        rows["provisions"][0]["provision_temporal_verified"] = True
        result = self.build(rows)
        self.assertTrue(all(n["properties"]["temporal"]["verified_applicability"] is False for n in result["nodes"]))
        p1 = next(n for n in result["nodes"] if n["id"] == "rule:provision:p1")
        self.assertTrue(p1["properties"]["source_properties"]["provision_temporal_verified"])
        self.assertEqual(p1["properties"]["temporal"]["assessment"], "INHERITED_UNVERIFIED")

    def test_accepted_name_and_resolved_evidence_are_not_semantic_review(self):
        rows = fixture();relation(rows)
        result = self.build(rows)
        self.assertEqual(len(result["edges"]), 6)
        self.assertEqual(result["candidates"][0]["primary_reason"], "SEMANTIC_REVIEW_REQUIRED")

    def test_explicit_review_with_input_and_record_hash_publishes_valid_relation(self):
        rows = fixture();relation(rows)
        with workspace() as root:
            data = write_inputs(root, rows)
            review = reviewed(root, data, rows)
            result = graph.build(data, review_catalog=review)
            self.assertEqual(len(result["edges"]), 7)
            self.assertEqual(result["candidates"], [])
            edge = next(e for e in result["edges"] if e["type"] == "REFERENCES")
            self.assertEqual(edge["properties"]["verification"]["semantic"], "VERIFIED")
            self.assertTrue(any(p["source_record_id"] == "fixture_review" for p in edge["properties"]["provenance"]))

    def test_stale_or_boolean_coerced_review_never_publishes(self):
        for overrides in ({"source_record_sha256": "stale"}, {"evidence_verified": 1}, {"reviewer": ""}):
            rows = fixture();relation(rows)
            with workspace() as root:
                data = write_inputs(root, rows);review = reviewed(root, data, rows, **overrides)
                self.assertEqual(len(graph.build(data, review_catalog=review)["edges"]), 6)

    def test_review_requires_explicit_dependency_snapshots(self):
        rows = fixture();relation(rows)
        with workspace() as root:
            data = write_inputs(root, rows);review = reviewed(root, data, rows, dependency_snapshots=[])
            result = graph.build(data, review_catalog=review)
            self.assertEqual(len(result["edges"]), 6)
            self.assertIn("SEMANTIC_REVIEW_DEPENDENCIES_REQUIRED", result["candidates"][0]["reason_codes"])

    def test_target_content_change_same_id_invalidates_original_review(self):
        rows = fixture();relation(rows)
        with workspace() as root:
            data = write_inputs(root, rows);review = reviewed(root, data, rows)
            self.assertEqual(len(graph.build(data, review_catalog=review)["edges"]), 7)
            rows["provisions"][1].update(text="ab", segment_char_start=0, segment_char_end=2,
                                           document_char_start=0, document_char_end=2)
            rows["spans"][1].update(segment_char_start=0, segment_char_end=2, document_char_start=0, document_char_end=2)
            write_inputs(root, rows)
            result = graph.build(data, review_catalog=review)
            self.assertEqual(sum(n["type"] == "Provision" for n in result["nodes"]), 2)
            self.assertEqual(len(result["edges"]), 6)
            self.assertIn("SEMANTIC_REVIEW_DEPENDENCIES_STALE", result["candidates"][0]["reason_codes"])

    def test_source_and_context_changes_same_ids_invalidate_review(self):
        mutations = [("provisions", "heading", "changed endpoint context"),
                     ("texts", "text", "abc additional document context"),
                     ("segments", "text", "abc additional segment context"),
                     ("documents", "title", "changed source document context")]
        for table, field, value in mutations:
            rows = fixture();relation(rows)
            with workspace() as root:
                data = write_inputs(root, rows);review = reviewed(root, data, rows)
                self.assertEqual(len(graph.build(data, review_catalog=review)["edges"]), 7)
                rows[table][0][field] = value
                write_inputs(root, rows)
                result = graph.build(data, review_catalog=review)
                self.assertEqual(len(result["edges"]), 6, table)
                self.assertIn("SEMANTIC_REVIEW_DEPENDENCIES_STALE", result["candidates"][0]["reason_codes"], table)

    def test_segment_and_document_coordinates_must_both_match_provision(self):
        rows = fixture()
        rows["provisions"][1].update(document_char_start=0, document_char_end=2)
        rows["spans"][1].update(document_char_start=0, document_char_end=2)
        result = self.build(rows)
        self.assertEqual(sum(n["type"] == "Provision" for n in result["nodes"]), 1)
        p2 = next(r for r in result["rejects"] if r["table"] == "provisions" and r["source_record_id"] == "p2")
        self.assertIn("DOCUMENT_COORDINATE_TEXT_MISMATCH", p2["reason_codes"])
        rows = fixture()
        rows["provisions"][1].update(coordinate_space="DOCUMENT_TEXT", segment_char_start=0, segment_char_end=2)
        rows["spans"][1].update(coordinate_space="DOCUMENT_TEXT", segment_char_start=0, segment_char_end=2)
        result = self.build(rows)
        self.assertEqual(sum(n["type"] == "Provision" for n in result["nodes"]), 1)
        self.assertIn("SEGMENT_COORDINATE_TEXT_MISMATCH", next(r for r in result["rejects"] if r["table"] == "provisions")["reason_codes"])

    def test_unverified_document_coordinates_cannot_support_legal_relation(self):
        rows = fixture()
        rows["provisions"][1].update(document_char_start=0, document_char_end=2)
        rows["spans"][1].update(document_char_start=0, document_char_end=2)
        row = relation(rows, source="p2", target="p1")
        row.update(evidence_text="a", evidence_span={"coordinate_space": "DOCUMENT_TEXT", "document_char_start": 0, "document_char_end": 1})
        with workspace() as root:
            data = write_inputs(root, rows);review = reviewed(root, data, rows)
            result = graph.build(data, review_catalog=review)
            self.assertFalse(any(e["type"] == "REFERENCES" for e in result["edges"]))
            reject = next(r for r in result["rejects"] if r["table"] == "relations")
            self.assertIn("ENDPOINT_NOT_PUBLISHED", reject["reason_codes"])
            self.assertIn("EVIDENCE_UNVERIFIED_SOURCE_COORDINATES", reject["reason_codes"])
            self.assertNotEqual(reject["literal_evidence"], "VERIFIED")

    def test_conflicting_legacy_coordinate_aliases_are_blocked(self):
        rows = fixture()
        rows["provisions"][1].update(char_start=0, char_end=2)
        result = self.build(rows)
        self.assertEqual(sum(n["type"] == "Provision" for n in result["nodes"]), 1)
        self.assertIn("COORDINATE_ALIAS_DISAGREEMENT", next(r for r in result["rejects"] if r["table"] == "provisions")["reason_codes"])

    def test_review_does_not_override_endpoint_or_evidence_gate(self):
        rows = fixture();relation(rows, kind="AMENDS")
        with workspace() as root:
            data = write_inputs(root, rows)
            review = reviewed(root, data, rows, operation_verified=True, scope_verified=True, direction_verified=True, temporal_verified=True)
            result = graph.build(data, review_catalog=review)
            self.assertEqual(len(result["edges"]), 6)
            self.assertIn("ENDPOINT_TYPE_NOT_ALLOWED", result["rejects"][0]["reason_codes"])
        rows = fixture();row = relation(rows, source="p2", target="p1")
        row["evidence_text"] = "a";row["evidence_span"].update(segment_char_start=0, segment_char_end=1)
        with workspace() as root:
            data = write_inputs(root, rows);review = reviewed(root, data, rows)
            result = graph.build(data, review_catalog=review)
            self.assertEqual(len(result["edges"]), 6)
            self.assertIn("EVIDENCE_OUTSIDE_SOURCE_PROVISION", result["candidates"][0]["reason_codes"])

    def test_missing_endpoint_citation_and_case_source_are_retained(self):
        rows = fixture();relation(rows, target="missing")
        rows["cases"] = [{"case_id": "case1", "document_id": "d1"}]
        rows["citations"] = [{"citation_id": "citation1", "source_id": "case1", "target_id": "p1", "status": "RESOLVED", "candidate_count": 1,
                              "evidence_text": "bc", "evidence_status": "RESOLVED", "evidence_span":
                              {"coordinate_space": "DOCUMENT_TEXT", "document_char_start": 1, "document_char_end": 3}}]
        result = self.build(rows)
        self.assertIn("MISSING_ENDPOINT", next(r for r in result["rejects"] if r["table"] == "relations")["reason_codes"])
        self.assertEqual(result["candidates"][0]["primary_reason"], "FACT_ENDPOINT_OUT_OF_SCOPE_M1")
        self.assertEqual(result["candidates"][0]["literal_evidence"], "VERIFIED")
        self.assertFalse(any(n["type"] == "Case" for n in result["nodes"]))

    def test_validator_checks_property_references_and_typed_edges(self):
        result = self.build()
        broken = deepcopy(result["nodes"])
        next(n for n in broken if n["type"] == "Provision")["properties"]["version_node_id"] = "rule:version:absent"
        with self.assertRaisesRegex(graph.BuildError, "property reference"):
            graph.validate_graph(broken, result["edges"])
        broken_edges = deepcopy(result["edges"])
        next(e for e in broken_edges if e["type"] == "HAS_IDENTITY")["target_id"] = "rule:document:d1"
        with self.assertRaisesRegex(graph.BuildError, "endpoint types"):
            graph.validate_graph(result["nodes"], broken_edges)
        broken = deepcopy(result["nodes"])
        next(n for n in broken if n["type"] == "Provision")["properties"]["coordinate_verification"]["DOCUMENT_TEXT"] = "UNVERIFIED"
        with self.assertRaisesRegex(graph.BuildError, "Unverified supplied coordinate"):
            graph.validate_graph(broken, result["edges"])

    def test_url_original_preserved_and_no_fetch_claim(self):
        result = self.build()
        doc = next(n for n in result["nodes"] if n["type"] == "Document")
        url = doc["properties"]["normalized_urls"]["source_url"]
        self.assertEqual(url["original"], " https://example.invalid/source ")
        self.assertEqual(url["normalized"], "https://example.invalid/source")
        self.assertEqual(url["access_status"], "NOT_FETCHED_M1")

    def test_input_order_independence_and_lf_export(self):
        rows = fixture()
        with workspace() as root:
            data = write_inputs(root, rows)
            before = {p.relative_to(data).as_posix(): p.read_bytes() for p in data.rglob("*.jsonl")}
            first = graph.build(data)
            second = graph.build(data)
            self.assertEqual(first, second)
            one = root / "one";two = root / "two"
            for target in (one, two):
                graph.export_graph(first, target, config_raw=graph.canonical(graph.CONFIG).encode(), code_hashes={"test": "hash"})
            for p in one.iterdir():
                raw = p.read_bytes()
                self.assertEqual(raw, (two / p.name).read_bytes())
                self.assertNotIn(b"\r\n", raw)
                self.assertTrue(raw.endswith(b"\n") or raw == b"")
            for values in rows.values():
                random.Random(17).shuffle(values)
            write_inputs(root, rows)
            shuffled = graph.build(data)
            self.assertEqual([n["id"] for n in first["nodes"]], [n["id"] for n in shuffled["nodes"]])
            self.assertEqual([e["id"] for e in first["edges"]], [e["id"] for e in shuffled["edges"]])
            # File hashes reflect physical reordering. In-memory source iteration changes
            # with the same file bytes must leave all exported content identical.
            original_loader = graph.load_source
            def reverse_loader(*args, **kwargs):
                source = original_loader(*args, **kwargs)
                source.records.reverse()
                return source
            graph.load_source = reverse_loader
            try:
                reversed_iteration = graph.build(data)
            finally:
                graph.load_source = original_loader
            self.assertEqual(shuffled, reversed_iteration)
            self.assertEqual(set(before), {p.relative_to(data).as_posix() for p in data.rglob("*.jsonl")})

    def test_cli_invalid_config_cannot_disable_gates_or_touch_existing_output(self):
        rows = fixture()
        with workspace() as root:
            write_inputs(root, rows)
            config = root / "config.json"
            bad = deepcopy(graph.CONFIG);bad["legal_relations_require_explicit_review"] = False
            config.write_text(json.dumps(bad), encoding="utf-8")
            out = root / "export";out.mkdir();marker = out / "nodes.jsonl";marker.write_bytes(b"previous validated output\n")
            command = [sys.executable, "-B", str(REPO / "scripts/build_rule_graph.py"), "--root", str(root), "--config", str(config), "--output", str(out)]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 1)
            self.assertIn("mandatory trust gates", process.stderr)
            self.assertEqual(marker.read_bytes(), b"previous validated output\n")

    def test_cli_refuses_output_inside_data(self):
        with workspace() as root:
            data = write_inputs(root, fixture())
            command = [sys.executable, "-B", str(REPO / "scripts/build_rule_graph.py"), "--root", str(root), "--output", str(data / "export"),
                       "--config", str(REPO / "configs/rule_graph_v1.json")]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 1)
            self.assertIn("outside immutable input", process.stderr)
            self.assertFalse((data / "export").exists())


if __name__ == "__main__":
    unittest.main()
