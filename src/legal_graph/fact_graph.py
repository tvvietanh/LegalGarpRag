"""Truthful Case-level Fact Graph; no unreviewed actor/event/assertion extraction."""
import argparse
from collections import Counter
from pathlib import Path
import sys
from urllib.parse import quote

from .rule_graph import BuildError, canonical, digest, digest_bytes, document_reasons, load_source, unique_index
from .ontology_graph import read_rule_bundle

SCHEMA = "fact-graph-v1"


def case_id(raw):
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise BuildError("Invalid Case ID")
    return "fact:case:" + quote(raw, safe="")


def extraction_reasons(row, metadata):
    reasons = []
    if row.get("case_extracted_facts_enabled") is not True:
        reasons.append("CASE_FACT_EXTRACTION_DISABLED_OR_UNVERIFIED")
    if metadata.get("case_extracted_facts_enabled") is not True:
        reasons.append("DOCUMENT_FACT_EXTRACTION_DISABLED_OR_UNVERIFIED")
    # Even flags becoming true cannot manufacture a reviewed extraction artifact.
    reasons.append("REVIEWED_EXTRACTION_ARTIFACT_REQUIRED")
    if row.get("case_sections_review_status") != "REVIEWED":
        reasons.append("LEGACY_CASE_SECTIONS_NOT_REVIEWED")
    if not isinstance(row.get("full_text"), str) or not row["full_text"].strip():
        reasons.append("FULL_TEXT_SOURCE_REVIEW_REQUIRED")
    reasons.append("OWN_HEADER_COURT_DATE_REVIEW_REQUIRED")
    return reasons


def build(data, rule_dir):
    rule_nodes, rule_manifest, rule_hash = read_rule_bundle(rule_dir)
    cases = load_source(data, "cases", "03_case_data/cases.jsonl", "case_id")
    metadata = load_source(data, "metadata", "04_metadata/documents.jsonl", "document_id")
    case_index, meta_index = unique_index(cases), unique_index(metadata)
    dependencies = {item["path"]: item for item in rule_manifest["inputs"]}
    for source in (cases, metadata):
        if dependencies.get(source.path, {}).get("sha256") != source.sha256:
            raise BuildError("Stale Case/metadata source versus reviewed Rule snapshot: " + source.path)
    nodes, rejects, queue = [], [], []
    primary = Counter()
    external_docs = set()
    for raw_id, record in sorted(case_index.items()):
        row = record.row
        meta = meta_index.get(row.get("document_id"))
        reasons = list(document_reasons(row))
        raw_document_id = row.get("document_id")
        document_id = "rule:document:" + quote(raw_document_id, safe="") if isinstance(raw_document_id, str) else ""
        if meta is None:
            reasons.append("SOURCE_DOCUMENT_METADATA_MISSING")
        else:
            if document_reasons(meta.row):
                reasons.append("SOURCE_DOCUMENT_POLICY_DENIED")
            if meta.row.get("source_group") != "JUDICIAL":
                reasons.append("SOURCE_DOCUMENT_NOT_JUDICIAL")
        external = rule_nodes.get(document_id)
        if external is None or external.get("type") != "Document":
            reasons.append("DOCUMENT_ENDPOINT_NOT_PUBLISHED")
        eligible = not reasons
        pending = extraction_reasons(row, meta.row if meta else {})
        queue.append({"id": "review:" + digest([SCHEMA, record.source_record_id]), **record.ref(), "source_case_id": raw_id,
                      "case_node_published": eligible, "primary_reason": (reasons + pending)[0],
                      "reason_codes": list(dict.fromkeys(reasons + pending)), "extracted_facts_created": 0,
                      "source_section_review_status": row.get("case_sections_review_status", "MISSING"),
                      "instruction": "No assertions from titles/legacy sections. Source permission and independent reviewed extraction are required."})
        if reasons:
            primary[reasons[0]] += 1
            rejects.append({"id": "reject:" + digest([SCHEMA, raw_id]), **record.ref(), "outcome": "EXCLUDED",
                            "primary_reason": reasons[0], "reason_codes": list(dict.fromkeys(reasons)), "record_count": 1})
            continue
        external_docs.add(document_id)
        original = {key: row[key] for key in ("case_id", "document_id", "record_classification", "graph_status", "graph_eligible", "graph_role",
                   "graph_import_policy", "case_extracted_facts_enabled", "case_sections_review_status", "local_source_status", "source_url",
                   "source_references", "view_url", "official_url", "canonical_url") if key in row}
        identity = {key: row[key] for key in ("case_id", "document_id", "official_document_id", "case_number", "title", "record_classification") if key in row}
        identity["verification_status"] = "SOURCE_IDENTITY_OBSERVATION"
        text = row.get("full_text")
        full_text = {"source_path": cases.path, "source_record_id": raw_id, "source_field": "full_text", "status": "MISSING_SOURCE_TEXT"}
        if isinstance(text, str) and text:
            full_text.update({"status": "SOURCE_TEXT_REFERENCE_ONLY", "sha256": digest_bytes(text.encode("utf-8")), "coordinate_space": "CASE_FULL_TEXT",
                              "char_start": 0, "char_end": len(text)})
        properties = {**record.ref(), "source_properties": original, "source_identity": identity,
                      "document_node_id": document_id, "full_text_reference": full_text,
                      "provenance": [record.ref(), meta.ref(), {"rule_document_node_id": document_id, "rule_node_sha256": digest(external), "rule_manifest_sha256": rule_hash}],
                      "verification": {"structural": "VERIFIED", "semantic_facts": "UNVERIFIED", "court_and_decision_date": "UNVERIFIED", "temporal": "UNVERIFIED"},
                      "fact_extraction_status": "PENDING_PERMISSION_AND_REVIEW" if any("DISABLED" in reason for reason in pending) else "PENDING_REVIEWED_EXTRACTION",
                      "extraction_pending_reasons": pending, "legacy_sections_imported_as_facts": False,
                      "omitted_legacy_claim_fields": ["facts", "reasoning", "decision", "features", "court", "decision_date"],
                      "temporal": {"assessment": "UNKNOWN", "verified_applicability": False}, "url_verification": "NOT_FETCHED_M3"}
        nodes.append({"id": case_id(raw_id), "type": "Case", "layer": "fact", "properties": properties})
    if len({n["id"] for n in nodes}) != len(nodes):
        raise BuildError("Duplicate published Case ID")
    for node in nodes:
        props = node["properties"]
        if props["document_node_id"] not in rule_nodes or any(field in props["source_properties"] for field in ("facts", "reasoning", "decision", "features", "court", "decision_date")):
            raise BuildError("Invalid Case reference or unreviewed legacy claims leaked")
    quality = {"schema_version": SCHEMA, "validation_verdict": "PASS_WITH_SOURCE_LIMITATIONS",
               "coverage": {"case_input_records": len(case_index), "case_nodes": len(nodes), "excluded_cases": len(rejects),
                            "source_active_cases": sum(r.row.get("graph_status") == "ACTIVE" for r in cases.records),
                            "source_case_fact_flags_true": sum(r.row.get("case_extracted_facts_enabled") is True for r in cases.records),
                            "review_queue_records": len(queue), "Actor": 0, "Event": 0, "FactAssertion": 0, "fact_edges": 0},
               "excluded_primary_reasons": dict(sorted(primary.items())),
               "case_section_source_status": dict(sorted(Counter(r.row.get("case_sections_review_status", "MISSING") for r in cases.records).items())),
               "checks": {"duplicate_ids": 0, "missing_document_node_references": 0, "allegations_promoted_to_findings": 0,
                          "policy_bypass_extractions": 0, "verified_court_date_claims": 0, "verified_applicability_claims": 0},
               "limitations": ["fact extraction pending: no approved extraction artifacts; disabled source flags respected.",
                               "Case source identity/full-text references are not verified allegations, findings, or decisions.",
                               "No Actor/Event/FactAssertion or case-to-law applicability is inferred."]}
    return {"nodes": sorted(nodes, key=lambda n: n["id"]), "edges": [], "rejects": sorted(rejects, key=lambda r: r["id"]),
            "candidates": [], "review_queue": sorted(queue, key=lambda r: r["id"]), "quality_report": quality,
            "dependencies": {"schema_version": SCHEMA, "inputs": [cases.manifest(), metadata.manifest()], "rule_manifest_sha256": rule_hash,
                             "rule_build_id": rule_manifest["build_id"], "external_rule_document_ids": sorted(external_docs)}}


def export(result, output, code_hashes):
    artifacts = {}
    for key in ("nodes", "edges", "rejects", "candidates", "review_queue"):
        artifacts[key + ".jsonl"] = b"".join((canonical(row) + "\n").encode("utf-8") for row in result[key])
    artifacts["quality_report.json"] = (canonical(result["quality_report"]) + "\n").encode("utf-8")
    deps = {**result["dependencies"], "source_code_sha256": code_hashes}
    manifest = {**deps, "milestone": "M3", "build_id": "build:" + digest(deps), "validation_verdict": "PASS_WITH_SOURCE_LIMITATIONS",
                "counts": {"nodes": len(result["nodes"]), "edges": 0, "node_types": {"Case": len(result["nodes"])}, "nodes_by_layer": {"fact": len(result["nodes"])}},
                "coverage": result["quality_report"]["coverage"], "artifacts": {name: {"bytes": len(raw), "sha256": digest_bytes(raw)} for name, raw in sorted(artifacts.items())},
                "determinism": {"encoding": "UTF-8", "newline": "LF", "runtime_timestamps": False}}
    artifacts["manifest.json"] = (canonical(manifest) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in artifacts.items():
        (output / (name + ".tmp")).write_bytes(raw)
        (output / (name + ".tmp")).replace(output / name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("Data"))
    parser.add_argument("--rule", type=Path, default=Path("outputs/rule_graph"))
    parser.add_argument("--output", type=Path, default=Path("outputs/fact_graph"))
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() == args.data.resolve() or args.data.resolve() in args.output.resolve().parents:
            raise BuildError("Output cannot be inside immutable Data")
        result = build(args.data, args.rule)
        if digest_bytes((args.rule / "manifest.json").read_bytes()) != result["dependencies"]["rule_manifest_sha256"]:
            raise BuildError("Rule snapshot changed during Case build")
        for item in result["dependencies"]["inputs"]:
            if digest_bytes((args.data / item["path"]).read_bytes()) != item["sha256"]:
                raise BuildError("Case source changed during build")
        repo = Path(__file__).resolve().parents[2]
        paths = [Path(__file__).resolve(), repo / "scripts/build_fact_graph.py", repo / "src/legal_graph/rule_graph.py", repo / "src/legal_graph/ontology_graph.py"]
        codes = {p.relative_to(repo).as_posix(): digest_bytes(p.read_bytes()) for p in paths}
        manifest = export(result, args.output, codes)
        print(f"M3 PASS_WITH_SOURCE_LIMITATIONS: Case={manifest['counts']['nodes']} edges=0 extraction_queue={manifest['coverage']['review_queue_records']}; no extracted facts.")
        return 0
    except (BuildError, ValueError, TypeError, KeyError, OSError) as exc:
        print("M3 FAIL: " + str(exc), file=sys.stderr)
        return 1
