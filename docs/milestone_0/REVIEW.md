**VERDICT = PASS_WITH_WARNINGS cho Milestone 0.** Không có blocker P0/P1. Có thể ghi nhận M0 đạt yêu cầu kiểm kê và đề xuất schema, kèm hai cảnh báo P2 dưới đây.

Đã đọc toàn bộ `AGENTS.md`, `docs/GRAPH_CONTRACT.md`, cấu hình hai custom agents, source kiểm kê, tests và các artifacts M0. Reviewer không chỉnh sửa source, dữ liệu hoặc báo cáo bàn giao.

Các findings P2

- `scripts/inventory_graph_inputs.py:272` dùng `Path.write_text()` với newline mặc định. Hai inventory hiện tại giống byte trên Windows nhưng chứa 30.089 CRLF. Serialize cùng object bằng LF cho SHA-256 khác. Đây là giới hạn tái lập xuyên hệ điều hành của công cụ M0. Schema graph đã quy định LF tại `SCHEMA_PROPOSAL.md:92`. Khi triển khai exporter M1/M5 cần thực thi quy tắc đó.
- `scripts/inventory_graph_inputs.py:138` dựng index bằng dictionary comprehension, nên bản ghi trùng ID sẽ lấy dòng cuối khi audit join. Profile vẫn báo duplicate đầy đủ. Dataset hiện tại chỉ có duplicates trong tập quarantine, vì thế không làm sai số liệu trusted screen đã báo. Trước khi tái sử dụng logic cho graph builder, phải chặn conflicting duplicate và raw-ID collision giữa loại endpoint theo schema tại `SCHEMA_PROPOSAL.md:9` và `:88`.

Checklist chấp nhận

| Nội dung | Kết quả |
|---|---|
| Kiểm kê dữ liệu thực và ZIP, không dùng số lịch sử làm giả định | PASS |
| Đối chiếu field/schema JSONL thực tế | PASS |
| Hash đầu vào và khả năng tái lập trên môi trường hiện tại | PASS |
| Rule schema, hướng hierarchy, namespace Provision/Version | PASS |
| Ontology phân biệt vocabulary, keyword association và `IS_A` | PASS |
| Fact phân biệt allegation/finding/adjudication, tôn trọng facts disabled | PASS |
| Cross-layer typed endpoints và evidence/semantic review gates | PASS |
| Temporal kế thừa không trở thành verified provision applicability | PASS |
| Quarantine và unresolved targets được ghi nhận, có gate chặn | PASS |
| Phạm vi M0 và kế hoạch triển khai/kiểm thử các milestone sau | PASS |

Kiểm tra độc lập đã chạy

- `python -B -m unittest discover -s tests -v` đạt **12/12 OK**.
- Gọi lại `inventory(Path.cwd())` trong memory. Object khớp hoàn toàn với `inventory.json`.
- Serialize theo newline Windows khớp byte cả `inventory.json` và `inventory.rerun.json`. SHA-256 cùng là `92a8d824401336c831ca417e4b43a2c0bec2fab8ae620a4d2a1b29794a7bd893`.
- Dataset digest khớp `30ebe107f6a48803e32769f788f1982662d8000e55a343fe01dd768e0db8a79e`. `git diff --exit-code -- Data` trả exit 0.
- Đọc trực tiếp JSONL, xác nhận 107 metadata, 18.871 provisions, 896 quarantine records, 15.651 identities, 18.871 versions, 36 cases và 562 headings.
- Kiểm tra độc lập toàn bộ parent levels, cycle và version–identity–document joins, đều **0 lỗi**.
- Xác nhận 4.067 provisions qua policy screen, 111 trong số đó có literal mismatch. Toàn bộ 18.871 versions là `INHERITED_DOCUMENT` với `provision_temporal_verified=false`. Cả 36 cases có `case_extracted_facts_enabled=false`.
- Accepted relations có 0 missing endpoints. Citations có 2.313 unresolved targets. Các số liệu khớp artifacts.

Đã truy cập lại năm source files XMU, các mô tả baseline khớp nội dung quan sát. Baseline dùng Fact liên kết Case/Law/Crime, Ontology có kNN/cộng đồng, Rule giữ trường trên Law nodes. Đề xuất Việt Nam phân biệt rõ các điều chỉnh theo yêu cầu bằng chứng và thời gian. Giới hạn chưa pin revision đã được công khai tại `BASELINE_XMU.md:9`. [Fact source](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/fact_graph.py), [Ontology source](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/ontology_graph.py), [Rule source](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/rule_graph.py).

Rủi ro còn lại và bước tối thiểu tiếp theo

646 literal mismatches, missing historical review artifacts, unresolved citations và thiếu reviewed concept/fact extraction đã được ghi nhận và có gate trong thiết kế. Trước triển khai Rule Graph, cần thực thi gate cho 111 policy-eligible mismatches cùng child closure, duplicate rejection, endpoint allow-list và temporal uncertainty. Khi port hành vi cụ thể từ XMU, cần pin revision hoặc lưu snapshot/hash đã kiểm tra.

Parent có thể giao builder ghi nguyên văn verdict này vào `docs/milestone_0/REVIEW.md`, rồi chốt Milestone 0.
