# Tiến độ graph offline

Checkpoint: `feature/hier-graph`; tiếp tục tự động theo master #1 và chỉ dẫn người dùng, mỗi milestone phải được reviewer độc lập chấp nhận.

| Mốc | Trạng thái |
|---|---|
| M0 Inventory/schema | PASS_WITH_WARNINGS; đã push c4abb8c; hai P2 runtime được xử lý trong M1 |
| M1 Rule Graph — Issue #2 | PASS re-review repair attempt1;46tests OK; đã push ac262a3 |
| M2 Ontology | PASS cuối approved export;27nodes/12edges; đã push9a6e6a2 |
| M3 Fact |PASS_WITH_SOURCE_LIMITATIONS;24Case/0edges/36queue,68tests OK; đã push17877c4; fact extraction pending |
| M4 Integration |PASS_WITH_SOURCE_LIMITATIONS;10.655nodes/11.814edges;đã push6485a8c |
| M5 Final/export/URL audit |Đã push5f2e7f5;10.655nodes/11.814edges;88tests theo frozen log;7VERIFIED/32UNRESOLVED;static review ACCEPTED_WITH_LIMITATIONS_FOR_OFFLINE_HANDOFF (`docs/milestone_5/REVIEW.md`);chưa independent full rerun |

M1 có10.604nodes/11.802edges;111mismatch queue,22closure excluded;0legal relations/verified applicability. Review PASS tại `docs/milestone_1/REVIEW.md`. Đã comment [Issue2](https://github.com/tvvietanh/LegalGarpRag/issues/2#issuecomment-6944559409). M2 catalog `ontology/curated_concepts_v1.json` có10statutory definitions,2IS_A và10groundings;17issues chỉ vocabulary,7.859keywords candidate. Đã independently approve M2 exact catalog hash/IDs; kiểm thử/logs và workflow approval tại `docs/milestone_2/REPORT.md`.

Data bất biến theo snapshot M0; không API/frontend/model/paid service, không merge main. Baseline XMU đã pin (`docs/BASELINE_PINNED.md`) và audit URL đã ghi snapshot;32 URL còn UNRESOLVED và temporal applicability chưa verified. Offline graph đã đủ bàn giao có giới hạn; không tuyên bố end-to-end QA hoặc full paper replication.
