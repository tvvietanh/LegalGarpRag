"""Final reproducible dataset. No network calls; observed URLs stay a sidecar."""
import argparse
from collections import Counter
from pathlib import Path
import sys

from .rule_graph import BuildError, canonical, digest, digest_bytes, parse_json
from .integration import safe_path, read_rows, validate_union
from .url_audit import classify, normalize, source_url

SCHEMA = "final-graph-v1"


def pinned_file(root, entry):
    path = safe_path(root, entry["path"])
    raw = path.read_bytes()
    if digest_bytes(raw) != entry["sha256"]:
        raise BuildError("Stale pinned release input: " + entry["path"])
    return raw


def audit_rows(nodes, observation_raw, root, manual=None):
    documents = {n["id"]: n for n in nodes if n["type"] == "Document"}
    observations = read_rows(observation_raw);seen = set();result = []
    approvals = {}
    if manual:
        if (manual.get("schema_version") != "url-identity-review-v1" or manual.get("reviewer_role") != "graph_reviewer" or
                manual.get("independent_review") is not True or not manual.get("reviewer") or
                manual.get("observation_snapshot_sha256") != digest_bytes(observation_raw)):
            raise BuildError("Invalid/stale independent URL identity review")
        for item in manual.get("approvals", []):
            key = item.get("document_node_id")
            if key in approvals or key not in documents:
                raise BuildError("Duplicate/missing reviewed URL Document")
            approvals[key] = item
    for observation in observations:
        key = observation.get("document_node_id")
        if key not in documents or key in seen:
            raise BuildError("Duplicate/unknown Document in URL snapshot")
        seen.add(key);node = documents[key];row = node["properties"]["source_properties"]
        field, original = source_url(node)
        if (observation.get("document_node_sha256") != digest(node) or observation.get("original_url") != original or
                observation.get("source_url_field") != field or not observation.get("checked_at")):
            raise BuildError("Stale URL document context or missing check timestamp")
        evidence = observation.get("identity_evidence", {})
        header = evidence.get("header_excerpt", "")
        expected = {"number": row.get("document_number") or row.get("instrument_number") or row.get("case_number") or "",
                    "title": row.get("title") or "", "authority": row.get("issuer") or ""}
        if evidence.get("expected_source_identity") != expected:
            raise BuildError("URL identity source expectations changed")
        for name, value in expected.items():
            needle = normalize(value)
            matched = bool(needle and len(needle) >= 4 and needle in normalize(header))
            if evidence.get(name + "_match") is not matched:
                raise BuildError("URL header match flags contradict frozen evidence")
        if "header_sha256" in evidence and evidence["header_sha256"] != digest_bytes(header.encode("utf-8")):
            raise BuildError("URL header evidence hash mismatch")
        if evidence.get("local_source_sha256_match"):
            relative = row.get("local_file_path")
            if not isinstance(relative, str) or evidence.get("local_source_path") != relative:
                raise BuildError("URL local lineage path mismatch")
            local_sha = digest_bytes(safe_path(root / "Data", relative).read_bytes())
            if not (local_sha == row.get("local_sha256") == evidence.get("local_source_sha256") == observation.get("response_sha256")):
                raise BuildError("URL local/fetched byte lineage mismatch")
        status, reasons = classify(node, observation)
        if observation.get("url_status") != status or (status != "VERIFIED" and "resolved_url" in observation):
            raise BuildError("URL status/resolution contradicts identity evidence")
        if status == "VERIFIED" and observation.get("resolved_url") != observation.get("final_url"):
            raise BuildError("Verified resolved URL must equal observed final URL")
        audit = dict(observation)
        approval = approvals.get(key)
        if approval:
            if (approval.get("decision") != "APPROVED" or approval.get("observation_record_sha256") != digest(observation) or
                    approval.get("document_node_sha256") != digest(node) or approval.get("response_sha256") != observation.get("response_sha256") or
                    observation.get("http_status") != 200 or not observation.get("response_is_pdf") or observation.get("truncated") or observation.get("access_error")):
                raise BuildError("Stale/unsupported manual URL identity approval")
            if approval.get("expected_number") != expected["number"] or not normalize(expected["number"]):
                raise BuildError("Reviewed document number differs from source identity")
            proof_text = header
            if approval.get("proof_kind") == "PDF_PAGE_VISUAL_IDENTITY":
                if type(approval.get("pdf_page_number")) is not int or approval["pdf_page_number"] != 1:
                    raise BuildError("Visual URL identity proof requires exact page1")
                if (evidence.get("local_source_sha256_match") is not True or
                        approval.get("local_pdf_sha256") != evidence.get("local_source_sha256") or
                        approval["local_pdf_sha256"] != observation.get("response_sha256")):
                    raise BuildError("Visual PDF response/local lineage mismatch")
                local_pdf = safe_path(root / "Data", row["local_file_path"]).read_bytes()
                if not local_pdf.lstrip().startswith(b"%PDF-") or digest_bytes(local_pdf) != approval["local_pdf_sha256"]:
                    raise BuildError("Visual proof source is not the matched PDF")
                image_path = safe_path(root, approval.get("rendered_page_path", ""))
                if not image_path.is_relative_to((root / "audit/evidence").resolve()) or image_path.suffix.lower() != ".png":
                    raise BuildError("Visual proof path must be inside audit/evidence")
                image = image_path.read_bytes()
                if not image.startswith(b"\x89PNG\r\n\x1a\n") or digest_bytes(image) != approval.get("rendered_page_sha256"):
                    raise BuildError("Visual page image hash/signature mismatch")
                proof_text = approval.get("transcript", "")
                if not isinstance(proof_text, str) or not proof_text or len(proof_text) > 8000 or not approval.get("renderer"):
                    raise BuildError("Bounded independent visual transcript/renderer required")
            elif not approval.get("evidence_quote") or approval["evidence_quote"] not in header:
                raise BuildError("Manual URL identity evidence quote not in fetched header")
            if normalize(expected["number"]) not in normalize(proof_text):
                raise BuildError("Reviewed document number not supported by fresh proof")
            for name in ("reviewed_title_alias", "reviewed_authority"):
                needle = normalize(approval.get(name, ""))
                if len(needle) < 4 or needle not in normalize(proof_text):
                    raise BuildError("Manual title/authority evidence not grounded")
            audit.update({"url_status": "VERIFIED", "resolved_url": observation["final_url"],
                          "reason_codes": ["INDEPENDENT_FRESH_DOCUMENT_IDENTITY_REVIEW"], "independent_identity_review": approval,
                          "identity_reviewer": manual["reviewer"]})
        audit["legal_temporal_effect_verified"] = False
        result.append(audit)
    if seen != set(documents):
        raise BuildError("URL snapshot must account for every published Document")
    return sorted(result, key=lambda r: r["document_node_id"])


def build(root, config_path):
    config_raw = config_path.read_bytes();config = parse_json(config_raw.decode("utf-8"))
    if config.get("schema_version") != SCHEMA:
        raise BuildError("Invalid final release config")
    m4_raw = pinned_file(root, config["integrated_manifest"]);m4 = parse_json(m4_raw.decode("utf-8"))
    if m4.get("schema_version") != "integrated-graph-v1" or m4.get("validation_verdict") != "PASS_WITH_SOURCE_LIMITATIONS":
        raise BuildError("Final release requires accepted integrated checkpoint")
    folder = safe_path(root, config["integrated_manifest"]["path"]).parent
    artifacts = {}
    for name, entry in m4["artifacts"].items():
        raw = safe_path(folder, name).read_bytes()
        if digest_bytes(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
            raise BuildError("Integrated artifact changed: " + name)
        artifacts[name] = raw
    for path, sha in m4["source_code_sha256"].items():
        if digest_bytes(safe_path(root, path).read_bytes()) != sha:
            raise BuildError("Integrated source code changed")
    if digest_bytes((root / "configs/integrated_graph_v1.json").read_bytes()) != m4["config_sha256"]:
        raise BuildError("Integrated config changed")
    for path, sha in m4["input_snapshot_sha256"].items():
        if digest_bytes(safe_path(root / "Data", path).read_bytes()) != sha:
            raise BuildError("Integrated source Data changed")
    upstream = {}
    for tag, sha in m4["upstream_manifest_sha256"].items():
        upstream_raw = (root / "outputs" / (tag + "_graph") / "manifest.json").read_bytes()
        if digest_bytes(upstream_raw) != sha:
            raise BuildError("Upstream checkpoint changed")
        upstream[tag] = parse_json(upstream_raw.decode("utf-8"))
    reviews = {}
    for entry in config["upstream_reviews"]:
        pinned_file(root, entry);reviews[entry["path"]] = entry["sha256"]
    nodes, edges = read_rows(artifacts["nodes.jsonl"]), read_rows(artifacts["edges.jsonl"])
    checks = validate_union(nodes, edges, {e["id"] for e in edges if e["layer"] != "rule"})
    if len(nodes) != m4["counts"]["nodes"] or len(edges) != m4["counts"]["edges"]:
        raise BuildError("Final graph counts disagree with pinned integration")
    observations_raw = pinned_file(root, config["url_observations"])
    manual = None
    if config.get("url_identity_approval"):
        manual = parse_json(pinned_file(root, config["url_identity_approval"]).decode("utf-8"))
        report_raw = pinned_file(root, config["url_identity_review_report"])
        if manual.get("review_report_sha256") != digest_bytes(report_raw):
            raise BuildError("Manual URL identity review report changed")
    audit = audit_rows(nodes, observations_raw, root, manual)
    qa = parse_json(pinned_file(root, config["qa_proof"]).decode("utf-8"))
    if qa.get("test_failures") != 0 or qa.get("test_errors") != 0 or qa.get("tests_passed", 0) <= 0 or qa.get("all_219_data_hashes_match") is not True:
        raise BuildError("Final QA proof does not pass")
    for relative, sha in qa["validated_source_sha256"].items():
        if digest_bytes(safe_path(root, relative).read_bytes()) != sha:
            raise BuildError("QA source/test snapshot stale")
    if digest_bytes(pinned_file(root, config["test_log"])) != qa["test_log_sha256"]:
        raise BuildError("Final test log/proof mismatch")
    baseline_raw = pinned_file(root, config["baseline_snapshot"])
    baseline = parse_json(baseline_raw.decode("utf-8"))
    url_counts = dict(sorted(Counter(r["url_status"] for r in audit).items()))
    metadata = read_rows((root / "Data/04_metadata/documents.jsonl").read_bytes())
    source_dispositions = {"metadata_input_records": len(metadata), "published_documents": sum(n["type"] == "Document" for n in nodes),
                           "quarantined_metadata_records": sum(r.get("graph_status") == "QUARANTINE" for r in metadata),
                           "quarantined_provision_records": upstream["rule"]["record_accounting"]["quarantine"]["input_records"],
                           "provision_exclusion_primary_reasons": upstream["rule"]["record_accounting"]["provisions"]["primary_reasons"],
                           "case_coverage": upstream["fact"]["coverage"],
                           "keyword_candidate_records": sum(r["records"] for r in upstream["ontology"]["inputs"] if r["path"].endswith("/issue_edges.jsonl")),
                           "candidate_source_records": m4["counts"]["candidate_source_records"],
                           "reject_or_excluded_source_records": m4["counts"]["reject_or_excluded_source_records"],
                           "unit": "Source table records;do not sum cross-table or queue overlays as unique documents/provisions."}
    quality = {"schema_version": SCHEMA, "final_status": "PASS_WITH_LIMITATIONS", "independent_final_review": "SEE_EXTERNAL_M5_REVIEW_REPORT",
               "checks": checks, "counts": m4["counts"], "url_status_counts": url_counts, "source_dispositions": source_dispositions,
               "temporal": {"verified_applicability_claims": 0, "inherited_or_unknown_preserved": True,
                            "node_assessment_counts": dict(sorted(Counter(n["properties"].get("temporal", {}).get("assessment", "NOT_APPLICABILITY_ASSERTION") for n in nodes).items()))},
               "tests": {"passed": qa["tests_passed"], "failures": 0, "errors": 0, "test_log_sha256": qa["test_log_sha256"]},
               "limitations": ["Case extraction disabled/unreviewed:24Case identities, no Actor/Event/FactAssertion.",
                               "10concept definition groundings do not establish case applicability or current legal effect.",
                               "Unresolved/blocked source URLs require identity review;HTTP200 alone is not verification.",
                               "111eligible text mismatches and22dependent descendants remain excluded;quarantine not promoted.",
                               "7859keyword associations and other unresolved relations remain candidate-only."]}
    final = {name: raw for name, raw in artifacts.items() if name not in {"quality_report.json"}}
    final["url_audit.jsonl"] = b"".join((canonical(row) + "\n").encode("utf-8") for row in audit)
    final["quality_report.json"] = (canonical(quality) + "\n").encode("utf-8")
    dependencies = {"schema_version": SCHEMA, "config_sha256": digest_bytes(config_raw),
                    "integrated_manifest_sha256": digest_bytes(m4_raw), "integrated_build_id": m4["build_id"],
                    "url_observation_snapshot_sha256": digest_bytes(observations_raw), "qa_proof": config["qa_proof"],
                    "test_log": config["test_log"], "upstream_review_sha256": reviews, "url_identity_approval": config.get("url_identity_approval", {}),
                    "visual_url_evidence_sha256": {item["rendered_page_path"]: item["rendered_page_sha256"] for item in (manual or {}).get("approvals", [])
                                                   if item.get("proof_kind") == "PDF_PAGE_VISUAL_IDENTITY"},
                    "baseline_snapshot_sha256": digest_bytes(baseline_raw), "baseline_commit": baseline["commit"],
                    "input_snapshot": {"dataset_digest": qa["dataset_digest"], "files_checked": 219, "tracked_data_files": 218,
                                       "optional_local_zip_not_committed": True, "consumed_source_sha256": m4["input_snapshot_sha256"]}}
    return final, dependencies, quality


def export(artifacts, dependencies, quality, output, code_hashes):
    deps = {**dependencies, "source_code_sha256": code_hashes}
    manifest = {**deps, "milestone": "M5", "build_id": "build:" + digest(deps), "final_status": "PASS_WITH_LIMITATIONS",
                "counts": quality["counts"], "url_status_counts": quality["url_status_counts"], "temporal": quality["temporal"], "tests": quality["tests"],
                "source_dispositions": quality["source_dispositions"],
                "known_limitations": quality["limitations"], "reproduction_command": "python -B scripts/build_final_graph.py",
                "independent_final_review": "docs/milestone_5/REVIEW.md external;not hashed here to avoid self-reference",
                "artifacts": {name: {"bytes": len(raw), "sha256": digest_bytes(raw)} for name, raw in sorted(artifacts.items())},
                "determinism": {"encoding": "UTF-8", "newline": "LF", "runtime_network_calls": 0, "timestamps": "Frozen URL observation input only"}}
    raw = {**artifacts, "manifest.json": (canonical(manifest) + "\n").encode("utf-8")}
    output.mkdir(parents=True, exist_ok=True)
    for name, data in raw.items():
        (output / (name + ".tmp")).write_bytes(data);(output / (name + ".tmp")).replace(output / name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/final_graph_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/final"))
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve();output = args.output.resolve()
        if output == root / "Data" or (root / "Data") in output.parents:
            raise BuildError("Final output cannot be inside Data")
        config = args.config if args.config.is_absolute() else root / args.config
        artifacts, dependencies, quality = build(root, config)
        repo = Path(__file__).resolve().parents[2]
        paths = [Path(__file__).resolve(), repo / "scripts/build_final_graph.py", repo / "src/legal_graph/url_audit.py", repo / "src/legal_graph/integration.py"]
        manifest = export(artifacts, dependencies, quality, output, {p.relative_to(repo).as_posix(): digest_bytes(p.read_bytes()) for p in paths})
        print(f"M5 PASS_WITH_LIMITATIONS: nodes={manifest['counts']['nodes']} edges={manifest['counts']['edges']} URLs={manifest['url_status_counts']};offline cached observations.")
        return 0
    except (BuildError, ValueError, TypeError, KeyError, OSError) as exc:
        print("M5 FAIL: " + str(exc), file=sys.stderr);return 1
