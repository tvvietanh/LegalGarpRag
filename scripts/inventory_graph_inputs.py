"""Read-only Milestone 0 audit. Standard library only; does not construct a graph."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile


REQUIRED = {
    "metadata": ("04_metadata/documents.jsonl", "document_id"),
    "documents": ("02_processed_data/documents.jsonl", "document_id"),
    "segments": ("02_processed_data/segments.jsonl", "segment_id"),
    "headings": ("02_processed_data/hierarchy_headings.jsonl", "id"),
    "provisions": ("02_processed_data/provisions.jsonl", "provision_id"),
    "quarantine": ("02_processed_data/quarantined_provisions.jsonl", "provision_id"),
    "cases": ("03_case_data/cases.jsonl", "case_id"),
    "spans": ("05_provenance/provision_spans.jsonl", "provision_id"),
    "identities": ("06_temporal/provision_identities.jsonl", "provision_identity_id"),
    "versions": ("06_temporal/provision_versions.jsonl", "provision_version_id"),
    "changes": ("06_temporal/legal_changes.jsonl", "change_id"),
    "relations": ("07_research_extensions/knowledge/accepted_relation_edges.jsonl", "edge_id"),
    "issues": ("07_research_extensions/knowledge/issues.jsonl", "issue_id"),
    "issue_edges": ("07_research_extensions/knowledge/issue_edges.jsonl", None),
    "citations": ("07_research_extensions/knowledge/citations.jsonl", "citation_id"),
}
STATUS_FIELDS = (
    "graph_status", "graph_eligible", "graph_role", "source_group", "record_classification",
    "metadata_verified", "temporal_verified", "local_source_status", "source_content_verified",
    "case_sections_review_status", "case_extracted_facts_enabled", "temporal_status",
    "provision_temporal_verified", "evidence_status", "provenance_status", "resolution_status",
    "resolution_scope", "type", "status", "operation", "coordinate_space", "level", "label",
)


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def discover_data_root(root: Path) -> Path:
    candidates = [p for p in (root, root / "Data") if (p / REQUIRED["metadata"][0]).is_file()]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one dataset at {root} or {root / 'Data'}; found {len(candidates)}")
    return candidates[0]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def profile(rows: list[dict], key: str | None) -> dict:
    fields = sorted({k for row in rows for k in row})
    result = {
        "records": len(rows),
        "fields": {k: {"present": sum(k in row for row in rows),
                        "null": sum(row.get(k) is None for row in rows if k in row),
                        "types": dict(sorted(Counter(type(row[k]).__name__ for row in rows if k in row).items()))}
                   for k in fields},
        "status_counts": {k: dict(sorted(Counter(canonical(row[k]) for row in rows if k in row).items()))
                          for k in STATUS_FIELDS if k in fields},
    }
    if key:
        ids = [row[key] for row in rows if isinstance(row.get(key), str) and row[key]]
        result["id_field"] = key
        result["missing_or_empty_ids"] = len(rows) - len(ids)
        result["duplicate_id_values"] = sorted(k for k, n in Counter(ids).items() if n > 1)
        result["duplicate_extra_records"] = len(ids) - len(set(ids))
    return result


def eligible_document(row: dict, hierarchy: bool = False) -> bool:
    policy = row.get("graph_import_policy", {})
    return (row.get("graph_eligible") is True and row.get("graph_status") == "ACTIVE"
            and policy.get("allow") is True and policy.get("allow_document_and_source_nodes") is True
            and (not hierarchy or policy.get("allow_provision_hierarchy") is True))


def check_evidence(row: dict, segments: dict, documents: dict, source_documents: dict | None = None) -> str:
    span = row.get("evidence_span")
    text = row.get("evidence_text", row.get("evidence"))
    if not isinstance(span, dict) or not isinstance(text, str) or not text:
        return "MISSING_SPAN_OR_TEXT"
    # Audit a literal slice in its declared coordinate space, never a fuzzy match.
    if span.get("coordinate_space") == "SEGMENT_TEXT":
        source = segments.get(span.get("segment_id"))
        start, end = span.get("segment_char_start", span.get("char_start")), span.get("segment_char_end", span.get("char_end"))
    elif span.get("coordinate_space") == "DOCUMENT_TEXT":
        document_id = span.get("document_id") or (source_documents or {}).get(row.get("source_id"))
        source = documents.get(document_id)
        start, end = span.get("document_char_start", span.get("char_start")), span.get("document_char_end", span.get("char_end"))
    else:
        return "UNSUPPORTED_COORDINATE_SPACE"
    if source is None:
        return "MISSING_SOURCE"
    owner = (source_documents or {}).get(row.get("source_id"))
    if owner is not None and source.get("document_id") != owner:
        return "SOURCE_DOCUMENT_MISMATCH"
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(source.get("text", "")):
        return "INVALID_BOUNDS"
    return "EXACT_SLICE" if source["text"][start:end] == text else "TEXT_MISMATCH"


def inventory(root: Path) -> dict:
    data = discover_data_root(root)
    files = sorted((p for p in data.rglob("*") if p.is_file()), key=lambda p: p.relative_to(data).as_posix())
    snapshots = [{"path": p.relative_to(data).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in files]
    rows = {}
    for name, (relative, _) in REQUIRED.items():
        path = data / relative
        if not path.is_file():
            raise ValueError(f"Required input absent: {path}")
        rows[name] = read_jsonl(path)
    profiles = {}
    for p in files:
        if p.suffix == ".jsonl":
            name = next((k for k, (rel, _) in REQUIRED.items() if rel == p.relative_to(data).as_posix()), None)
            profiles[p.relative_to(data).as_posix()] = profile(rows[name] if name else read_jsonl(p), REQUIRED[name][1] if name else None)
    index = {name: {r[key]: r for r in rows[name] if key in r} for name, (_, key) in REQUIRED.items() if key}
    meta, prov, cases, ids, versions = (index[n] for n in ("metadata", "provisions", "cases", "identities", "versions"))
    allowed_docs = {k for k, v in meta.items() if eligible_document(v)}
    hierarchy_docs = {k for k, v in meta.items() if eligible_document(v, True)}
    allowed_provs = {k for k, v in prov.items() if v.get("document_id") in hierarchy_docs}
    allowed_cases = {k for k, v in cases.items() if eligible_document(v) and v.get("document_id") in allowed_docs}
    registry = {**{k: "Document" for k in meta}, **{k: "Provision" for k in prov}, **{k: "Case" for k in cases},
                **{k: "LegalIssue" for k in index["issues"]}, **{k: "ProvisionIdentity" for k in ids}}
    known = set(registry)
    trusted = allowed_docs | allowed_provs | allowed_cases | set(index["issues"])
    parent_ids = set(meta) | set(prov)
    source_documents = {**{k: k for k in meta}, **{k: v.get("document_id") for k, v in prov.items()},
                        **{k: v.get("document_id") for k, v in cases.items()}}
    joins = {
        "provision_document_missing": sorted(k for k, v in prov.items() if v.get("document_id") not in meta),
        "provision_parent_missing": sorted(k for k, v in prov.items() if v.get("parent_id") not in parent_ids),
        "provision_parent_wrong_document": sorted(k for k, v in prov.items() if v.get("parent_id") in prov and prov[v["parent_id"]].get("document_id") != v.get("document_id")),
        "provision_identity_missing": sorted(k for k, v in prov.items() if v.get("provision_identity_id") not in ids),
        "provision_version_missing": sorted(k for k, v in prov.items() if v.get("provision_version_id") not in versions),
        "version_identity_missing": sorted(k for k, v in versions.items() if v.get("provision_identity_id") not in ids),
        "version_document_missing": sorted(k for k, v in versions.items() if v.get("source_document_version_id") not in meta),
        "case_document_missing": sorted(k for k, v in cases.items() if v.get("document_id") not in meta),
        "provision_span_missing": sorted(set(prov) - set(index["spans"])),
        "quarantine_overlap_provisions": sorted(set(index["quarantine"]) & set(prov)),
        "shared_provision_version_raw_ids": len(set(prov) & set(versions)),
    }
    edges = {}
    for name in ("relations", "issue_edges", "citations"):
        endpoint_missing = []
        types = Counter()
        gated = Counter()
        evidence = Counter()
        for n, row in enumerate(rows[name], 1):
            s, t = row.get("source_id"), row.get("target_id")
            missing = [side for side, val in (("source", s), ("target", t)) if val not in known]
            if missing:
                endpoint_missing.append({"record_number": n, "source_id": s, "target_id": t, "missing": missing})
            types[f"{registry.get(s, 'MISSING')}->{registry.get(t, 'MISSING')}"] += 1
            gated["ENDPOINTS_POLICY_ELIGIBLE" if s in trusted and t in trusted else "EXCLUDED_ENDPOINT_OR_UNRESOLVED"] += 1
            evidence[check_evidence(row, index["segments"], index["documents"], source_documents)] += 1
        edges[name] = {"records": len(rows[name]), "missing_endpoint_records": endpoint_missing,
                       "missing_endpoint_count": len(endpoint_missing), "endpoint_types": dict(sorted(types.items())),
                       "policy_screen_only_not_semantic_approval": dict(sorted(gated.items())), "evidence_slice_check": dict(sorted(evidence.items()))}
    provision_slices = Counter()
    eligible_provision_slices = Counter()
    provision_slice_findings = []
    for row in rows["provisions"]:
        status = check_evidence({"source_id": row["provision_id"], "evidence_text": row["text"], "evidence_span": row}, index["segments"], index["documents"], source_documents)
        provision_slices[status] += 1
        if row["provision_id"] in allowed_provs:
            eligible_provision_slices[status] += 1
        if status != "EXACT_SLICE":
            provision_slice_findings.append({"provision_id": row["provision_id"], "document_id": row["document_id"],
                                             "status": status, "policy_eligible": row["provision_id"] in allowed_provs,
                                             "has_excluded_annotation_spans": bool(row.get("excluded_annotation_spans"))})
    exclusion_partitions = Counter()
    for k, row in prov.items():
        document = meta.get(row.get("document_id"), {})
        reason = ("ELIGIBLE_POLICY_SCREEN" if k in allowed_provs else
                  "DOCUMENT_QUARANTINE_OR_INELIGIBLE" if not eligible_document(document) else "DOCUMENT_HIERARCHY_DENIED")
        exclusion_partitions[reason] += 1
    local_paths = Counter()
    missing_claimed = []
    for row in rows["metadata"]:
        value = row.get("local_file_path")
        if not value:
            local_paths["NO_PATH"] += 1
        elif (data / value).is_file():
            local_paths["EXISTS"] += 1
        else:
            local_paths["MISSING"] += 1
            missing_claimed.append({"document_id": row["document_id"], "path": value})
    archive_reports = []
    for p in files:
        if p.suffix == ".zip":
            with zipfile.ZipFile(p) as archive:
                members = sorted((m for m in archive.infolist() if not m.is_dir()), key=lambda m: m.filename)
                same, absent, different = [], [], []
                for member in members:
                    target = data / member.filename
                    if not target.is_file():
                        absent.append(member.filename)
                    else:
                        with archive.open(member) as handle:
                            digest = hashlib.file_digest(handle, "sha256").hexdigest()
                        (same if sha256_file(target) == digest else different).append(member.filename)
                archive_reports.append({"path": p.relative_to(data).as_posix(), "member_files": len(members),
                                        "uncompressed_bytes": sum(m.file_size for m in members),
                                        "same_as_local": len(same), "absent_locally": absent, "different_from_local": different})
    return {
        "schema": "milestone-0-inventory-v1", "scope": "inventory_only_no_graph_export",
        "data_root": data.relative_to(root).as_posix(), "files": snapshots,
        "dataset_digest": hashlib.sha256(canonical(snapshots).encode()).hexdigest(),
        "file_count": len(files), "total_bytes": sum(x["bytes"] for x in snapshots),
        "extensions": dict(sorted(Counter(p.suffix for p in files).items())),
        "profiles": profiles, "joins": joins, "edge_audits": edges,
        "policy_screen": {"document_nodes": len(allowed_docs), "hierarchy_documents": len(hierarchy_docs),
                          "hierarchy_document_ids": sorted(hierarchy_docs), "provisions": len(allowed_provs),
                          "excluded_provisions_by_document_policy": len(prov) - len(allowed_provs),
                          "provision_exclusive_reason_partition": dict(sorted(exclusion_partitions.items())),
                          "quarantined_candidates_excluded": len(rows["quarantine"]),
                          "case_nodes": len(allowed_cases), "case_ids": sorted(allowed_cases),
                          "excluded_cases": len(cases) - len(allowed_cases),
                          "allowed_cases_extracted_facts_enabled": sum(cases[k].get("case_extracted_facts_enabled") is True for k in allowed_cases)},
        "provision_literal_segment_slice_check": dict(sorted(provision_slices.items())),
        "eligible_provision_literal_segment_slice_check": dict(sorted(eligible_provision_slices.items())),
        "provision_slice_findings": sorted(provision_slice_findings, key=lambda x: x["provision_id"]),
        "metadata_local_paths": dict(sorted(local_paths.items())), "metadata_missing_claimed_paths": missing_claimed,
        "archives": archive_reports,
        "notes": ["Policy screening is an upper bound, not semantic or evidence approval.",
                  "Null versus missing is retained in field profiles; no source data changed.",
                  "Archive members are streamed for comparison; no extraction or promotion to trusted data.",
                  "No legal assertion or effective-date claim is validated by this inventory."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path, help="Compare input hashes with an earlier inventory")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        data = discover_data_root(root).resolve()
        output = args.output.resolve()
        if output == data or data in output.parents:
            raise ValueError("Audit output must be outside immutable input directory")
        result = inventory(root)
        if args.compare:
            previous = json.loads(args.compare.read_text(encoding="utf-8"))
            if previous["files"] != result["files"]:
                raise ValueError("Input snapshot differs from comparison report")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"Inventory OK: {result['file_count']} files; digest={result['dataset_digest']}")
        print(f"Policy screen: {result['policy_screen']['document_nodes']} documents, {result['policy_screen']['provisions']} provisions, {result['policy_screen']['case_nodes']} cases")
        return 0
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"Inventory ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
