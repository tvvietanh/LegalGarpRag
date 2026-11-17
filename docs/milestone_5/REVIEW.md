# M5 — Final review of committed offline graph artifacts

**Review date:** 2026-11-17 (Asia/Ho_Chi_Minh)  
**Repository:** `tvvietanh/LegalGarpRag`  
**Reviewed checkpoint:** `5f2e7f531244d01206ac3db156f1e387eecf697c` (`feature/hier-graph`)  
**Reviewer:** ChatGPT (GitHub source/artifact inspection; not the previous `graph_reviewer` execution environment)  
**Verdict:** **ACCEPTED_WITH_LIMITATIONS_FOR_OFFLINE_HANDOFF (repository/artifact review)**  
**Independent full rebuild/test execution:** **NOT PERFORMED**.

## 1. What was checked

Read the committed M5 implementation (`src/legal_graph/final_release.py`, `src/legal_graph/url_audit.py`), regression tests (`tests/test_final_release.py`), pinned configuration (`configs/final_graph_v1.json`), source URL approval evidence, final manifest/quality/coverage reports, `outputs/final/url_audit.jsonl`, `outputs/final/traversal_examples.json`, prior M1–M4 reviewer reports, draft M5 review, final QA proof and test log.

This was an external **static source and artifact consistency review**, **not** a claim that the reviewer re-ran 88 tests, independently re-downloaded all documents, regenerated the complete graph, or rehashed all 219 original local source files.

## 2. Evidence and observed results

- `outputs/final/manifest.json` and `quality_report.json` report **10,655 nodes / 11,814 edges**: Rule **10,604 / 11,802**, Ontology **27 nodes / 2 internal edges**, Fact **24 Case nodes / 0 edges**, and **10 cross-layer REGULATED_BY** definition-grounding edges.
- `docs/milestone_5/TEST_LOG.txt` contains **88 test lines ending in `... ok`**, followed by `Ran 88 tests` and `OK`. `audit/final_qa_v1.json` reports **88 passed, 0 failures, 0 errors** and unchanged 219 source file hashes. These are **committed test records**, not a new test run by this reviewer.
- Independently parsed the committed URL sidecar rows: `outputs/final/url_audit.jsonl` has **39 records: 7 VERIFIED, 32 UNRESOLVED**. The earlier frozen observation file has **3 VERIFIED, 36 UNRESOLVED**, explaining the post-review uplift by four approved identity records. **HTTP 200 alone is not treated as identity verification**.
- `traversal_examples.json` contains **two example concept → Rule provision → Document traversals**, and **zero reviewed Case graph links**. Case document property references are explicitly NOT inferred semantic edges.
- M5 code validates pinned M4 artifact hashes/counts, upstream source/config/review hashes, exact frozen URL observation context, manual proof binding, cached QA proof and test-log hash before exporting. No network call is required by the final offline builder; URL collection is separate.
- M1–M4 prior reviewer reports state PASS/PASS_WITH_SOURCE_LIMITATIONS. M5 reuses reviewed graph records, preserving source exclusions, candidates and unresolved temporal applicability.

## 3. Findings

### P0/P1 — none identified in reviewed code and artifacts
No critical blocking defect was found through the **static/metadata review**. This statement does not guarantee that an unexecuted regression or manual legal review could not reveal a defect.

### P2 — stale draft documentation
`docs/milestone_5/REPORT.md`, `VALIDATION.txt`, `docs/FINAL_CHECKLIST.md`, `docs/HANDOFF.md`, and `docs/PROGRESS.md` include earlier draft figures (**86 tests, 3 VERIFIED / 36 UNRESOLVED**) or `review pending` language, while committed final `quality_report.json`, QA proof and URL sidecar show **88 tests, 7 VERIFIED / 32 UNRESOLVED**. Interpret those files as historical draft checkpoints until synchronized. **Do not alter `docs/milestone_5/REVIEW_DRAFT.md` casually**: the manual URL approval artifact pins its SHA-256.

### Coverage limitations — explicitly accepted, not fixed
- Fact extraction is disabled/unreviewed: **24 Case identities, 0 Actor/Event/FactAssertion, 0 semantic Case links**.
- Ontology is curated and small (**10 approved concepts, 2 IS_A, 10 definition groundings**).
- No provision-level verified legal applicability/temporal validity; no approval to infer it.
- **32/39 source URLs remain UNRESOLVED**, not necessarily unreachable. URL identity proof is separate from legal effectivity.
- **111 eligible text-span mismatches, 22 dependent child exclusions and 896 quarantined provision records** remain excluded. Keyword-derived relations remain candidates.
- Current graph supports a **narrow Ontology → Rule retrieval demonstration**, not a full Fact → Ontology → Rule judgment chain.

## 4. Release decision and handoff

**Accept the committed M5 bundle for limited offline integration/demo** using `outputs/final/{nodes.jsonl,edges.jsonl,manifest.json,quality_report.json,url_audit.jsonl}` and `docs/HANDOFF.md`. Downstream Researcher/Auditor/Adjudicator must preserve verification statuses and abstain where a URL, time applicability or case fact has not been verified.

**Do not label the deliverable a fully verified legal dataset, full paper replication, all-URLs-verified, or independently re-executed M5 PASS.**

For final formal signoff, optionally re-run the full tests/build on a clean checkout with the pinned data snapshot and reconcile draft documentation. This review closes the **GitHub source/artifact review** without changing M1–M5 graph data or the hash-pinned review evidence.

## 5. URLs to review materials

- `outputs/final/manifest.json`
- `outputs/final/quality_report.json`
- `audit/final_qa_v1.json`
- `docs/milestone_5/TEST_LOG.txt`
- `docs/milestone_5/REVIEW_DRAFT.md` (historical source approval decision)
- `docs/milestone_5/VALIDATION.txt` (historical draft validation)
