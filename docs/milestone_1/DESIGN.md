# M1 — thiết kế runtime Rule Graph

Phạm vi: triển khai [Issue #2](https://github.com/tvvietanh/LegalGarpRag/issues/2) từ schema M0 đã review; chỉ Rule Graph offline. Không xây Ontology/Fact/API/frontend; `cases.jsonl` chỉ là registry để giữ nguồn viện dẫn và định vị DOCUMENT_TEXT, không tạo Case hoặc assertion. Không gọi mạng/model. Tài liệu này mô tả hành vi đã triển khai, không nâng trạng thái pháp lý của nguồn.

## Mô hình và gate

Runtime: `src/legal_graph/rule_graph.py`; CLI: `scripts/build_rule_graph.py`; cấu hình cố định: `configs/rule_graph_v1.json`. Chỉ dùng Python standard library. Config có thể được đọc từ file khác nhưng nội dung canonical phải đúng cấu hình v1; không cho override để tắt review hoặc bật verified temporal claims. So sánh cấu hình giữ phân biệt JSON bool và số.

Node envelopes/type/layer giữ schema M0: Document, Provision, ProvisionIdentity, ProvisionVersion; layer `rule`. Stable IDs `rule:<kind>:<percent-encoded original ID>`; Provision và Version có raw ID giống nhau dùng namespace khác nhau. Không thay ID đầu vào. `CONTAINS`, `HAS_IDENTITY`, `HAS_VERSION` dùng FK thật và provenance. Legal relations chỉ dùng allow-list endpoint M0: CITES/REFERENCES gồm Document→Document, Provision→Provision/Document; AMENDS/REPEALS/REPLACES gồm Document→Document hoặc Provision→ProvisionIdentity. Case endpoints giữ candidate ngoài M1. Không dựng LegalRule từ checklist, không thêm Chapter/Section node từ nhãn bố cục.

Document phải ACTIVE, graph_eligible=true và cả policy.allow/allow_document_and_source_nodes=true. Missing/false/khác kiểu đều deny. Provision cần document đã publish, hierarchy flag true, không trùng bất kỳ ID ở file quarantine; cấp ARTICLE/CLAUSE/POINT đúng; literal span đúng owner/bounds/text; `provision_spans` nhất quán; provenance RESOLVED; identity/version/document/instrument joins đúng. Root Article phải parent là đúng document; Clause parent Article, Point parent Clause, cùng document. Self-loop/cycle/orphan/wrong type bị chặn. Chain resolution không phụ thuộc thứ tự record, không dựa vào recursion Python; con của bất kỳ cha bị chặn cũng không được publish.

Tập trusted index từ chối cả duplicate ID giống hệt và conflicting duplicate trước export; không lấy dòng cuối. Raw endpoint ID collision giữa Document/Provision/Identity/Case cũng fail. Version raw ID chỉ được trùng đúng Provision mà FK version của nó chỉ về ID đó; reuse một version cho nhiều provision bị fail. Riêng quarantine luôn excluded: duplicate nguồn vẫn được đếm theo occurrences và distinct IDs, group theo source record hash để ghi disposition ổn định; grouping không phải promotion hoặc dedupe mất số liệu.

111 policy-eligible literal mismatch được ghi đủ vào `provision_review_queue.jsonl`, giữ text/span gốc, SHA-256 và hướng dẫn review. Không tự sửa cleaning/annotation; mọi child closure phụ thuộc cha bị chặn cũng bị loại. Queue là một view phục vụ review của các record đã được tính trong excluded partitions; không cộng queue vào tổng excluded lần nữa.

## Provenance, property references và temporal

Mỗi node/edge có source path tương đối với Data, file SHA-256, source record ID, canonical record SHA-256, provenance list và verification dimensions tách structural/literal/semantic/temporal. Node giữ source_properties gốc; cạnh FK chỉ giữ material IDs/FKs/span/temporal source fields và immutable references, tránh lặp toàn văn đã giữ ở Provision node. Evidence references giữ span, source document/provision/version IDs, method/confidence/status khi thật sự có trong nguồn. Không dùng timestamp runtime hoặc absolute machine path trong graph artifacts.

Qualified property references `document_node_id`, `parent_node_id`, `identity_node_id`, `version_node_id` đều được validate tồn tại, đúng type và join nhất quán; không chỉ kiểm edge endpoints. Source-properties/provenance IDs là locator của dữ liệu đầu vào, không phải tuyên bố có node cho mọi record nguồn. Mọi published provision có đúng một CONTAINS parent và identity/version closure; các identity/version ngoài closure được tính excluded riêng.

Temporal fields gốc nằm trong source_properties và temporal.source. Assessment runtime luôn chưa xác minh: INHERITED_UNVERIFIED cho source INHERITED_DOCUMENT, UNKNOWN cho identity/nguồn không đủ, DOCUMENT_SOURCE_UNREVIEWED cho metadata. Mọi node/edge `verified_applicability=false`. Metadata temporal_verified=true hoặc source date/status không trở thành xác nhận hiệu lực theo provision. M1 không dùng dates để chọn luật áp dụng, không suy interval mới và không auto-close version từ thay đổi pháp lý.

URL chỉ strip whitespace vào trường normalized, giữ nguyên original và source_properties; access_status=NOT_FETCHED_M1. Các cờ URL VERIFIED kế thừa vẫn là quan sát nguồn; M1 không fetch, không đổi URL hoặc khẳng định URL hiện đọc được. Audit URL thuộc master Issue #1.

## Review catalog cho legal relations

Sau repair P1-02, mọi supplied SEGMENT_TEXT và DOCUMENT_TEXT đều phải cắt đúng provision text với owner/bounds hợp lệ; legacy char aliases phải nhất quán. Published Provision ghi coordinate_verification, validator chặn supplied space chưa verified. Legal evidence còn kiểm source bounds thật trước khi dùng làm phạm vi, không suy document bounds từ việc segment slice khớp.

Sau repair P1-01, catalog bắt buộc `dependency_snapshots`: sorted hash-only references (source_path, source_record_id, source_record_sha256, source_sha256) cho source/target, ancestor provisions, identity/version/span/segment, metadata và processed document context liên quan. Thiếu hoặc bất kỳ dependency đổi cùng ID đều làm review stale. File hashes bảo thủ: thay đổi row khác trong cùng file cũng cần re-review. Published legal edge giữ dependency snapshots để downstream kiểm tra; không lặp toàn văn vào catalog.

Accepted filename, confidence, evidence_status=RESOLVED hoặc exact slice không đủ chứng minh legal semantics. Mặc định không có explicit review catalog, nên **0 legal relations** được publish. Accepted relations/citations/legal changes đều có accounting và candidate/reject, không bị bỏ qua âm thầm.

Tùy chọn `--review-catalog <JSONL>` chỉ dành cho hồ sơ review thật; không có catalog thật nào được tạo để làm tăng coverage trong M1. Mỗi review phải có review_id riêng, source_path/source_record_id, source_record_sha256, source_input_sha256, raw source_id/target_id, relation_type, decision=APPROVED, reviewer, reviewed_at, evidence_verified=true, semantic_verified=true, target_resolution_verified=true. Khớp hash cả file/record ràng buộc chính evidence text/span và target/direction của source row; mismatch/stale/coerced bool bị chặn. AMENDS/REPEALS/REPLACES còn cần operation_verified/scope_verified/direction_verified/temporal_verified=true. Một review không được override policy, endpoint, evidence hoặc hierarchy gate.

Literal evidence phải thuộc đúng source document và nằm trong phạm vi source Provision khi source là Provision. SEGMENT_TEXT dùng segment_id; DOCUMENT_TEXT của case join source case→document→processed text. Citations/changes phải resolve duy nhất (`candidate_count=1`, RESOLVED). Không tự đổi target Provision của AMENDS thành Identity: endpoint schema sai phải reject hoặc chờ review/mapping riêng về sau. Self-loop legal relation không publish. Hoạt động sửa đổi được review cũng không tạo verified date applicability trong M1.

Các review records trong tests đều ghi nhãn SYNTHETIC_TEST_ONLY, chỉ chứng minh gate positive/negative, không có mặt trong graph thực.

## Export và tính tái lập

`outputs/rule_graph/` là checkpoint riêng M1 theo Issue #2; không thay `outputs/graph_v1/`/final của các milestone sau. File nodes/edges/rejects/candidates/provision_review_queue JSONL; manifest và quality_report JSON. UTF-8, ensure_ascii=false, sort_keys=true, compact canonical JSON, LF end-of-line, sort record theo ID; binary writes tránh newline translation Windows. `.gitattributes` giữ bytes artifacts, M1 source/config trên các checkout; không đổi attributes Data/M0.

Manifest chứa schema/config/source-code/input/review hashes, build_id, counts/types/layers, complete primary-reason accounting và output hashes. Input hashes được đọc lại trước export. Runtime không ghi vào Data. Nếu input/config/ID sai, exit 1 trước export; output cũ có thể còn nguyên và không phải kết quả của lần FAIL. Chỉ tin manifest/checks cùng exit code và hashes của run thành công. Artifact files được ghi qua temporary replacement; manifest được ghi cuối làm dấu bundle hoàn tất, không tuyên bố transaction toàn thư mục.

Cùng actual input/config/code/review bytes → cùng toàn bộ output bytes/build_id. Đảo thứ tự iteration trong memory nhưng giữ file bytes cũng không đổi output. Nếu **sửa thứ tự vật lý JSONL**, hash file/provenance/manifest thay đổi một cách trung thực; namespace IDs/edge identity/topology vẫn ổn định. Không thể vừa lưu SHA-256 input thật vừa tuyên bố output provenance byte-identical sau khi bytes nguồn thay đổi. Tests kiểm cả hai trường hợp này, tách rõ invariant; đây là chi tiết hóa test shuffle trong đề xuất M0.

M0 P2 được xử lý trong runtime M1 bằng binary LF và unique typed index fail-closed; công cụ M0 và review lịch sử không bị sửa. Không port code/hành vi cụ thể từ XMU; chỉ dùng baseline kiến trúc đã ghi nguồn ở M0. Việc pin revision/snapshot XMU vẫn là việc chưa hoàn tất trong master #1 khi cần attribution/port cụ thể, không được tuyên bố đã pin trong M1.
