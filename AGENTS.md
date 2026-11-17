# LegalGarpRag — Codex orchestrator instructions

## Mission and hard boundary
Build **offline** 3-layer Hierarchical Legal Knowledge Graph for Vietnamese Labor Law: Rule Graph, Ontology Graph, Fact Graph, cross-layer integration. All online/server/API/RAG retrieval/Researcher-Auditor-Adjudicator UI tasks belong to another teammate and are OUT OF SCOPE.

## Two subagents
- `graph_builder`: sole implementation owner. May change offline source, configurations, tests and documentation.
- `graph_reviewer`: independent READ-ONLY reviewer. Never edit. Must review *after* each completed builder milestone; findings return to builder to fix.
- Parent/main Codex session acts as coordinator. It must not let both subagents edit files concurrently or self-certify a review.
- Workflow per milestone: parent delegates builder -> waits -> delegates reviewer -> waits -> if FAIL, return precisely identified blockers to builder -> re-review -> record verdict. Two agents are roles, not a claim of automatic infinite background loop.

## Order of work
0. Inventory actual repo and compare with documented baseline; propose schema before code; do not delete old files.
1. Rule Graph: trusted documents/provisions/hierarchy and carefully typed relation and temporal edges.
2. Ontology Graph: curated concepts and issues; explicit definitions, boundaries, evidence; don't equate topic association with formal subclassing.
3. Fact Graph: only graph-eligible cases, separate allegation/findings/decisions; grounded assertions.
4. Cross-layer linking, provenance and temporal gates.
5. Deterministic export for online teammate and test/metric report.

## Quality gates
- Every graph node has `id`, `type`, `layer`, `properties`; every graph edge has `id`, `source_id`, `target_id`, `type`, `layer`, `properties`.
- Stable namespace-aware IDs. No missing endpoint or accidental duplicate. Any excluded records must be counted and explained.
- Existing input is immutable. Never move records from quarantine to trusted output without explicit evidence and review.
- Evidence metadata retained, including document/case/provision source references and span when available.
- Temporal status must be honest: inherited/unverified != verified at provision level.
- OWL is optional; formal semantics may be represented as typed node/edge schema first.
- Never invent facts, statute applicability or source URLs.
- Read `docs/GRAPH_CONTRACT.md` before writing code. Fields there are v1 **output design** and not assumptions about existing input.

## Required final artifacts
`outputs/graph_v1/nodes.jsonl`, `outputs/graph_v1/edges.jsonl`, `outputs/graph_v1/manifest.json`, `outputs/graph_v1/quality_report.json`, documented run commands, tests, and review report. Existing repository conventions can override paths with documented rationale.

## Reference
XMU baseline: https://github.com/XMUDeepLIT/LegalGraphRAG (inspect `core/graph_construct` if available). Project: https://github.com/tvvietanh/LegalGarpRag . Cite exact source code files when attributing baseline behavior.
