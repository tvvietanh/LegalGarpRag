# Tiến độ graph offline

Checkpoint: `feature/hier-graph`; tiếp tục tự động theo master #1 và chỉ dẫn người dùng, mỗi milestone phải được reviewer độc lập chấp nhận.

| Mốc | Trạng thái |
|---|---|
| M0 Inventory/schema | PASS_WITH_WARNINGS; đã push c4abb8c; hai P2 runtime được xử lý trong M1 |
| M1 Rule Graph — Issue #2 | PASS re-review repair attempt1;46tests OK; đã push ac262a3 |
| M2 Ontology | PASS cuối approved export;27nodes/12edges;57tests trước và11targeted approved OK; chuẩn bị push |
| M3 Fact | Mốc kế tiếp tự động; facts disabled phải giữ giới hạn Case-only khi policy yêu cầu |
| M4 Integration | Chưa bắt đầu; không tạo liên kết thiếu evidence |
| M5 Final/export/URL audit | Chưa bắt đầu; VERIFIED identity hoặc honest UNRESOLVED/BLOCKED |

M1 có10.604nodes/11.802edges;111mismatch queue,22closure excluded;0legal relations/verified applicability. Review PASS tại `docs/milestone_1/REVIEW.md`. Đã comment [Issue2](https://github.com/tvvietanh/LegalGarpRag/issues/2#issuecomment-6944559409). M2 catalog `ontology/curated_concepts_v1.json` có10statutory definitions,2IS_A và10groundings;17issues chỉ vocabulary,7.859keywords candidate. Draft semantic UNVERIFIED tới khi graph_reviewer approve exact catalog hash/IDs; kiểm thử/logs và workflow approval tại `docs/milestone_2/REPORT.md`.

Data bất biến theo snapshot M0; không API/frontend/model/paid service, không merge main. Pin XMU revision và live URL identity audit vẫn pending trong master, không tuyên bố hoàn tất từ graph checkpoint.
