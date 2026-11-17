"""Tests for the M0 audit, not tests for an unimplemented graph builder."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from contextlib import contextmanager
import shutil
import uuid
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inventory_graph_inputs.py"
TEST_TMP = SCRIPT.parents[1] / "outputs" / "milestone_0" / "test_tmp"
TEST_TMP.mkdir(parents=True, exist_ok=True)
@contextmanager
def temporary_workspace():
    # Python 3.13 mkdir(mode=0o700) produces inaccessible ACLs in this Windows sandbox.
    # Use a unique ordinary directory inside the writable workspace instead.
    path = TEST_TMP / ("audit_" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield str(path)
    finally:
        if not path.resolve().is_relative_to(TEST_TMP.resolve()):
            raise RuntimeError("Refusing cleanup outside test workspace")
        shutil.rmtree(path)

SPEC = importlib.util.spec_from_file_location("inventory_graph_inputs", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class InventoryTests(unittest.TestCase):
    def make_data(self, root):
        data = root / "Data"
        for relative, _ in audit.REQUIRED.values():
            path = data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return data

    def test_discover_nested_and_root_layouts(self):
        with temporary_workspace() as tmp:
            root = Path(tmp)
            data = self.make_data(root)
            self.assertEqual(audit.discover_data_root(root), data)
            self.assertEqual(audit.discover_data_root(data), data)

    def test_discover_fails_on_ambiguous_or_absent_layout(self):
        with temporary_workspace() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                audit.discover_data_root(root)
            self.make_data(root)
            path = root / "04_metadata/documents.jsonl"
            path.parent.mkdir()
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "found 2"):
                audit.discover_data_root(root)

    def test_parse_error_reports_line_and_non_objects_rejected(self):
        with temporary_workspace() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text('{}\nnot json\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, ":2: invalid JSON"):
                audit.read_jsonl(path)
            path.write_text('[]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected object"):
                audit.read_jsonl(path)

    def test_utf8_bom_blank_lines_and_missing_versus_null(self):
        with temporary_workspace() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text('\ufeff{"id":"a","x":null}\n\n{"id":"b"}\n', encoding="utf-8")
            result = audit.profile(audit.read_jsonl(path), "id")
            self.assertEqual(result["records"], 2)
            self.assertEqual(result["fields"]["x"]["present"], 1)
            self.assertEqual(result["fields"]["x"]["null"], 1)

    def test_duplicates_count_records_and_values_separately(self):
        result = audit.profile([{"id": "a"}, {"id": "a"}, {"id": "a"}, {"id": "b"}, {}], "id")
        self.assertEqual(result["duplicate_id_values"], ["a"])
        self.assertEqual(result["duplicate_extra_records"], 2)
        self.assertEqual(result["missing_or_empty_ids"], 1)

    def test_policy_requires_all_explicit_true_flags(self):
        row = {"graph_eligible": True, "graph_status": "ACTIVE", "graph_import_policy":
               {"allow": True, "allow_document_and_source_nodes": True, "allow_provision_hierarchy": False}}
        self.assertTrue(audit.eligible_document(row))
        self.assertFalse(audit.eligible_document(row, hierarchy=True))
        row["graph_eligible"] = "true"
        self.assertFalse(audit.eligible_document(row))
        row["graph_eligible"] = True
        row["graph_status"] = "QUARANTINE"
        self.assertFalse(audit.eligible_document(row))
        self.assertFalse(audit.eligible_document({}))

    def test_segment_evidence_checks_owner_bounds_and_exact_text(self):
        segments = {"s": {"document_id": "d", "text": "abcde"}}
        row = {"source_id": "p", "evidence_text": "bc", "evidence_span":
               {"coordinate_space": "SEGMENT_TEXT", "segment_id": "s", "segment_char_start": 1, "segment_char_end": 3}}
        self.assertEqual(audit.check_evidence(row, segments, {}, {"p": "d"}), "EXACT_SLICE")
        self.assertEqual(audit.check_evidence(row, segments, {}, {"p": "other"}), "SOURCE_DOCUMENT_MISMATCH")
        row["evidence_text"] = "bd"
        self.assertEqual(audit.check_evidence(row, segments, {}), "TEXT_MISMATCH")
        row["evidence_span"]["segment_char_end"] = 99
        self.assertEqual(audit.check_evidence(row, segments, {}), "INVALID_BOUNDS")

    def test_case_document_evidence_joins_source_without_document_id_in_span(self):
        row = {"source_id": "case1", "evidence_text": "bc", "evidence_span":
               {"coordinate_space": "DOCUMENT_TEXT", "document_char_start": 1, "document_char_end": 3}}
        documents = {"d": {"document_id": "d", "text": "abcd"}}
        self.assertEqual(audit.check_evidence(row, {}, documents, {"case1": "d"}), "EXACT_SLICE")
        self.assertEqual(audit.check_evidence(row, {}, documents), "MISSING_SOURCE")

    def test_missing_evidence_and_unsupported_space_are_explicit(self):
        self.assertEqual(audit.check_evidence({}, {}, {}), "MISSING_SPAN_OR_TEXT")
        row = {"evidence_text": "x", "evidence_span": {"coordinate_space": "UNRESOLVED"}}
        self.assertEqual(audit.check_evidence(row, {}, {}), "UNSUPPORTED_COORDINATE_SPACE")

    def test_inventory_is_deterministic_and_never_changes_input(self):
        with temporary_workspace() as tmp:
            root = Path(tmp)
            data = self.make_data(root)
            before = {p: p.read_bytes() for p in data.rglob("*") if p.is_file()}
            first = audit.inventory(root)
            second = audit.inventory(root)
            self.assertEqual(first, second)
            self.assertEqual(before, {p: p.read_bytes() for p in data.rglob("*") if p.is_file()})
            self.assertEqual(first["scope"], "inventory_only_no_graph_export")

    def test_missing_required_input_fails_informatively(self):
        with temporary_workspace() as tmp:
            root = Path(tmp)
            data = self.make_data(root)
            (data / audit.REQUIRED["cases"][0]).unlink()
            with self.assertRaisesRegex(ValueError, "Required input absent.*cases.jsonl"):
                audit.inventory(root)

    def test_cli_refuses_to_write_inside_input_directory(self):
        with temporary_workspace() as tmp:
            root = Path(tmp)
            data = self.make_data(root)
            path = data / "do_not_write.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--output", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("outside immutable input directory", result.stderr)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
