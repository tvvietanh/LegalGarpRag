"""Deterministic, evidence-gated Rule Graph. Inputs are immutable; no network I/O."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import quote


SCHEMA = "rule-graph-v1"
TABLES = {
    "documents": ("04_metadata/documents.jsonl", "document_id"),
    "texts": ("02_processed_data/documents.jsonl", "document_id"),
    "segments": ("02_processed_data/segments.jsonl", "segment_id"),
    "headings": ("02_processed_data/hierarchy_headings.jsonl", "id"),
    "provisions": ("02_processed_data/provisions.jsonl", "provision_id"),
    "quarantine": ("02_processed_data/quarantined_provisions.jsonl", "provision_id"),
    "spans": ("05_provenance/provision_spans.jsonl", "provision_id"),
    "identities": ("06_temporal/provision_identities.jsonl", "provision_identity_id"),
    "versions": ("06_temporal/provision_versions.jsonl", "provision_version_id"),
    "cases": ("03_case_data/cases.jsonl", "case_id"),
    "relations": ("07_research_extensions/knowledge/accepted_relation_edges.jsonl", "edge_id"),
    "citations": ("07_research_extensions/knowledge/citations.jsonl", "citation_id"),
    "changes": ("06_temporal/legal_changes.jsonl", "change_id"),
}
CONFIG = {"schema_version": SCHEMA, "layers": ["rule"], "legal_relations_require_explicit_review": True,
          "temporal_claims_enabled": False, "url_normalization": "strip_only_no_fetch"}
NODE_TYPES = {"document": "Document", "provision": "Provision", "identity": "ProvisionIdentity", "version": "ProvisionVersion"}
RELATION_ENDPOINTS = {
    "CITES": {("Document", "Document"), ("Provision", "Provision"), ("Provision", "Document")},
    "REFERENCES": {("Document", "Document"), ("Provision", "Provision"), ("Provision", "Document")},
    "AMENDS": {("Document", "Document"), ("Provision", "ProvisionIdentity")},
    "REPEALS": {("Document", "Document"), ("Provision", "ProvisionIdentity")},
    "REPLACES": {("Document", "Document"), ("Provision", "ProvisionIdentity")},
}
SPAN_KEYS = ("document_id", "segment_id", "coordinate_space", "segment_char_start", "segment_char_end",
             "document_char_start", "document_char_end", "page_start", "page_end", "source_unit_type", "provenance_status")
TEMPORAL_KEYS = ("valid_from", "valid_to", "temporal_status", "temporal_evidence", "provision_temporal_verified",
                 "temporal_coverage_as_of", "introduced_by_change_id", "ended_by_change_id", "effective_from",
                 "effective_to", "temporal_verified", "status", "legal_status", "consolidation_as_of")


class BuildError(ValueError):
    """Fail closed before replacing any published output."""


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value) -> str:
    return digest_bytes(canonical(value).encode("utf-8"))


def qid(kind: str, raw: str) -> str:
    if kind not in NODE_TYPES or not isinstance(raw, str) or not raw or raw != raw.strip():
        raise BuildError(f"Invalid qualified ID: {kind!r}, {raw!r}")
    return "rule:" + kind + ":" + quote(raw, safe="")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BuildError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def parse_json(text: str):
    def reject_constant(value):
        raise BuildError(f"Non-finite JSON constant: {value}")
    return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=reject_constant)


@dataclass(frozen=True)
class Record:
    table: str
    source_path: str
    source_sha256: str
    source_record_id: str
    source_record_sha256: str
    row: dict

    def ref(self) -> dict:
        return {"source_path": self.source_path, "source_sha256": self.source_sha256,
                "source_record_id": self.source_record_id, "source_record_sha256": self.source_record_sha256}


@dataclass
class Source:
    path: str
    sha256: str
    size_bytes: int
    records: list[Record]

    def manifest(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.size_bytes, "records": len(self.records)}


def load_source(data: Path, table: str, relative: str, key: str) -> Source:
    path = data / relative
    if not path.is_file():
        raise BuildError(f"Required input absent: {relative}")
    raw = path.read_bytes()
    file_hash = digest_bytes(raw)
    records = []
    for number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = parse_json(line)
        except (ValueError, BuildError) as exc:
            raise BuildError(f"{relative}:{number}: {exc}") from exc
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key] or row[key] != row[key].strip():
            raise BuildError(f"{relative}:{number}: expected object with nonempty untrimmed string {key}")
        records.append(Record(table, relative, file_hash, row[key], digest(row), row))
    return Source(relative, file_hash, len(raw), sorted(records, key=lambda r: (r.source_record_id, r.source_record_sha256)))


def unique_index(source: Source) -> dict[str, Record]:
    result = {}
    for record in source.records:
        if record.source_record_id in result:
            previous = result[record.source_record_id]
            kind = "CONFLICTING_DUPLICATE" if previous.source_record_sha256 != record.source_record_sha256 else "DUPLICATE_ID"
            raise BuildError(f"{kind}: {source.path}:{record.source_record_id}; no last-write-wins")
        result[record.source_record_id] = record
    return result


def discover_data(root: Path) -> Path:
    candidates = [p for p in (root, root / "Data") if (p / TABLES["documents"][0]).is_file()]
    if len(candidates) != 1:
        raise BuildError("Expected exactly one dataset at root or root/Data")
    return candidates[0]


def document_reasons(row: dict) -> list[str]:
    policy = row.get("graph_import_policy")
    policy = policy if isinstance(policy, dict) else {}
    reasons = []
    if row.get("graph_status") != "ACTIVE":
        reasons.append("DOCUMENT_NOT_ACTIVE")
    if row.get("graph_eligible") is not True:
        reasons.append("DOCUMENT_INELIGIBLE")
    if policy.get("allow") is not True:
        reasons.append("IMPORT_POLICY_DENIED")
    if policy.get("allow_document_and_source_nodes") is not True:
        reasons.append("DOCUMENT_NODES_DENIED")
    return reasons


def source_span(row: dict) -> dict:
    keys = SPAN_KEYS + ("char_start", "char_end", "line_start", "line_end", "span_scope", "page_status", "excluded_annotation_spans")
    return {k: row[k] for k in keys if k in row}


def evidence_check(row: dict, indexes: dict, owner: str | None, source_provision: dict | None = None) -> tuple[str, list[Record]]:
    span = row.get("evidence_span")
    text = row.get("evidence_text", row.get("evidence"))
    if not isinstance(span, dict) or not isinstance(text, str) or not text:
        return "EVIDENCE_MISSING_SPAN_OR_TEXT", []
    if span.get("coordinate_space") == "SEGMENT_TEXT":
        record = indexes["segments"].get(span.get("segment_id"))
        start, end = span.get("segment_char_start", span.get("char_start")), span.get("segment_char_end", span.get("char_end"))
    elif span.get("coordinate_space") == "DOCUMENT_TEXT":
        declared = span.get("document_id", owner)
        if declared != owner:
            return "EVIDENCE_OWNER_MISMATCH", []
        record = indexes["texts"].get(declared)
        start, end = span.get("document_char_start", span.get("char_start")), span.get("document_char_end", span.get("char_end"))
    else:
        return "EVIDENCE_UNSUPPORTED_COORDINATE_SPACE", []
    if record is None:
        return "EVIDENCE_SOURCE_MISSING", []
    if owner is None or record.row.get("document_id") != owner:
        return "EVIDENCE_OWNER_MISMATCH", [record]
    source_text = record.row.get("text")
    if not isinstance(source_text, str) or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source_text):
        return "EVIDENCE_INVALID_BOUNDS", [record]
    if source_text[start:end] != text:
        return "EVIDENCE_TEXT_MISMATCH", [record]
    if source_provision is not None:
        if span.get("coordinate_space") == "SEGMENT_TEXT":
            lower, upper = source_provision.get("segment_char_start"), source_provision.get("segment_char_end")
            same_segment = span.get("segment_id") == source_provision.get("segment_id")
        else:
            lower, upper = source_provision.get("document_char_start"), source_provision.get("document_char_end")
            same_segment = True
        if (type(lower) is not int or type(upper) is not int or not 0 <= lower < upper <= len(source_text) or
                source_text[lower:upper] != source_provision.get("text")):
            return "EVIDENCE_UNVERIFIED_SOURCE_COORDINATES", [record]
        if not same_segment or type(lower) is not int or type(upper) is not int or not lower <= start < end <= upper:
            return "EVIDENCE_OUTSIDE_SOURCE_PROVISION", [record]
    return "VERIFIED", [record]


def provision_coordinate_checks(row: dict, indexes: dict) -> tuple[list[str], list[Record], dict]:
    """Verify every supplied coordinate space; no segment-only proof of document bounds."""
    owner = row.get("document_id")
    status, supports = evidence_check({"evidence_text": row.get("text"), "evidence_span": row}, indexes, owner)
    reasons = [] if status == "VERIFIED" else [status]
    verification = {row.get("coordinate_space", "UNSPECIFIED"): status}
    for space, keys in (("SEGMENT_TEXT", ("segment_char_start", "segment_char_end")),
                        ("DOCUMENT_TEXT", ("document_char_start", "document_char_end"))):
        if any(key in row for key in keys):
            span = {**row, "coordinate_space": space}
            alternate, context = evidence_check({"evidence_text": row.get("text"), "evidence_span": span}, indexes, owner)
            supports.extend(context)
            verification[space] = alternate
            if alternate != "VERIFIED":
                code = space.removesuffix("_TEXT") + "_COORDINATE_" + alternate.removeprefix("EVIDENCE_")
                reasons.append(code)
    # Legacy char_start/end are aliases in the declared coordinate_space, not a
    # third independent source. Reject contradictory or incomplete aliases.
    if any(key in row for key in ("char_start", "char_end")):
        declared = row.get("coordinate_space")
        keys = ("segment_char_start", "segment_char_end") if declared == "SEGMENT_TEXT" else ("document_char_start", "document_char_end")
        if (not all(key in row for key in ("char_start", "char_end", *keys)) or
                any(type(row[key]) is not int for key in ("char_start", "char_end", *keys)) or
                (row["char_start"], row["char_end"]) != (row[keys[0]], row[keys[1]])):
            reasons.append("COORDINATE_ALIAS_DISAGREEMENT")
    return list(dict.fromkeys(reasons)), supports, verification


def cycle_members(provisions: dict[str, Record]) -> set[str]:
    done, cycles = set(), set()
    for start in sorted(provisions):
        path, positions = [], {}
        current = start
        while current in provisions and current not in done:
            if current in positions:
                cycles.update(path[positions[current]:])
                break
            positions[current] = len(path)
            path.append(current)
            current = provisions[current].row.get("parent_id")
        done.update(path)
    return cycles


def temporal(row: dict, kind: str) -> dict:
    # M1 publishes source/version structure, never verified effective-date claims.
    assessment = "INHERITED_UNVERIFIED" if row.get("temporal_status") == "INHERITED_DOCUMENT" else "UNKNOWN"
    if kind == "document":
        assessment = "DOCUMENT_SOURCE_UNREVIEWED"
    return {"source": {k: row[k] for k in TEMPORAL_KEYS if k in row}, "assessment": assessment,
            "verified_applicability": False}


def evidence_ref(record: Record) -> dict:
    ref = record.ref()
    for key in ("document_id", "case_id", "provision_id", "provision_identity_id", "provision_version_id",
                "source_document_version_id", "method", "confidence", "evidence_status", "provenance_status"):
        if key in record.row:
            ref[key] = record.row[key]
    if "evidence_span" in record.row:
        ref["span"] = record.row["evidence_span"]
    elif "coordinate_space" in record.row:
        ref["span"] = source_span(record.row)
    if "evidence_text" in record.row:
        ref["evidence_text"] = record.row["evidence_text"]
        ref["evidence_text_sha256"] = digest_bytes(record.row["evidence_text"].encode("utf-8"))
    return ref


def provenance(records: list[Record]) -> list[dict]:
    refs = {canonical(evidence_ref(r)): evidence_ref(r) for r in records}
    return [refs[k] for k in sorted(refs)]


def properties(record: Record, supports: list[Record], literal: str = "NOT_APPLICABLE") -> dict:
    return {**record.ref(), "source_properties": record.row, "provenance": provenance([record] + supports),
            "verification": {"structural": "VERIFIED", "literal_evidence": literal,
                             "semantic": "NOT_APPLICABLE", "temporal": "UNVERIFIED"}}


def make_node(kind: str, record: Record, supports: list[Record], literal: str = "NOT_APPLICABLE", **extra) -> dict:
    props = properties(record, supports, literal)
    props["temporal"] = temporal(record.row, kind)
    props.update(extra)
    return {"id": qid(kind, record.source_record_id), "type": NODE_TYPES[kind], "layer": "rule", "properties": props}


def make_edge(edge_type: str, source: str, target: str, record: Record, supports: list[Record], *, semantic=False) -> dict:
    evidence_key = [record.source_path, record.source_record_id, record.row.get("evidence_span", source_span(record.row))]
    props = properties(record, supports, "VERIFIED" if edge_type in RELATION_ENDPOINTS or edge_type == "CONTAINS" else "NOT_APPLICABLE")
    if not semantic:
        # Text is retained on the source Provision node. FK edges retain material FK/span
        # fields plus immutable record/file hashes rather than duplicating full text.
        material = set(SPAN_KEYS + TEMPORAL_KEYS + ("parent_id", "level", "provision_id", "provision_identity_id",
                                                   "provision_version_id", "source_document_version_id", "canonical_path"))
        props["source_properties"] = {k: v for k, v in record.row.items() if k in material}
    props["derivation"] = "reviewed_source_relation" if semantic else "validated_source_foreign_key"
    props["verification"]["semantic"] = "VERIFIED" if semantic else "NOT_APPLICABLE"
    props["temporal"] = {"assessment": "UNKNOWN", "verified_applicability": False}
    return {"id": "edge:" + digest([SCHEMA, "rule", edge_type, source, target, evidence_key]),
            "source_id": source, "target_id": target, "type": edge_type, "layer": "rule", "properties": props}


def disposition(record: Record, outcome: str, reasons: list[str], *, count=1, **extra) -> dict:
    if not reasons:
        raise BuildError("Missing exclusion reason")
    return {"id": outcome.lower() + ":" + digest([SCHEMA, record.source_path, record.source_record_id, record.source_record_sha256, outcome]),
            "table": record.table, **record.ref(), "outcome": outcome, "record_count": count,
            "primary_reason": reasons[0], "reason_codes": list(dict.fromkeys(reasons)), **extra}


def load_reviews(path: Path | None) -> tuple[dict, dict | None]:
    if path is None:
        return {}, None
    source = load_source(path.parent, "reviews", path.name, "review_id")
    by_id = unique_index(source)
    reviews = {}
    for record in by_id.values():
        row = record.row
        key = (row.get("source_path"), row.get("source_record_id"))
        if not all(isinstance(k, str) and k for k in key) or key in reviews:
            raise BuildError("Invalid or duplicate source record in explicit review catalog")
        reviews[key] = record
    return reviews, source.manifest()


def review_dependencies(record: Record, source: tuple | None, target: tuple | None, indexes: dict) -> list[dict]:
    """Snapshot endpoint content and context, not just their reusable source IDs.

    File hashes deliberately invalidate a review even for unrelated edits in the
    same source file. This conservative scope avoids silently reusing a decision
    after extraction/context changes under otherwise stable endpoint IDs.
    """
    dependencies = {}

    def add(item: Record | None):
        if item is not None:
            dependencies[(item.source_path, item.source_record_id)] = item.ref()

    def add_document(document_id):
        add(indexes["documents"].get(document_id))
        add(indexes["texts"].get(document_id))

    for endpoint in (source, target):
        if endpoint is None:
            continue
        kind, item = endpoint
        add(item)
        if kind == "document":
            add_document(item.source_record_id)
        elif kind in {"provision", "case"}:
            add_document(item.row.get("document_id"))
            if kind == "provision":
                current, visited = item, set()
                while current is not None and current.source_record_id not in visited:
                    visited.add(current.source_record_id)
                    add(current)
                    row = current.row
                    add(indexes["segments"].get(row.get("segment_id")))
                    add(indexes["spans"].get(current.source_record_id))
                    add(indexes["identities"].get(row.get("provision_identity_id")))
                    add(indexes["versions"].get(row.get("provision_version_id")))
                    current = indexes["provisions"].get(row.get("parent_id"))
        elif kind == "identity":
            # Identity itself is an endpoint; its published versions/provisions
            # and their source contexts define the reviewed identity's scope.
            for provision in indexes["provisions"].values():
                if provision.row.get("provision_identity_id") == item.source_record_id:
                    add(provision)
                    add(indexes["versions"].get(provision.row.get("provision_version_id")))
                    add(indexes["spans"].get(provision.source_record_id))
                    add(indexes["segments"].get(provision.row.get("segment_id")))
                    add_document(provision.row.get("document_id"))
    span = record.row.get("evidence_span")
    if isinstance(span, dict):
        add(indexes["segments"].get(span.get("segment_id")))
        if span.get("document_id"):
            add_document(span["document_id"])
    return sorted(dependencies.values(), key=canonical)


def review_check(record: Record, edge_type: str, source: str, target: str, reviews: dict,
                 dependencies: list[dict]) -> tuple[str, Record | None]:
    review = reviews.get((record.source_path, record.source_record_id))
    if review is None:
        return "SEMANTIC_REVIEW_REQUIRED", None
    row = review.row
    expectations = {"source_record_sha256": record.source_record_sha256, "source_input_sha256": record.source_sha256,
                    "source_id": source, "target_id": target, "relation_type": edge_type,
                    "decision": "APPROVED", "evidence_verified": True, "semantic_verified": True,
                    "target_resolution_verified": True}
    if any(type(row.get(k)) is not type(v) or row.get(k) != v for k, v in expectations.items()):
        return "SEMANTIC_REVIEW_INVALID_OR_STALE", review
    if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("reviewer", "reviewed_at")):
        return "SEMANTIC_REVIEW_MISSING_ATTRIBUTION", review
    snapshots = row.get("dependency_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        return "SEMANTIC_REVIEW_DEPENDENCIES_REQUIRED", review
    if (not all(isinstance(item, dict) for item in snapshots) or
            canonical(sorted(snapshots, key=canonical)) != canonical(dependencies)):
        return "SEMANTIC_REVIEW_DEPENDENCIES_STALE", review
    if edge_type in {"AMENDS", "REPEALS", "REPLACES"} and not all(row.get(k) is True for k in ("operation_verified", "scope_verified", "direction_verified", "temporal_verified")):
        return "TEMPORAL_OPERATION_REVIEW_REQUIRED", review
    return "VERIFIED", review


def validate_graph(nodes: list[dict], edges: list[dict]) -> dict:
    index = {}
    for node in nodes:
        if set(node) != {"id", "type", "layer", "properties"} or node["layer"] != "rule" or node["type"] not in NODE_TYPES.values():
            raise BuildError("Invalid node envelope/type/layer")
        if node["id"] in index:
            raise BuildError("Duplicate published node ID: " + node["id"])
        index[node["id"]] = node
        props = node["properties"]
        if not isinstance(props, dict) or not props.get("provenance") or not all(k in props for k in ("source_record_id", "source_path", "source_sha256", "source_record_sha256", "verification")):
            raise BuildError("Missing node provenance")
        if props.get("temporal", {}).get("verified_applicability") is not False:
            raise BuildError("M1 must not assert verified applicability")
        kind = next(k for k, value in NODE_TYPES.items() if value == node["type"])
        if node["id"] != qid(kind, props["source_record_id"]):
            raise BuildError("Node namespace does not match its type/source ID")
    graph_references = {"document_node_id": {"Document"}, "parent_node_id": {"Document", "Provision"},
                        "identity_node_id": {"ProvisionIdentity"}, "version_node_id": {"ProvisionVersion"}}
    for node in nodes:
        required_refs = {"Provision": {"document_node_id", "parent_node_id", "identity_node_id", "version_node_id"},
                         "ProvisionVersion": {"identity_node_id", "document_node_id"}}.get(node["type"], set())
        if not required_refs.issubset(node["properties"]):
            raise BuildError("Missing required graph property reference")
        for key, allowed in graph_references.items():
            if key in node["properties"]:
                target = index.get(node["properties"][key])
                if target is None or target["type"] not in allowed:
                    raise BuildError("Missing/wrong typed property reference: " + node["id"] + ":" + key)
        if node["type"] == "Provision":
            row = node["properties"]["source_properties"]
            spaces = {row.get("coordinate_space")}
            if any(k in row for k in ("segment_char_start", "segment_char_end")):
                spaces.add("SEGMENT_TEXT")
            if any(k in row for k in ("document_char_start", "document_char_end")):
                spaces.add("DOCUMENT_TEXT")
            if any(node["properties"].get("coordinate_verification", {}).get(space) != "VERIFIED" for space in spaces):
                raise BuildError("Unverified supplied coordinate space on published provision")
            version = index[node["properties"]["version_node_id"]]
            if any(version["properties"][key] != node["properties"][key] for key in ("identity_node_id", "document_node_id")):
                raise BuildError("Provision/version property joins disagree")
    edge_ids, parent_counts = set(), Counter()
    children, indegree = defaultdict(list), Counter({node["id"]: 0 for node in nodes})
    for edge in edges:
        if set(edge) != {"id", "source_id", "target_id", "type", "layer", "properties"} or edge["layer"] != "rule":
            raise BuildError("Invalid edge envelope/layer")
        if edge["id"] in edge_ids:
            raise BuildError("Duplicate published edge ID")
        edge_ids.add(edge["id"])
        s, t = index.get(edge["source_id"]), index.get(edge["target_id"])
        if s is None or t is None:
            raise BuildError("Dangling edge")
        if s["id"] == t["id"]:
            raise BuildError("Self-loop edge")
        pair, kind = (s["type"], t["type"]), edge["type"]
        if kind == "CONTAINS":
            sl = s["properties"]["source_properties"].get("level")
            tl = t["properties"]["source_properties"].get("level")
            if not ((pair == ("Document", "Provision") and tl == "ARTICLE") or
                    (pair == ("Provision", "Provision") and (sl, tl) in {("ARTICLE", "CLAUSE"), ("CLAUSE", "POINT")})):
                raise BuildError("Invalid CONTAINS endpoint levels")
            if t["properties"]["parent_node_id"] != s["id"]:
                raise BuildError("CONTAINS disagrees with parent property")
            expected_doc = s["id"] if s["type"] == "Document" else s["properties"]["document_node_id"]
            if t["properties"]["document_node_id"] != expected_doc:
                raise BuildError("Cross-document CONTAINS")
            parent_counts[t["id"]] += 1
            children[s["id"]].append(t["id"])
            indegree[t["id"]] += 1
        elif kind in {"HAS_IDENTITY", "HAS_VERSION"}:
            expected = ("Provision", "ProvisionIdentity") if kind == "HAS_IDENTITY" else ("ProvisionIdentity", "ProvisionVersion")
            if pair != expected:
                raise BuildError("Invalid identity/version endpoint types")
            if kind == "HAS_IDENTITY" and s["properties"]["identity_node_id"] != t["id"]:
                raise BuildError("HAS_IDENTITY disagrees with property reference")
            if kind == "HAS_VERSION" and t["properties"]["identity_node_id"] != s["id"]:
                raise BuildError("HAS_VERSION disagrees with property reference")
        elif kind in RELATION_ENDPOINTS:
            if pair not in RELATION_ENDPOINTS[kind] or edge["properties"]["verification"].get("semantic") != "VERIFIED":
                raise BuildError("Invalid/unreviewed legal relation")
        else:
            raise BuildError("Unknown published edge type")
        if not edge["properties"].get("provenance"):
            raise BuildError("Missing edge provenance")
    if any(parent_counts[n["id"]] != 1 for n in nodes if n["type"] == "Provision"):
        raise BuildError("Every published provision must have exactly one published parent")
    ready = [key for key, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise BuildError("Published hierarchy cycle")
    return {"duplicate_node_ids": 0, "duplicate_edge_ids": 0, "dangling_edges": 0,
            "missing_property_node_references": 0, "invalid_endpoint_types": 0, "hierarchy_cycles": 0,
            "false_verified_applicability_claims": 0, "unverified_supplied_coordinate_spaces": 0}


def build(data: Path, *, review_catalog: Path | None = None) -> dict:
    sources = {table: load_source(data, table, relative, key) for table, (relative, key) in TABLES.items()}
    indexes = {table: unique_index(source) for table, source in sources.items() if table != "quarantine"}
    docs, provisions, identities, versions = (indexes[t] for t in ("documents", "provisions", "identities", "versions"))
    reviews, review_manifest = load_reviews(review_catalog)
    raw_registry = {}
    for table, kind in (("documents", "document"), ("provisions", "provision"), ("identities", "identity"), ("cases", "case")):
        for key, record in indexes[table].items():
            if key in raw_registry:
                raise BuildError("RAW_ENDPOINT_NAMESPACE_COLLISION: " + key)
            raw_registry[key] = (kind, record)
    # Version/provision raw-ID equality is intentional only for the matching version FK.
    for key in versions:
        if key in raw_registry and not (raw_registry[key][0] == "provision" and provisions[key].row.get("provision_version_id") == key):
            raise BuildError("VERSION_NAMESPACE_COLLISION: " + key)
    version_users = defaultdict(list)
    for key, record in provisions.items():
        version_users[record.row.get("provision_version_id")].append(key)
    if any(len(users) > 1 for version, users in version_users.items() if version is not None):
        raise BuildError("VERSION_REUSED_BY_MULTIPLE_PROVISIONS")
    nodes, edges, rejects, candidates, review_queue = [], [], [], [], []
    counts = defaultdict(Counter)

    def exclude(record, reasons, *, outcome="EXCLUDED", **extra):
        target = candidates if outcome == "CANDIDATE" else rejects
        target.append(disposition(record, outcome, reasons, **extra))
        counts[record.table][outcome] += extra.get("count", 1)

    allowed_docs = set()
    for key, record in docs.items():
        reasons = document_reasons(record.row)
        if reasons:
            exclude(record, reasons)
        else:
            allowed_docs.add(key)
    quarantine_ids = {r.source_record_id for r in sources["quarantine"].records}
    quarantine_groups = Counter((r.source_record_id, r.source_record_sha256) for r in sources["quarantine"].records)
    quarantine_records = {(r.source_record_id, r.source_record_sha256): r for r in sources["quarantine"].records}
    for key, amount in sorted(quarantine_groups.items()):
        exclude(quarantine_records[key], ["QUARANTINED_SOURCE_RECORD"], count=amount)
    cycles = cycle_members(provisions)
    reasons_by_id, blockers, supports_by_id, coordinate_verification = {}, {}, {}, {}
    policy_screen, literal_screen = set(), Counter()
    for key, record in provisions.items():
        row, reasons, supports = record.row, [], []
        doc = docs.get(row.get("document_id"))
        if doc is None:
            reasons.append("SOURCE_DOCUMENT_MISSING")
        elif doc.source_record_id not in allowed_docs:
            reasons.append("DOCUMENT_NOT_PUBLISHED")
        elif doc.row["graph_import_policy"].get("allow_provision_hierarchy") is not True:
            reasons.append("HIERARCHY_POLICY_DENIED")
        else:
            policy_screen.add(key)
        if key in quarantine_ids:
            reasons.append("QUARANTINED_PROVISION_ID")
        if row.get("level") not in {"ARTICLE", "CLAUSE", "POINT"}:
            reasons.append("INVALID_PROVISION_LEVEL")
        coordinate_reasons, evidence_support, spaces = provision_coordinate_checks(row, indexes)
        status = spaces.get(row.get("coordinate_space"), "EVIDENCE_UNSUPPORTED_COORDINATE_SPACE")
        coordinate_verification[key] = spaces
        supports.extend(evidence_support)
        if key in policy_screen:
            literal_screen[status] += 1
        reasons.extend(coordinate_reasons)
        span = indexes["spans"].get(key)
        if span is None:
            reasons.append("PROVENANCE_SPAN_MISSING")
        elif any(span.row.get(field) != row.get(field) for field in SPAN_KEYS):
            reasons.append("PROVENANCE_SPAN_DISAGREEMENT")
        else:
            supports.append(span)
        if row.get("provenance_status") != "RESOLVED":
            reasons.append("PROVENANCE_NOT_RESOLVED")
        identity = identities.get(row.get("provision_identity_id"))
        version = versions.get(row.get("provision_version_id"))
        if identity is None:
            reasons.append("IDENTITY_MISSING")
        elif doc and identity.row.get("instrument_id") != doc.row.get("instrument_id"):
            reasons.append("IDENTITY_INSTRUMENT_MISMATCH")
        if version is None:
            reasons.append("VERSION_MISSING")
        elif (version.row.get("provision_identity_id") != row.get("provision_identity_id") or
              version.row.get("source_document_version_id") != row.get("document_id") or
              row.get("source_document_version_id") != row.get("document_id")):
            reasons.append("VERSION_IDENTITY_DOCUMENT_MISMATCH")
        parent = row.get("parent_id")
        if parent == key:
            reasons.append("PARENT_SELF_LOOP")
        if key in cycles:
            reasons.append("PARENT_CYCLE")
        if parent in docs:
            if parent != row.get("document_id") or row.get("level") != "ARTICLE":
                reasons.append("PARENT_DOCUMENT_OR_LEVEL_MISMATCH")
        elif parent in provisions:
            parent_row = provisions[parent].row
            if parent_row.get("document_id") != row.get("document_id"):
                reasons.append("PARENT_WRONG_DOCUMENT")
            if (parent_row.get("level"), row.get("level")) not in {("ARTICLE", "CLAUSE"), ("CLAUSE", "POINT")}:
                reasons.append("PARENT_WRONG_LEVEL")
        else:
            reasons.append("PARENT_MISSING_OR_WRONG_TYPE")
        reasons_by_id[key] = list(dict.fromkeys(reasons))
        supports_by_id[key] = supports
        if key in policy_screen and status == "EVIDENCE_TEXT_MISMATCH":
            review_queue.append(disposition(record, "PENDING_REVIEW", [status], source_properties=row,
                                            span_record=span.ref() if span else {},
                                            instruction="Do not edit source; evidence/review required before publication."))
    # Resolve ancestry without relying on input order or Python recursion depth.
    selected, resolved = set(), set()
    for start in sorted(provisions):
        trail, current = [], start
        while current not in resolved:
            if reasons_by_id[current]:
                resolved.add(current)
                blockers[current] = current
                break
            trail.append(current)
            parent = provisions[current].row["parent_id"]
            if parent in allowed_docs:
                selected.add(current)
                resolved.add(current)
                break
            current = parent
        for key in reversed(trail):
            if key in resolved:
                continue
            parent = provisions[key].row["parent_id"]
            if parent in selected:
                selected.add(key)
            else:
                reasons_by_id[key].append("PARENT_NOT_PUBLISHED")
                blockers[key] = blockers.get(parent, parent)
            resolved.add(key)
    for key, record in provisions.items():
        if key not in selected:
            extra = {"blocking_source_id": blockers[key]} if key in blockers else {}
            exclude(record, reasons_by_id[key], **extra)
    used_identities = {provisions[key].row["provision_identity_id"] for key in selected}
    used_versions = {provisions[key].row["provision_version_id"] for key in selected}
    for table, used in (("identities", used_identities), ("versions", used_versions)):
        for key, record in indexes[table].items():
            if key not in used:
                exclude(record, ["NOT_IN_TRUSTED_PROVISION_CLOSURE"])
    headings_by_doc = defaultdict(list)
    for record in sources["headings"].records:
        headings_by_doc[record.row.get("document_id")].append(record)
    for key in sorted(allowed_docs):
        record = docs[key]
        urls = {k: {"original": record.row[k], "normalized": record.row[k].strip(), "normalization": "strip_only",
                    "access_status": "NOT_FETCHED_M1"}
                for k in ("source_url", "canonical_url", "view_url", "official_url", "download_url") if isinstance(record.row.get(k), str)}
        headings = sorted(headings_by_doc[key], key=lambda h: (h.source_record_id, h.source_record_sha256))
        nodes.append(make_node("document", record, headings, normalized_urls=urls,
                               layout_headings=[{"source": h.ref(), "source_properties": h.row, "verification": "UNREVIEWED_LAYOUT"} for h in headings]))
    for key in sorted(selected):
        record, row = provisions[key], provisions[key].row
        identity, version, doc = identities[row["provision_identity_id"]], versions[row["provision_version_id"]], docs[row["document_id"]]
        parent_kind = "document" if row["parent_id"] in docs else "provision"
        parent_id = qid(parent_kind, row["parent_id"])
        nodes.append(make_node("provision", record, supports_by_id[key] + [doc, identity, version], "VERIFIED",
                               document_node_id=qid("document", row["document_id"]), parent_node_id=parent_id,
                               identity_node_id=qid("identity", row["provision_identity_id"]), version_node_id=qid("version", row["provision_version_id"]),
                               coordinate_verification=coordinate_verification[key]))
        edges.append(make_edge("CONTAINS", parent_id, qid("provision", key), record, supports_by_id[key]))
        edges.append(make_edge("HAS_IDENTITY", qid("provision", key), qid("identity", row["provision_identity_id"]), record, [identity]))
        edges.append(make_edge("HAS_VERSION", qid("identity", row["provision_identity_id"]), qid("version", row["provision_version_id"]), version, [identity, record]))
    for key in sorted(used_identities):
        nodes.append(make_node("identity", identities[key], []))
    for key in sorted(used_versions):
        record = versions[key]
        nodes.append(make_node("version", record, [identities[record.row["provision_identity_id"]]],
                               identity_node_id=qid("identity", record.row["provision_identity_id"]),
                               document_node_id=qid("document", record.row["source_document_version_id"])))
    published = {n["id"]: n for n in nodes}
    relation_published = Counter()
    for table in ("relations", "citations", "changes"):
        for record in sources[table].records:
            row, reasons, support = record.row, [], []
            edge_type = "CITES" if table == "citations" else {"AMEND": "AMENDS", "REPEAL": "REPEALS", "REPLACE": "REPLACES"}.get(row.get("operation")) if table == "changes" else row.get("type")
            raw_source = row.get("source_provision_id") if table == "changes" else row.get("source_id")
            raw_target = row.get("target_provision_identity_id") if table == "changes" else row.get("target_id")
            source, target = raw_registry.get(raw_source), raw_registry.get(raw_target)
            outcome = "CANDIDATE"
            if edge_type not in RELATION_ENDPOINTS:
                reasons.append("UNKNOWN_RELATION_TYPE")
                outcome = "REJECTED"
            if source is None or (raw_target is not None and target is None):
                reasons.append("MISSING_ENDPOINT")
                outcome = "REJECTED"
            elif raw_target is None or row.get("status", row.get("resolution_status", "RESOLVED")) != "RESOLVED":
                reasons.append("UNRESOLVED_TARGET")
            elif source[0] == "case" or target[0] == "case":
                reasons.append("FACT_ENDPOINT_OUT_OF_SCOPE_M1")
            else:
                pair = (NODE_TYPES[source[0]], NODE_TYPES[target[0]])
                if edge_type in RELATION_ENDPOINTS and pair not in RELATION_ENDPOINTS[edge_type]:
                    reasons.append("ENDPOINT_TYPE_NOT_ALLOWED")
                    outcome = "REJECTED"
                if qid(source[0], raw_source) not in published or qid(target[0], raw_target) not in published:
                    reasons.append("ENDPOINT_NOT_PUBLISHED")
                    outcome = "REJECTED"
                if raw_source == raw_target:
                    reasons.append("RELATION_SELF_LOOP")
                    outcome = "REJECTED"
            owner = None
            if source:
                owner = source[1].row.get("document_id") if source[0] != "document" else raw_source
            source_provision = source[1].row if source and source[0] == "provision" else None
            literal, evidence_support = evidence_check(row, indexes, owner, source_provision)
            support.extend(evidence_support)
            if literal != "VERIFIED":
                reasons.append(literal)
            if row.get("evidence_status") != "RESOLVED":
                reasons.append("SOURCE_EVIDENCE_NOT_RESOLVED")
            if table in {"citations", "changes"} and (type(row.get("candidate_count")) is not int or row.get("candidate_count") != 1):
                reasons.append("TARGET_NOT_UNIQUELY_RESOLVED")
            dependencies = review_dependencies(record, source, target, indexes)
            review_status, review = review_check(record, edge_type, raw_source, raw_target, reviews, dependencies)
            if review_status != "VERIFIED":
                reasons.append(review_status)
            elif review:
                support.append(review)
            if reasons:
                exclude(record, reasons, outcome=outcome, source_id=raw_source, target_id=raw_target,
                        relation_type=edge_type, literal_evidence=literal, source_properties=row)
            else:
                edge = make_edge(edge_type, qid(source[0], raw_source), qid(target[0], raw_target), record, support, semantic=True)
                edge["properties"]["verification"]["review_record_id"] = review.source_record_id
                edge["properties"]["review_dependency_snapshots"] = dependencies
                edges.append(edge)
                relation_published[table] += 1
    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: e["id"])
    rejects.sort(key=lambda r: r["id"])
    candidates.sort(key=lambda r: r["id"])
    review_queue.sort(key=lambda r: r["id"])
    checks = validate_graph(nodes, edges)
    primary = defaultdict(Counter)
    overlapping = defaultdict(Counter)
    for record in rejects + candidates:
        primary[record["table"]][record["primary_reason"]] += record["record_count"]
        for reason in record["reason_codes"]:
            overlapping[record["table"]][reason] += record["record_count"]
    accounting = {}
    for table in ("documents", "provisions", "identities", "versions", "quarantine", "relations", "citations", "changes"):
        published_count = {"documents": len(allowed_docs), "provisions": len(selected), "identities": len(used_identities), "versions": len(used_versions)}.get(table, relation_published[table])
        excluded_count = sum(counts[table].values())
        if published_count + excluded_count != len(sources[table].records):
            raise BuildError("Record accounting mismatch: " + table)
        accounting[table] = {"input_records": len(sources[table].records), "published_records": published_count,
                             "dispositions": dict(sorted(counts[table].items())), "primary_reasons": dict(sorted(primary[table].items())),
                             "overlapping_reason_labels": dict(sorted(overlapping[table].items()))}
    quality = {"schema_version": SCHEMA, "validation_verdict": "PASS", "scope": "M1_rule_graph_only_not_independent_review",
               "checks": checks, "accounting": accounting,
               "policy_screen": {"documents": len(allowed_docs), "hierarchy_documents": sum(docs[k].row["graph_import_policy"].get("allow_provision_hierarchy") is True for k in allowed_docs),
                                 "provisions": len(policy_screen), "literal_evidence": dict(sorted(literal_screen.items()))},
               "provision_review_queue": {"records": len(review_queue), "reason": "eligible_literal_mismatch_requires_review"},
               "closure": {"directly_blocked": sum(bool(v) and v[0] != "PARENT_NOT_PUBLISHED" for v in reasons_by_id.values()),
                           "parent_closure_excluded": sum(v == ["PARENT_NOT_PUBLISHED"] for v in reasons_by_id.values()),
                           "published_provisions": len(selected)},
               "quarantine": {"records": len(sources["quarantine"].records), "distinct_ids": len(quarantine_ids),
                              "duplicate_extra_records": len(sources["quarantine"].records) - len(quarantine_ids)},
               "temporal": {"verified_applicability_claims": 0, "assessment_counts": dict(sorted(Counter(n["properties"]["temporal"]["assessment"] for n in nodes).items()))},
               "legal_relation_review": {"published": sum(relation_published.values()), "explicit_review_catalog_supplied": review_catalog is not None},
               "url_audit": {"network_calls": 0, "normalization": "strip_only_preserve_original", "verification": "NOT_FETCHED_M1"},
               "notes": ["No ontology or fact graph is built in M1.", "Source temporal/status/URL fields are preserved as source observations, not new verified claims.",
                         "Structural PASS is not an independent reviewer verdict; see milestone review documentation."]}
    return {"nodes": nodes, "edges": edges, "rejects": rejects, "candidates": candidates, "provision_review_queue": review_queue,
            "quality_report": quality, "inputs": sorted((s.manifest() for s in sources.values()), key=lambda s: s["path"]),
            "review_catalog": review_manifest}


def export_graph(result: dict, output: Path, *, config_raw: bytes, code_hashes: dict) -> dict:
    artifacts = {}
    for name in ("nodes", "edges", "rejects", "candidates", "provision_review_queue"):
        artifacts[name + ".jsonl"] = b"".join((canonical(row) + "\n").encode("utf-8") for row in result[name])
    artifacts["quality_report.json"] = (canonical(result["quality_report"]) + "\n").encode("utf-8")
    dependencies = {"inputs": result["inputs"], "review_catalog": result["review_catalog"], "config_sha256": digest_bytes(config_raw),
                    "source_code_sha256": code_hashes, "schema_version": SCHEMA}
    manifest = {**dependencies, "build_id": "build:" + digest(dependencies), "milestone": "M1", "layers": ["rule"],
                "validation_verdict": "PASS", "review_status": "SEE_INDEPENDENT_MILESTONE_REVIEW",
                "counts": {"nodes": len(result["nodes"]), "edges": len(result["edges"]),
                           "node_types": dict(sorted(Counter(n["type"] for n in result["nodes"]).items())),
                           "edge_types": dict(sorted(Counter(e["type"] for e in result["edges"]).items())),
                           "nodes_by_layer": {"rule": len(result["nodes"])}, "edges_by_layer": {"rule": len(result["edges"])},
                           "candidate_records": sum(r["record_count"] for r in result["candidates"]),
                           "rejected_or_excluded_records": sum(r["record_count"] for r in result["rejects"]),
                           "review_queue_records": len(result["provision_review_queue"])},
                "record_accounting": result["quality_report"]["accounting"],
                "artifacts": {name: {"sha256": digest_bytes(raw), "bytes": len(raw)} for name, raw in sorted(artifacts.items())},
                "determinism": {"encoding": "UTF-8", "newline": "LF", "record_order": "qualified_id", "runtime_timestamps": False},
                "input_immutability": "file_hashes_rechecked_before_export"}
    artifacts["manifest.json"] = (canonical(manifest) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    # Binary writes prevent Windows newline translation. Manifest is the final commit marker.
    for name, raw in artifacts.items():
        temporary = output / (name + ".tmp")
        temporary.write_bytes(raw)
        temporary.replace(output / name)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/rule_graph"))
    parser.add_argument("--config", type=Path, default=Path("configs/rule_graph_v1.json"))
    parser.add_argument("--review-catalog", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        data = discover_data(root).resolve()
        output = args.output.resolve()
        if output == data or data in output.parents:
            raise BuildError("Output must be outside immutable input directory")
        config_raw = args.config.read_bytes()
        if canonical(parse_json(config_raw.decode("utf-8-sig"))) != canonical(CONFIG):
            raise BuildError("Unsupported config; mandatory trust gates cannot be disabled")
        result = build(data, review_catalog=args.review_catalog)
        for source in result["inputs"]:
            if digest_bytes((data / source["path"]).read_bytes()) != source["sha256"]:
                raise BuildError("Input changed during build: " + source["path"])
        repo = Path(__file__).resolve().parents[2]
        code_hashes = {str(p.relative_to(repo)).replace("\\", "/"): digest_bytes(p.read_bytes()) for p in
                       (Path(__file__).resolve(), repo / "scripts/build_rule_graph.py")}
        manifest = export_graph(result, output, config_raw=config_raw, code_hashes=code_hashes)
        print(f"Rule Graph PASS: nodes={manifest['counts']['nodes']}, edges={manifest['counts']['edges']}, build_id={manifest['build_id']}")
        print(f"Review queue={manifest['counts']['review_queue_records']}; legal relations published={result['quality_report']['legal_relation_review']['published']}; URLs not fetched.")
        return 0
    except (BuildError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Rule Graph FAIL (no validated replacement): {exc}", file=sys.stderr)
        return 1
