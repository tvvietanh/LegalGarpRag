# Tiến độ graph offline

Checkpoint: `feature/hier-graph`; tiếp tục tự động theo master #1 và chỉ dẫn người dùng, mỗi milestone phải được reviewer độc lập chấp nhận.

| Mốc | Trạng thái |
|---|---|
| M0 Inventory/schema | PASS_WITH_WARNINGS; đã push c4abb8c; hai P2 runtime được xử lý trong M1 |
| M1 Rule Graph — Issue #2 | PASS re-review repair attempt1;46tests OK; chuẩn bị commit/push sau verdict |
| M2 Ontology | Mốc kế tiếp tự động; curated concepts/grounding có evidence, không chỉ keyword labels |
| M3 Fact | Chưa bắt đầu; facts disabled phải giữ giới hạn Case-only khi policy yêu cầu |
| M4 Integration | Chưa bắt đầu; không tạo liên kết thiếu evidence |
| M5 Final/export/URL audit | Chưa bắt đầu; VERIFIED identity hoặc honest UNRESOLVED/BLOCKED |

M1 có 10.604 nodes/11.802 structural edges;111 eligible mismatch queue,22 child closure excluded,0 legal relations/verified applicability claims. Repair attempt1 bind explicit review endpoint/context snapshots và kiểm tất cả supplied coordinate spaces; reviewer đã PASS, không còn P0/P1. Tests/logs: `docs/milestone_1/VALIDATION.txt`; lịch sử FAIL: `docs/milestone_1/REVIEW_ROUND_1.md`; verdict: `docs/milestone_1/REVIEW.md`. Bàn giao commit/push M1 rồi parent giao builder M2 ngay, không chờ xác nhận mới từ người dùng.

Data bất biến theo snapshot M0; không API/frontend/model/paid service, không merge main. Pin XMU revision và live URL identity audit vẫn pending trong master, không tuyên bố hoàn tất từ graph checkpoint.
