"""Verified union only: never infer a link from a keyword, title or similarity."""
import argparse
from collections import Counter
from pathlib import Path
import sys

from .rule_graph import BuildError, canonical, digest, digest_bytes, parse_json, validate_graph
from .ontology_graph import approval_check, check_taxonomy

SCHEMA = "integrated-graph-v1"
BUNDLES = {"rule": ("rule_graph", "rule-graph-v1"), "ontology": ("ontology_graph", "ontology-graph-v1"), "fact": ("fact_graph", "fact-graph-v1")}


def safe_path(base, relative):
    value = Path(relative)
    resolved = (base / value).resolve()
    if value.is_absolute() or not resolved.is_relative_to(base.resolve()):
        raise BuildError("Unsafe dependency path")
    return resolved


def read_rows(raw):
    result = []
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            row = parse_json(line)
            if not isinstance(row, dict):
                raise BuildError("Expected graph object")
            result.append(row)
    return result


def load_bundle(root, tag, pinned, hash_cache):
    folder, schema = BUNDLES[tag]
    base = root / "outputs" / folder
    raw = (base / "manifest.json").read_bytes()
    if digest_bytes(raw) != pinned:
        raise BuildError("Unapproved/stale upstream manifest: " + tag)
    manifest = parse_json(raw.decode("utf-8"))
    if manifest.get("schema_version") != schema:
        raise BuildError("Wrong upstream schema: " + tag)
    if tag == "rule" and manifest.get("validation_verdict") != "PASS":
        raise BuildError("Unaccepted Rule validation status")
    if tag == "fact" and manifest.get("validation_verdict") != "PASS_WITH_SOURCE_LIMITATIONS":
        raise BuildError("Unaccepted Fact validation status")
    artifacts = {}
    for name, entry in manifest["artifacts"].items():
        path = safe_path(base, name)
        if Path(name).name != name:
            raise BuildError("Upstream artifact must be a filename")
        content = path.read_bytes()
        if digest_bytes(content) != entry["sha256"] or len(content) != entry["bytes"]:
            raise BuildError("Upstream artifact hash/size mismatch: " + tag + "/" + name)
        artifacts[name] = content
    for relative, sha in manifest["source_code_sha256"].items():
        path = safe_path(root, relative)
        if digest_bytes(path.read_bytes()) != sha:
            raise BuildError("Stale upstream source code: " + relative)
    for entry in manifest["inputs"]:
        path = safe_path(root / "Data", entry["path"])
        if path not in hash_cache:
            hash_cache[path] = digest_bytes(path.read_bytes())
        if hash_cache[path] != entry["sha256"]:
            raise BuildError("Stale upstream Data input: " + entry["path"])
    nodes, edges = read_rows(artifacts["nodes.jsonl"]), read_rows(artifacts["edges.jsonl"])
    if manifest["counts"]["nodes"] != len(nodes) or manifest["counts"]["edges"] != len(edges):
        raise BuildError("Upstream manifest record counts mismatch")
    return {"manifest": manifest, "manifest_sha256": digest_bytes(raw), "artifacts": artifacts, "nodes": nodes, "edges": edges}


def validate_union(nodes, edges, approved_ontology_edge_ids):
    index = {}
    allowed_nodes = {"Document": "rule", "Provision": "rule", "ProvisionIdentity": "rule", "ProvisionVersion": "rule",
                     "LegalConcept": "ontology", "LegalIssue": "ontology", "Case": "fact"}
    for node in nodes:
        if set(node) != {"id", "type", "layer", "properties"} or allowed_nodes.get(node["type"]) != node["layer"]:
            raise BuildError("Invalid integrated node envelope/type/layer")
        if node["id"] in index:
            raise BuildError("Duplicate integrated node ID")
        if not node["id"].startswith(node["layer"] + ":") or not node["properties"].get("provenance"):
            raise BuildError("Invalid namespace/provenance")
        if node["properties"].get("temporal", {}).get("verified_applicability", False) is not False:
            raise BuildError("False verified temporal applicability")
        if node["type"] == "LegalConcept" and node["properties"]["verification"].get("semantic") != "VERIFIED":
            raise BuildError("Unapproved ontology concept")
        index[node["id"]] = node
    references = {"document_node_id": {"Document"}, "parent_node_id": {"Document", "Provision"},
                  "identity_node_id": {"ProvisionIdentity"}, "version_node_id": {"ProvisionVersion"}}
    nested_references = {**references, "provision_node_id": {"Provision"}, "definition_provision_id": {"Provision"},
                         "classification_provision_id": {"Provision"}, "rule_document_node_id": {"Document"}}
    def check_references(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in nested_references:
                    target = index.get(child) if isinstance(child, str) else None
                    if target is None or target["type"] not in nested_references[key]:
                        raise BuildError("Missing/wrong integrated property reference: " + key)
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)
    for node in nodes:
        check_references(node["properties"])
        for key, types in references.items():
            if key in node["properties"]:
                target = index.get(node["properties"][key])
                if target is None or target["type"] not in types:
                    raise BuildError("Missing/wrong integrated property reference")
        if node["type"] == "Case":
            if "document_node_id" not in node["properties"] or node["properties"].get("legacy_sections_imported_as_facts") is not False:
                raise BuildError("Invalid Case policy/reference")
            if any(k in node["properties"]["source_properties"] for k in ("facts", "reasoning", "decision", "features", "court", "decision_date")):
                raise BuildError("Legacy Case claims leaked")
    edge_ids, taxonomy = set(), []
    for edge in edges:
        if set(edge) != {"id", "source_id", "target_id", "type", "layer", "properties"}:
            raise BuildError("Invalid integrated edge envelope")
        if edge["id"] in edge_ids:
            raise BuildError("Duplicate integrated edge ID")
        edge_ids.add(edge["id"])
        check_references(edge["properties"])
        source, target = index.get(edge["source_id"]), index.get(edge["target_id"])
        if source is None or target is None:
            raise BuildError("Dangling integrated edge")
        if source["id"] == target["id"] or not edge["properties"].get("provenance"):
            raise BuildError("Self-loop or missing edge provenance")
        if edge["properties"].get("temporal", {}).get("verified_applicability", False) is not False:
            raise BuildError("False verified edge temporal applicability")
        if source["type"] == "Case" or target["type"] == "Case":
            raise BuildError("No reviewed Case graph link authorized in these checkpoints")
        if edge["layer"] == "rule":
            if source["layer"] != "rule" or target["layer"] != "rule":
                raise BuildError("Wrong Rule edge layer/endpoints")
        elif edge["type"] == "IS_A":
            if edge["layer"] != "ontology" or (source["type"], target["type"]) != ("LegalConcept", "LegalConcept"):
                raise BuildError("Wrong IS_A layer/endpoints")
            taxonomy.append({"relation_key": edge["id"], "source_key": source["id"], "target_key": target["id"], "type": "IS_A"})
        elif edge["type"] == "REGULATED_BY":
            if edge["layer"] != "cross" or (source["type"], target["type"]) != ("LegalConcept", "Provision"):
                raise BuildError("Wrong grounding layer/endpoints")
            if edge["properties"].get("mapping_kind") != "STATUTORY_DEFINITION":
                raise BuildError("Unapproved applicability/grounding semantics")
        else:
            raise BuildError("Unsupported integrated link type/layer")
        if edge["layer"] != "rule":
            if edge["id"] not in approved_ontology_edge_ids or edge["properties"]["verification"].get("semantic") != "VERIFIED":
                raise BuildError("Unreviewed cross-layer/ontology link")
    check_taxonomy(taxonomy, {n["id"] for n in nodes if n["type"] == "LegalConcept"})
    validate_graph([n for n in nodes if n["layer"] == "rule"], [e for e in edges if e["layer"] == "rule"])
    return {"duplicate_node_ids": 0, "duplicate_edge_ids": 0, "dangling_edges": 0, "missing_property_references": 0,
            "invalid_endpoint_types_or_layers": 0, "unreviewed_case_links": 0, "verified_applicability_claims": 0}


def traversal_examples(nodes, edges):
    index = {n["id"]: n for n in nodes}
    grounding = {e["source_id"]: e for e in edges if e["type"] == "REGULATED_BY"}
    contains = {e["target_id"]: e for e in edges if e["type"] == "CONTAINS"}
    examples = []
    for isa in [e for e in edges if e["type"] == "IS_A"]:
        ground = grounding.get(isa["target_id"])
        if not ground:
            continue
        path = [isa["source_id"], isa["target_id"], ground["target_id"]]
        steps = [{"edge_id": e["id"], "type": e["type"], "direction": "forward"} for e in (isa, ground)]
        current = ground["target_id"]
        while current in contains:
            edge = contains[current];current = edge["source_id"]
            path.append(current);steps.append({"edge_id": edge["id"], "type": "CONTAINS", "direction": "reverse"})
        examples.append({"kind": "subtype_to_definition_and_document", "node_ids": path, "steps": steps,
                         "interpretation": "Reviewed concept taxonomy/definition grounding, not case applicability."})
    cases = [n for n in nodes if n["type"] == "Case"]
    return {"graph_traversals": examples, "case_document_property_examples":
            [{"case_node_id": n["id"], "document_node_id": n["properties"]["document_node_id"], "reference_kind": "PROPERTY_REFERENCE_NOT_INFERRED_EDGE"} for n in cases[:3]],
            "case_graph_links": sum(index[e["source_id"]]["type"] == "Case" or index[e["target_id"]]["type"] == "Case" for e in edges)}


def diagnostic_union(bundles, filename):
    records, origins, duplicate_copies = {}, {}, 0
    for tag, bundle in bundles.items():
        for row in read_rows(bundle["artifacts"].get(filename, b"")):
            key = row["id"]
            if key in records:
                if canonical(records[key]) != canonical(row):
                    raise BuildError("Conflicting diagnostic copies")
                duplicate_copies += row.get("record_count", 1)
            else:
                records[key] = row
            origins.setdefault(key, []).append(tag)
    result = [{**records[key], "upstream_bundles": sorted(set(origins[key]))} for key in sorted(records)]
    return result, duplicate_copies


def build(root, config_path):
    config_raw = config_path.read_bytes();config = parse_json(config_raw.decode("utf-8"))
    if config.get("schema_version") != SCHEMA or set(config.get("upstream_manifest_sha256", {})) != set(BUNDLES):
        raise BuildError("Invalid pinned integration configuration")
    cache = {};bundles = {tag: load_bundle(root, tag, config["upstream_manifest_sha256"][tag], cache) for tag in BUNDLES}
    rule, ontology, fact = (bundles[tag] for tag in BUNDLES)
    if digest_bytes((root / "configs/rule_graph_v1.json").read_bytes()) != rule["manifest"]["config_sha256"]:
        raise BuildError("Stale Rule configuration")
    for bundle in (ontology, fact):
        if bundle["manifest"]["rule_manifest_sha256"] != rule["manifest_sha256"] or bundle["manifest"]["rule_build_id"] != rule["manifest"]["build_id"]:
            raise BuildError("Stale Rule dependency across layers")
    om = ontology["manifest"]
    if om.get("semantic_release_status") != "APPROVED":
        raise BuildError("Ontology draft cannot enter trusted union")
    catalog_path = safe_path(root, om["catalog"]["path"])
    if digest_bytes(catalog_path.read_bytes()) != om["catalog"]["sha256"]:
        raise BuildError("Stale ontology catalog")
    approval_path = safe_path(root / "ontology", om["approval"]["path"])
    approved, approval = approval_check(approval_path, root / "docs/milestone_2/REVIEW.md", om["catalog"]["sha256"], rule["manifest_sha256"],
                                      [n["id"] for n in ontology["nodes"] if n["type"] == "LegalConcept"], [e["id"] for e in ontology["edges"]])
    if not approved or approval != om["approval"]:
        raise BuildError("Ontology approval snapshot mismatch")
    nodes = sorted([n for b in bundles.values() for n in b["nodes"]], key=lambda n: n["id"])
    edges = sorted([e for b in bundles.values() for e in b["edges"]], key=lambda e: e["id"])
    checks = validate_union(nodes, edges, {e["id"] for e in ontology["edges"]})
    provenance = []
    for tag, bundle in bundles.items():
        for record in bundle["nodes"] + bundle["edges"]:
            provenance.append({"id": "provenance:" + digest(record["id"]), "graph_record_id": record["id"], "upstream_bundle": tag,
                               "upstream_manifest_sha256": bundle["manifest_sha256"], "provenance": record["properties"]["provenance"]})
    candidates, candidate_copies = diagnostic_union(bundles, "candidates.jsonl")
    rejects, reject_copies = diagnostic_union(bundles, "rejects.jsonl")
    queue_bundles = {tag: {**b, "artifacts": {"queue.jsonl": b["artifacts"].get("provision_review_queue.jsonl", b["artifacts"].get("review_queue.jsonl", b""))}} for tag, b in bundles.items()}
    queue, queue_copies = diagnostic_union(queue_bundles, "queue.jsonl")
    coverage = {"nodes_by_layer": dict(sorted(Counter(n["layer"] for n in nodes).items())), "node_types": dict(sorted(Counter(n["type"] for n in nodes).items())),
                "edges_by_layer": dict(sorted(Counter(e["layer"] for e in edges).items())), "edge_types": dict(sorted(Counter(e["type"] for e in edges).items())),
                "verified_definition_groundings": sum(e["type"] == "REGULATED_BY" for e in edges), "reviewed_case_graph_links": 0,
                "candidate_source_records": sum(r.get("record_count", 1) for r in candidates), "reject_or_excluded_source_records": sum(r.get("record_count", 1) for r in rejects),
                "review_queue_records": sum(r.get("record_count", 1) for r in queue), "duplicate_candidate_copies_removed": candidate_copies,
                "duplicate_reject_copies_removed": reject_copies, "duplicate_queue_copies_removed": queue_copies,
                "queue_is_overlay_not_additional_exclusion": True}
    quality = {"schema_version": SCHEMA, "validation_verdict": "PASS_WITH_SOURCE_LIMITATIONS", "checks": checks, "coverage": coverage,
               "limitations": ["Case nodes retain identity/source references; fact extraction pending.", "Definition groundings do not assert legal applicability.",
                               "Keyword/citation/unresolved candidates are never promoted by union.", "Temporal uncertainty and URL verification limits remain upstream source observations."]}
    return {"nodes": nodes, "edges": edges, "provenance": sorted(provenance, key=lambda p: p["id"]), "candidates": candidates, "rejects": rejects,
            "review_queue": queue, "coverage_report": coverage, "quality_report": quality, "traversal_examples": traversal_examples(nodes, edges),
            "dependencies": {"schema_version": SCHEMA, "config_sha256": digest_bytes(config_raw),
                             "upstream_manifest_sha256": {tag: b["manifest_sha256"] for tag, b in bundles.items()},
                             "upstream_build_ids": {tag: b["manifest"]["build_id"] for tag, b in bundles.items()},
                             "input_snapshot_sha256": {p.relative_to(root / "Data").as_posix(): sha for p, sha in sorted(cache.items())}}}


def export(result, output, code_hashes):
    artifacts = {}
    for key in ("nodes", "edges", "provenance", "candidates", "rejects", "review_queue"):
        artifacts[key + ".jsonl"] = b"".join((canonical(row) + "\n").encode("utf-8") for row in result[key])
    for key in ("coverage_report", "quality_report", "traversal_examples"):
        artifacts[key + ".json"] = (canonical(result[key]) + "\n").encode("utf-8")
    deps = {**result["dependencies"], "source_code_sha256": code_hashes}
    manifest = {**deps, "milestone": "M4", "build_id": "build:" + digest(deps), "validation_verdict": "PASS_WITH_SOURCE_LIMITATIONS",
                "counts": {"nodes": len(result["nodes"]), "edges": len(result["edges"]), **result["coverage_report"]},
                "artifacts": {name: {"bytes": len(raw), "sha256": digest_bytes(raw)} for name, raw in sorted(artifacts.items())},
                "determinism": {"encoding": "UTF-8", "newline": "LF", "runtime_timestamps": False}}
    artifacts["manifest.json"] = (canonical(manifest) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in artifacts.items():
        (output / (name + ".tmp")).write_bytes(raw);(output / (name + ".tmp")).replace(output / name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/integrated_graph_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/integrated_graph"))
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve();output = args.output.resolve()
        if output == root / "Data" or (root / "Data") in output.parents:
            raise BuildError("Output cannot be inside immutable Data")
        config = args.config if args.config.is_absolute() else root / args.config
        result = build(root, config)
        for tag, (folder, _) in BUNDLES.items():
            if digest_bytes((root / "outputs" / folder / "manifest.json").read_bytes()) != result["dependencies"]["upstream_manifest_sha256"][tag]:
                raise BuildError("Upstream manifest changed during integration")
        repo = Path(__file__).resolve().parents[2]
        paths = [Path(__file__).resolve(), repo / "scripts/build_integrated_graph.py", repo / "src/legal_graph/rule_graph.py", repo / "src/legal_graph/ontology_graph.py"]
        m = export(result, output, {p.relative_to(repo).as_posix(): digest_bytes(p.read_bytes()) for p in paths})
        print(f"M4 PASS_WITH_SOURCE_LIMITATIONS: nodes={m['counts']['nodes']} edges={m['counts']['edges']} cross={m['counts']['verified_definition_groundings']} case_links=0")
        return 0
    except (BuildError, ValueError, TypeError, KeyError, OSError) as exc:
        print("M4 FAIL: " + str(exc), file=sys.stderr);return 1
