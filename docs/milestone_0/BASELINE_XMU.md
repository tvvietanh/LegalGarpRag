# Baseline XMU — kiểm tra nguồn ở Milestone 0

Ngày đọc: 17/11/2026. Baseline nghiên cứu: [XMUDeepLIT/LegalGraphRAG](https://github.com/XMUDeepLIT/LegalGraphRAG). Đích dự án: [tvvietanh/LegalGarpRag](https://github.com/tvvietanh/LegalGarpRag). Các nhận định bên dưới dựa trên **mã nguồn từng file**, không suy từ tên ba tầng.

## Nguồn và giới hạn revision

Đã đọc qua web các raw URL nhánh `main` sau. Không chạy code, không gọi embedding/model. Trình duyệt trả bản cached khác thời điểm giữa directory listing và raw files: directory chỉ liệt kê `__init__.py`, `feature_graph.py`, `graph_db.py`, trong khi raw có thêm ba module tầng. Vì thế không gán tất cả nội dung này cho một commit đã xác minh.

Trang lịch sử cached hiển thị commit `a3c9c3070cadb72ec317d2ecc2cce99da4b37c57` (Add bibtex, 03/08/2026), nhưng trang commit và GitHub API không truy cập được qua web trong lần đọc; urllib trực tiếp bị mạng từ chối. **SHA của snapshot mã nguồn đã đọc: chưa xác minh**. Đây là giới hạn tái lập baseline, không phải giới hạn của kiểm kê local. Khi cần port code cụ thể, M1 phải pin SHA và đối chiếu lại file; M0 chỉ dùng so sánh cấu trúc.

## Đối chiếu theo file

| File / hàm nguồn đã đọc | Hành vi quan sát | Quyết định cho dự án Việt Nam |
|---|---|---|
| [`core/graph_construct/feature_graph.py`](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/feature_graph.py), `construct_hierargraph`, dòng 23–52 | Khởi tạo graph chung; nhận nhóm `case`, `law`, `crime`; tạo embedding rồi lưu node, kNN và cộng đồng. File cũng có retrieval. | Kế thừa ý tưởng liên kết tầng trong graph chung. Runtime offline v1 không cần embedding, model hoặc retrieval. |
| [`core/graph_construct/graph_db.py`](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/graph_db.py), `InMemoryGraphDB.__init__`, `add_node`, `add_edge`, `save`, dòng 19–35, 67–99, 203–213 | NetworkX MultiDiGraph và kho properties riêng; node type Cases/Laws/Crimes/Cluster; thêm cạnh trực tiếp; lưu pickle. | Dùng hợp đồng node/edge có namespace và validate endpoint trước publish. JSONL là canonical export; không phụ thuộc pickle/DB. |
| [`core/graph_construct/fact_graph.py`](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/fact_graph.py), `store_nodes`, `build_relationships`, dòng 18–141 | Lưu Cases/Laws/Crimes; Case→Law bằng `entry` (`RELATES_TO_LAW`); Law→Crime theo description exact/fuzzy (`RELATED_CRIME`). Hàm còn xóa Laws có entry≤101. | Không chuyển tội danh thành concept lao động; không fuzzy-match để khẳng định căn cứ; không áp dụng điều kiện xóa theo số điều. Fact Việt Nam cần Case và assertion có người phát biểu/trạng thái chứng cứ. |
| [`core/graph_construct/ontology_graph.py`](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/ontology_graph.py), `run_knn`, `build_communities`, dòng 69–200 | Thêm Case→Case `SIMILAR_TO` theo cosine top-k; phát hiện cộng đồng, PageRank/degree; model tóm tắt thành Cluster, nối `BELONGS_TO`. | Cộng đồng/độ tương đồng không chứng minh `IS_A`. Ontology Việt Nam là vocabulary issue và concept được tuyển chọn, định nghĩa và duyệt. Không dựng taxonomy từ kNN. |
| [`core/graph_construct/rule_graph.py`](https://raw.githubusercontent.com/XMUDeepLIT/LegalGraphRAG/main/core/graph_construct/rule_graph.py), `law_node_properties`, `update_insights_in_graph`, dòng 8–33 | Rule layer là fields trên Laws: `entry`, description, crimes, `judge_dep`, `related_laws`, insights; có cập nhật insights. | Không xem checklist/insight sinh tự động là quy phạm. Rule Việt Nam bắt đầu từ Document/Provision/Identity/Version, hierarchy và bằng chứng quan hệ; checklist chỉ là nghiên cứu chờ duyệt. |

Đây là diễn giải mã nguồn, không tuyên bố dự án XMU cung cấp ontology hình thức hoặc mô hình hiệu lực điều khoản tương đương yêu cầu hiện tại. Không sao chép module XMU vào repo. Phần online của baseline không thuộc phạm vi triển khai.

## Local repository so với baseline

Local HEAD `019949659cd6f5d4bfdd2608b3506e9282a9b390` (Data Legal). Trước M0 không có package Python/pyproject/test hay graph builder trong cây source được kiểm tra; có Data và gói cấu hình hai agent/tài liệu. Trang remote dự án được đọc chỉ liệt kê Data ở root; không dùng remote để ghi đè local. Các báo cáo pipeline cũ được nhắc trong `Data/Detail.data.md` không phải code hiện có hay chứng chỉ cho lần build mới.
