# M4 — tích hợp offline, chờ review

Trạng thái cuối: reviewer **PASS_WITH_SOURCE_LIMITATIONS**, không P0/P1; xem [REVIEW.md](REVIEW.md). Các mô tả chờ review bên dưới lưu mốc trước verdict. Chuẩn bị commit/push rồi tiếp M5 tự động.

Union thực có **10.655nodes** (rule10.604,ontology27,fact24), **11.814edges** (rule11.802,ontology2,cross10,fact0). Không đổi node/edge records đã review của upstream; M2groundings chỉ STATUTORY_DEFINITION, không applicability.24Cases không có graph edges; chỉ có qualified document property references. Không suy Case→Concept/Provision từ titles, keywords hoặc citation chưa review.

`configs/integrated_graph_v1.json` pin chính xác3manifest hashes đã reviewer chấp thuận. Runtime kiểm artifact hashes/counts, current source-code hashes,15Data inputs với cache dùng chung, Rule config, cross-bundle Rule dependency, M2catalog/approval/exact ID sets/review report. Thay pin nghĩa là thay trust input, phải review lại; không tự cập nhật pin khi upstream thay đổi. Union kiểm namespace/type/layer/duplicate/conflict/edge endpoints/property references/IS_A cycles và false temporal claims cả node lẫn edge. M1–M3 source/tests/catalog/artifacts không sửa.

Candidate/reject/queue giữ source record counts và upstream attribution; identical diagnostic copies được loại một bản và đếm copies_removed, conflict thì fail. Queue là overlay, không cộng lại vào tổng source exclusions. Không đồng nhất hai record thuộc các bảng khác nhau chỉ vì có vẻ mô tả cùng quan hệ pháp lý.7.859keyword associations vẫn candidate; source relation/citation/temporal uncertainty giữ nguyên.

Tệp mới: `src/legal_graph/integration.py`, `scripts/build_integrated_graph.py`, `scripts/query_integrated_graph.py`, config, `tests/test_integration.py`. Checkpoint `outputs/integrated_graph/` gồm nodes/edges/manifest/quality_report/coverage_report/provenance/traversal_examples/candidates/rejects/review_queue. Manifest liên kết các upstream snapshots/source/input hashes; provenance index giữ nguồn từng graph record. Code tạo traversal nằm trong integration.py được hash; query script chỉ đọc graph hiện có, không là dependency tạo artifact.

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/build_integrated_graph.py
python -B scripts/build_integrated_graph.py --output outputs/integrated_graph_rerun
python -B scripts/query_integrated_graph.py --concept fixed_term_labor_contract
```

Query thực: `ontology:concept:fixed_term_labor_contract` → IS_A → `ontology:concept:labor_contract` → REGULATED_BY → `rule:provision:prov_c6b64b7574aec2bb` → CONTAINS(reverse) → `rule:provision:prov_ac3195a5489c40d5` → CONTAINS(reverse) → `rule:document:doc_d98ede4425ed3133`. Đây là taxonomy/định nghĩa và hierarchy, không bằng chứng luật áp dụng cho Case.

**77tests** (68trước+9M4); stale manifests/artifacts/current source/Data/config/catalog/approval/report, duplicates/wrong layer/endpoints/property refs, false temporal claims/unapproved concepts, no Case keyword promotion, dedup accounting và LF/two builds. Kết quả/hash/count diagnostics ở `VALIDATION.txt`. Runtime PASS_WITH_SOURCE_LIMITATIONS không thay verdict độc lập; đang chờ graph_reviewer. Sau PASS mới commit/push M4 và làm M5 final export/URL audit, không mở API/frontend/model.
