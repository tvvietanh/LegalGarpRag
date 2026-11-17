"""Small curated ontology grounded only in reviewed M1 provision snapshots."""
from collections import Counter
import argparse
import hashlib
from pathlib import Path
import sys
from urllib.parse import quote

from .rule_graph import BuildError, Record, canonical, digest, digest_bytes, load_source, parse_json, unique_index

SCHEMA = "ontology-graph-v1"


def oid(kind, raw):
    if kind not in {"concept", "issue"} or not isinstance(raw, str) or not raw or raw != raw.strip():
        raise BuildError("Invalid ontology ID")
    return "ontology:" + kind + ":" + quote(raw, safe="")


def read_json(path):
    return parse_json(path.read_bytes().decode("utf-8-sig"))


def read_rule_bundle(path):
    raw = (path / "manifest.json").read_bytes()
    manifest = parse_json(raw.decode("utf-8"))
    if manifest.get("validation_verdict") != "PASS" or manifest.get("schema_version") != "rule-graph-v1":
        raise BuildError("M2 requires valid M1 Rule Graph")
    nodes_raw = None
    for name, item in manifest["artifacts"].items():
        content = (path / name).read_bytes() if Path(name).name == name else b""
        if Path(name).name != name or digest_bytes(content) != item["sha256"]:
            raise BuildError("Rule artifact hash mismatch: " + name)
        if name == "nodes.jsonl":
            nodes_raw = content
    if nodes_raw is None:
        raise BuildError("Rule nodes artifact missing")
    nodes = {}
    for line in nodes_raw.decode("utf-8").splitlines():
        node = parse_json(line)
        if node["id"] in nodes:
            raise BuildError("Duplicate Rule endpoint")
        nodes[node["id"]] = node
    return nodes, manifest, digest_bytes(raw)


def evidence_check(item, rule_nodes):
    node = rule_nodes.get(item.get("provision_node_id"))
    if node is None or node.get("type") != "Provision":
        raise BuildError("Evidence endpoint must be published Rule Provision")
    props = node["properties"]
    if item.get("rule_node_sha256") != digest(node):
        raise BuildError("Stale evidence Rule node snapshot")
    expected = {k: props[k] for k in ("source_path", "source_sha256", "source_record_id", "source_record_sha256")}
    if item.get("source_ref") != expected:
        raise BuildError("Wrong evidence source owner/hash")
    text = props["source_properties"]["text"]
    start, end = item.get("provision_char_start"), item.get("provision_char_end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise BuildError("Invalid curated evidence offsets")
    if text[start:end] != item.get("quote") or digest_bytes(item["quote"].encode("utf-8")) != item.get("quote_sha256"):
        raise BuildError("Curated evidence quote mismatch")
    if props["verification"]["literal_evidence"] != "VERIFIED" or any(v != "VERIFIED" for v in props["coordinate_verification"].values()):
        raise BuildError("Unverified Rule coordinates cannot ground concepts")
    return node


def check_taxonomy(taxonomy, keys):
    seen, parents = set(), {key: [] for key in keys}
    for item in taxonomy:
        key = item.get("relation_key")
        if not isinstance(key, str) or not key or key in seen:
            raise BuildError("Duplicate/missing taxonomy relation key")
        seen.add(key)
        source, target = item.get("source_key"), item.get("target_key")
        if item.get("type") != "IS_A" or source not in keys or target not in keys or source == target:
            raise BuildError("Invalid IS_A endpoints/type/self-loop")
        parents[source].append(target)
    done = set()
    def visit(key, visiting):
        if key in visiting:
            raise BuildError("IS_A cycle")
        if key in done:
            return
        for parent in parents[key]:
            visit(parent, visiting | {key})
        done.add(key)
    for key in keys:
        visit(key, set())


def edge_id(kind, source, target, evidence):
    return "edge:" + digest([SCHEMA, kind, source, target, evidence])


def approval_check(approval_path, report_path, catalog_hash, rule_hash, concept_ids, edge_ids):
    if approval_path is None:
        return False, None
    if report_path is None or not report_path.is_file():
        raise BuildError("Independent review report required for approval")
    approval = read_json(approval_path)
    expected = {"schema_version": "ontology-review-v1", "decision": "APPROVED", "reviewer_role": "graph_reviewer",
                "independent_review": True, "catalog_sha256": catalog_hash, "rule_manifest_sha256": rule_hash,
                "concept_ids": sorted(concept_ids), "edge_ids": sorted(edge_ids),
                "review_report_sha256": digest_bytes(report_path.read_bytes())}
    if any(canonical(approval.get(k)) != canonical(v) for k, v in expected.items()) or not approval.get("reviewer"):
        raise BuildError("Missing/stale independent catalog approval")
    return True, {"path": approval_path.name, "sha256": digest_bytes(approval_path.read_bytes()),
                  "review_report_sha256": expected["review_report_sha256"], "reviewer": approval["reviewer"]}


def build(data, rule_dir, catalog_path, *, approval_path=None, review_report=None):
    rule_nodes, rule_manifest, rule_hash = read_rule_bundle(rule_dir)
    catalog_raw = catalog_path.read_bytes()
    catalog = parse_json(catalog_raw.decode("utf-8-sig"))
    catalog_hash = digest_bytes(catalog_raw)
    if catalog.get("schema_version") != "ontology-catalog-v1" or catalog.get("rule_manifest_sha256") != rule_hash:
        raise BuildError("Stale/missing catalog Rule snapshot")
    if not isinstance(catalog.get("scope_vi"), str) or not catalog["scope_vi"].strip():
        raise BuildError("Catalog scope required")
    concepts = {}
    for item in catalog.get("concepts", []):
        key = item.get("concept_key")
        if not isinstance(key, str) or not key or key in concepts:
            raise BuildError("Duplicate/missing concept key")
        for field in ("label_vi", "definition_vi", "inclusion_criteria_vi", "exclusion_boundary_vi"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise BuildError("Missing curated definition/boundary: " + field)
        if not isinstance(item.get("evidence"), list) or not item["evidence"]:
            raise BuildError("Missing definition evidence")
        checked = [evidence_check(e, rule_nodes) for e in item["evidence"]]
        if item.get("definition_provision_id") != checked[0]["id"] or item["definition_vi"] != item["evidence"][0]["quote"]:
            raise BuildError("Definition must equal its exact source quote")
        concepts[key] = item
    if not concepts:
        raise BuildError("Curated ontology must contain evidence-backed concepts")
    taxonomy = catalog.get("taxonomy", [])
    check_taxonomy(taxonomy, set(concepts))
    nodes, edges, evidence_rows = [], [], []
    source_path = "ontology/" + catalog_path.name
    external_ids = set()

    def provenance(evidences):
        refs = []
        for item in evidences:
            node = evidence_check(item, rule_nodes)
            external_ids.add(node["id"])
            props = node["properties"]
            refs.append({**item, "source_span": {k: props["source_properties"][k] for k in
                         ("coordinate_space", "segment_id", "segment_char_start", "segment_char_end", "document_char_start", "document_char_end", "page_start", "page_end")
                         if k in props["source_properties"]}, "method": "curated_exact_source_quote", "literal_evidence": "VERIFIED"})
        return sorted(refs, key=canonical)

    def props(item, key, evidences):
        return {"source_record_id": key, "source_path": source_path, "source_sha256": catalog_hash,
                "source_record_sha256": digest(item), "source_properties": item, "scope_vi": catalog["scope_vi"],
                "provenance": provenance(evidences), "verification": {"literal_evidence": "VERIFIED", "semantic": "UNVERIFIED", "temporal": "UNVERIFIED"},
                "curation_status": "PROPOSED", "temporal": {"assessment": "UNKNOWN", "verified_applicability": False}}
    for key, item in sorted(concepts.items()):
        node_id = oid("concept", key)
        properties = props(item, key, item["evidence"])
        properties.update({k: item[k] for k in ("label_vi", "definition_vi", "inclusion_criteria_vi", "exclusion_boundary_vi")})
        nodes.append({"id": node_id, "type": "LegalConcept", "layer": "ontology", "properties": properties})
        target = item["definition_provision_id"]
        edges.append({"id": edge_id("REGULATED_BY", node_id, target, item["evidence"]), "source_id": node_id, "target_id": target,
                      "type": "REGULATED_BY", "layer": "cross", "properties": {**props(item, "definition:" + key, item["evidence"]),
                      "mapping_kind": "STATUTORY_DEFINITION", "semantics": "Definition grounding only; no claim of case applicability or current legal effect."}})
    for item in taxonomy:
        if not item.get("rationale_vi") or not item.get("evidence"):
            raise BuildError("IS_A requires explicit rationale and evidence")
        checked = [evidence_check(e, rule_nodes) for e in item["evidence"]]
        classification = rule_nodes.get(item.get("classification_provision_id"))
        source_definition = rule_nodes[concepts[item["source_key"]]["definition_provision_id"]]
        if classification is None or classification["id"] not in {n["id"] for n in checked} or source_definition["id"] not in {n["id"] for n in checked}:
            raise BuildError("IS_A missing source definition/classification evidence")
        if source_definition["properties"]["parent_node_id"] != classification["id"]:
            raise BuildError("Classification is not the source definition parent")
        source, target = oid("concept", item["source_key"]), oid("concept", item["target_key"])
        edges.append({"id": edge_id("IS_A", source, target, item["evidence"]), "source_id": source, "target_id": target,
                      "type": "IS_A", "layer": "ontology", "properties": props(item, item["relation_key"], item["evidence"])})
    approved, approval = approval_check(approval_path, review_report, catalog_hash, rule_hash,
                                        [n["id"] for n in nodes], [e["id"] for e in edges])
    for record in nodes + edges:
        record["properties"]["verification"]["semantic"] = "VERIFIED" if approved else "UNVERIFIED"
        record["properties"]["curation_status"] = "INDEPENDENTLY_REVIEWED" if approved else "PROPOSED"
        if approved:
            record["properties"]["independent_approval"] = approval
        evidence_rows.append({"id": "evidence:" + digest([record["id"], record["properties"]["provenance"]]), "graph_record_id": record["id"],
                              "literal_evidence": "VERIFIED", "semantic": record["properties"]["verification"]["semantic"],
                              "provenance": record["properties"]["provenance"]})
    issues = load_source(data, "issues", "07_research_extensions/knowledge/issues.jsonl", "issue_id")
    issue_index = unique_index(issues)
    for raw, record in sorted(issue_index.items()):
        nodes.append({"id": oid("issue", raw), "type": "LegalIssue", "layer": "ontology", "properties":
                      {**record.ref(), "source_properties": record.row, "label_vi": record.row.get("label_vi", ""),
                       "vocabulary_status": "SOURCE_VOCABULARY", "definition_status": "PENDING_SOURCE_DEFINITION",
                       "provenance": [record.ref()], "verification": {"literal_evidence": "NOT_APPLICABLE", "semantic": "NOT_APPLICABLE", "temporal": "NOT_APPLICABLE"}}})
    association_path = data / "07_research_extensions/knowledge/issue_edges.jsonl"
    association_raw = association_path.read_bytes()
    association_hash = digest_bytes(association_raw)
    groups = {}
    total_keywords = 0
    for line in association_raw.decode("utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = parse_json(line)
        if not isinstance(item, dict):
            raise BuildError("Invalid issue association record")
        key = digest(item);total_keywords += 1
        if key not in groups:
            groups[key] = {"id": "candidate:" + key, "source_path": "07_research_extensions/knowledge/issue_edges.jsonl",
                           "source_sha256": association_hash, "source_record_id": "row:" + key, "source_record_sha256": key,
                           "source_properties": item, "record_count": 0, "outcome": "CANDIDATE", "primary_reason": "KEYWORD_ASSOCIATION_NOT_SEMANTIC_AXIOM",
                           "verification": {"semantic": "UNVERIFIED"}}
        groups[key]["record_count"] += 1
    candidates = sorted(groups.values(), key=lambda r: r["id"])
    local = {n["id"]: n for n in nodes}
    if len(local) != len(nodes) or len({e["id"] for e in edges}) != len(edges):
        raise BuildError("Duplicate published ontology graph ID")
    for edge in edges:
        source, target = local.get(edge["source_id"]), local.get(edge["target_id"], rule_nodes.get(edge["target_id"]))
        if source is None or target is None or source["type"] != "LegalConcept":
            raise BuildError("Missing/wrong ontology edge endpoint")
        if edge["type"] == "IS_A" and (target["type"] != "LegalConcept" or edge["layer"] != "ontology"):
            raise BuildError("Invalid IS_A type/layer")
        if edge["type"] == "REGULATED_BY" and (target["type"] != "Provision" or edge["layer"] != "cross"):
            raise BuildError("Invalid grounding endpoint/layer")
    grounded = {item["definition_provision_id"] for item in concepts.values()}
    coverage = {"curated_concepts": len(concepts), "independently_accepted_concepts": len(concepts) if approved else 0,
                "proposed_concepts": 0 if approved else len(concepts), "taxonomy_edges": len(taxonomy), "grounding_edges": len(grounded),
                "rule_provision_denominator": rule_manifest["counts"]["node_types"]["Provision"], "definition_grounded_provisions": len(grounded),
                "source_issue_vocabulary": len(issue_index), "keyword_association_records": total_keywords, "keyword_axioms_published": 0}
    quality = {"schema_version": SCHEMA, "structural_validation": "PASS", "semantic_release_status": "APPROVED" if approved else "PROPOSED_PENDING_INDEPENDENT_REVIEW",
               "checks": {"duplicate_ids": 0, "dangling_edges_with_declared_rule_dependencies": 0, "IS_A_cycles": 0,
                          "unsupported_keyword_axioms": 0, "verified_applicability_claims": 0}, "coverage": coverage,
               "known_limitations": ["Small vocabulary of source definitions; no exhaustive ontology.", "Grounding is not current applicability.",
                                     "No Fact Graph or case classifications are built in M2."]}
    return {"nodes": sorted(nodes, key=lambda n: n["id"]), "edges": sorted(edges, key=lambda e: e["id"]),
            "candidates": candidates, "rejects": [], "evidence": sorted(evidence_rows, key=lambda e: e["id"]),
            "quality_report": quality, "coverage_report": coverage,
            "dependencies": {"schema_version": SCHEMA, "catalog": {"path": source_path, "sha256": catalog_hash},
                             "rule_manifest_sha256": rule_hash, "rule_build_id": rule_manifest["build_id"], "approval": approval,
                             "external_rule_node_ids": sorted(external_ids),
                             "inputs": [issues.manifest(), {"path": "07_research_extensions/knowledge/issue_edges.jsonl", "sha256": association_hash,
                                                          "bytes": len(association_raw), "records": total_keywords}]}}


def export(result, output, code_hashes):
    raw = {}
    for key in ("nodes", "edges", "candidates", "rejects", "evidence"):
        raw[key + ".jsonl"] = b"".join((canonical(r) + "\n").encode("utf-8") for r in result[key])
    for key in ("quality_report", "coverage_report"):
        raw[key + ".json"] = (canonical(result[key]) + "\n").encode("utf-8")
    deps = {**result["dependencies"], "source_code_sha256": code_hashes}
    manifest = {**deps, "build_id": "build:" + digest(deps), "milestone": "M2", "semantic_release_status": result["quality_report"]["semantic_release_status"],
                "counts": {"nodes": len(result["nodes"]), "edges": len(result["edges"]),
                           "node_types": dict(sorted(Counter(n["type"] for n in result["nodes"]).items())),
                           "edges_by_layer": dict(sorted(Counter(e["layer"] for e in result["edges"]).items()))},
                "artifacts": {name: {"sha256": digest_bytes(value), "bytes": len(value)} for name, value in sorted(raw.items())},
                "determinism": {"encoding": "UTF-8", "newline": "LF", "runtime_timestamps": False}}
    raw["manifest.json"] = (canonical(manifest) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    for name, value in raw.items():
        (output / (name + ".tmp")).write_bytes(value)
        (output / (name + ".tmp")).replace(output / name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("Data"))
    parser.add_argument("--rule", type=Path, default=Path("outputs/rule_graph"))
    parser.add_argument("--catalog", type=Path, default=Path("ontology/curated_concepts_v1.json"))
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--review-report", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/ontology_graph"))
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() == args.data.resolve() or args.data.resolve() in args.output.resolve().parents:
            raise BuildError("Output cannot be inside immutable Data")
        result = build(args.data, args.rule, args.catalog, approval_path=args.approval, review_report=args.review_report)
        if digest_bytes(args.catalog.read_bytes()) != result["dependencies"]["catalog"]["sha256"] or digest_bytes((args.rule / "manifest.json").read_bytes()) != result["dependencies"]["rule_manifest_sha256"]:
            raise BuildError("Catalog/Rule dependency changed during build")
        for item in result["dependencies"]["inputs"]:
            if digest_bytes((args.data / item["path"]).read_bytes()) != item["sha256"]:
                raise BuildError("Ontology source changed during build")
        repo = Path(__file__).resolve().parents[2]
        paths = (Path(__file__).resolve(), repo / "scripts/build_ontology_graph.py", repo / "src/legal_graph/rule_graph.py")
        codes = {p.relative_to(repo).as_posix(): digest_bytes(p.read_bytes()) for p in paths}
        manifest = export(result, args.output, codes)
        print(f"M2 {manifest['semantic_release_status']}: nodes={manifest['counts']['nodes']} edges={manifest['counts']['edges']} catalog_sha256={result['dependencies']['catalog']['sha256']}")
        return 0
    except (BuildError, ValueError, TypeError, KeyError, OSError) as exc:
        print("M2 FAIL: " + str(exc), file=sys.stderr)
        return 1
