# Offline Three-layer Graph — proposed v1 output contract

## Inputs (checked against user-provided archive 01_raw_data.zip)
- `02_processed_data/provisions.jsonl`: `provision_id`, `document_id`, `level`, `parent_id`, `text`, `canonical_path`, `provision_identity_id`, `provision_version_id`, provenance/page fields.
- `04_metadata/documents.jsonl`: `document_id`, `source_group`, `record_classification`, `document_type`, `source_url`, `metadata_verified`, `temporal_verified`, `status`, `valid_from`, `valid_to`.
- `06_temporal/provision_versions.jsonl`: `provision_version_id`, `provision_identity_id`, `valid_from`, `valid_to`, `temporal_status`, `provision_temporal_verified`.
- `03_case_data/cases.jsonl`: `case_id`, `document_id`, `facts`, `reasoning`, `decision`, `full_text`, `graph_eligible`, `graph_status`, review-status and provenance fields.
- `07_research_extensions/knowledge/accepted_relation_edges.jsonl`: `edge_id`, `source_id`, `target_id`, `type`, `evidence_status`, `resolution_scope`, `evidence_span`.
- `07_research_extensions/knowledge/issues.jsonl`: `issue_id`, `issue_key`, `label_vi`.
- `07_research_extensions/knowledge/issue_edges.jsonl`: `source_id`, `target_id`, `type`, `provenance_status`, `evidence_span`.
- May be nested under `Data/`. Validate path and file schema dynamically; do not hardcode historical counts.

## Export schema (not yet implemented)
`nodes.jsonl`: `{ "id": "rule:document:<source_id>", "type": "Document", "layer": "rule", "properties": { ... } }`
`edges.jsonl`: `{ "id": "edge:<stable_hash>", "source_id": "...", "target_id": "...", "type": "CONTAINS", "layer": "rule", "properties": { "evidence_source_id": "...", "verification_status": "..." } }`
Use one immutable qualified ID per node, explicit `source_record_id`, original fields preserved in properties where material. No fabricated null values when source lacks data.

### Rule
Nodes: `Document`, `Provision` (ARTICLE/CLAUSE/POINT property), `ProvisionIdentity`, `ProvisionVersion`; optional `LegalRule` only after separate semantic validation.
Edges: `CONTAINS`, `HAS_IDENTITY`, `HAS_VERSION`, `CITES`, `REFERENCES`, `AMENDS`, `REPEALS`, `REPLACES` with typed endpoints; source records must support the chosen direction.
Do NOT automatically assert date-validity at provision level from `INHERITED_DOCUMENT`.

### Ontology
Nodes: `LegalIssue`, `LegalConcept`; optional curated `ActorType`, `ActionType` as subclasses/categories only after review.
Edges: `IS_A` (curated and semantically justified), `RELATED_TO` (weak topical relation clearly labeled), `ABOUT_ISSUE` or equivalent, `REGULATED_BY` only with grounding. Do not equate weak issue matches to ontology axioms.

### Fact
Nodes: `Case`, `Actor`, `Event`, `FactAssertion`, optionally `EvidenceSpan`.
Edges: `HAS_ASSERTION`, `HAS_EVENT`, `INVOLVES`, `SUPPORTED_BY`; separate `ALLEGED_BY`, `FOUND_BY_COURT`, `DECIDED_BY` or assertion status properties when supported. If no reviewed event extraction, export only Case nodes and explicitly report 'fact extraction pending' — never auto-invent assertions.

### Cross layer
Allowed: `INSTANCE_OF` (Fact -> Ontology), `REGULATED_BY` (Ontology -> Rule), grounded `CITES` (Case -> Provision/Document) where typed, documented with evidence. Validate every edge endpoint and evidence. Cross-layer mapping can be incomplete; quantify coverage.

## Acceptance gates
- Duplicate IDs = 0; invalid dangling edges in published graph = 0 (report rejects separately).
- Trusted output excludes quarantined provisions and graph-ineligible cases.
- All published extracted legal assertions/effective-date claims have verified evidence; unreviewed edges must remain candidate-only.
- Deterministic build: same inputs/config -> same IDs/content + stable order (exclude runtime timestamps from hash comparison).
- Manifest includes input hashes, schema version, record counts, layer counts, excluded counts, reject reasons and validation verdict.
- Unit tests cover namespace collisions, parent ordering, evidence, source/target types, temporal uncertainty and quarantine.

## Reference-scale snapshot only, not current ground truth
Earlier inspected ZIP: 107 metadata documents, 18,871 provisions, 2,029 accepted relations, 17 issues, 7,859 issue edges, 36 cases (24 ACTIVE). Runtime must compute actual numbers again; evidence-status of extracted issue edges does NOT guarantee semantic truth.
