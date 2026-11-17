# Milestone 0 — kiểm kê dữ liệu và đề xuất schema

Ngày thực hiện: 17/11/2026. Phạm vi hoàn thành của builder: đọc đầy đủ `AGENTS.md`, `docs/GRAPH_CONTRACT.md`, cấu hình vai trò; kiểm tra repo/dữ liệu thực; nghiên cứu source baseline; đề xuất schema và kế hoạch gate/test. **Chưa dựng ba tầng graph, chưa có graph export hoàn chỉnh.** Verdict kiểm tra độc lập do graph_reviewer cung cấp riêng, builder không tự chứng nhận.

## Tệp tạo mới

- `scripts/inventory_graph_inputs.py`: kiểm kê chỉ đọc, profile keys/types/missing/null/status toàn bộ JSONL hiện có; hashes mọi file Data; join/endpoint/policy/span audit; so sánh ZIP bằng streaming, không giải nén.
- `tests/test_inventory_graph_inputs.py`: 12 test cho công cụ kiểm kê.
- `outputs/milestone_0/inventory.json`: kết quả máy đọc được, hash input, số liệu/từng finding (không phải graph output).
- `docs/milestone_0/BASELINE_XMU.md`: hành vi baseline có link chính xác tới 5 source files, giới hạn revision.
- `docs/milestone_0/SCHEMA_PROPOSAL.md`: node/edge endpoint matrix, IDs, evidence, temporal, policy, candidate/reject và deterministic handoff.
- `docs/milestone_0/REPORT.md`: báo cáo này; `VALIDATION.txt`: bằng chứng lệnh kiểm tra; `REVIEW.md` sẽ chỉ ghi kết quả reviewer thực nhận.

Không thay `AGENTS.md`, `docs/GRAPH_CONTRACT.md`, `.codex/`, `README_SETUP.md` hoặc `Data/`. Trước tác vụ các file hướng dẫn/config và ZIP đã là untracked; không coi đó là thay đổi của builder. Repo trước M0 chưa có source Python/test/pyproject; môi trường chạy thật Python 3.13.12, chưa kiểm chứng Python 3.11.

## Kiểm kê thực so với tài liệu cũ

| Tập | Số thực tại workspace | Nhận định |
|---|---:|---|
| Toàn Data | 219 file, 484.057.860 byte | Gồm ZIP 180.081.453 byte và Detail.data.md. Không khớp snapshot 421 file/374.977.620 byte mô tả trong Detail.data.md. |
| Nội dung ZIP | 217 file, 303.849.988 byte giải nén | Cả 217 đều có local và cùng SHA-256; không cần giải nén; không thiếu/khác file nào so với ZIP. |
| JSONL / PDF / DOCX / PNG | 30 / 84 / 5 / 96 | Các extraction_review, legacy_quality_reports, legacy_review_queues được tài liệu cũ nhắc không có đầy đủ ở cây thực tại. Không sử dụng báo cáo PASS lịch sử. |
| Metadata / processed documents | 107 / 107 | Metadata 39 ACTIVE, 68 QUARANTINE; 84 local source paths tồn tại, 23 không có path; không bịa path. |
| Provisions / quarantined records | 18.871 / 896 | Hai file riêng, ID overlap=0; quarantine có 553 ID khác nhau, 282 ID bị lặp, 343 extra records. Tất cả 896 bị loại nguyên trạng. |
| Cấp provision | 3.359 ARTICLE / 10.033 CLAUSE / 5.479 POINT | Parent FK về Document hoặc Provision; không thiếu endpoint, không cross-document parent theo check hiện có. |
| Headings | 562 | 311 Chapter, 251 Section; key `id`/`label`, không có parent_id; schema không giả định trường level/heading_id. |
| Identities / versions / spans | 15.651 / 18.871 / 18.871 | Joins cần thiết không thiếu; 18.871 provision và version có raw ID giống nhau nên phải dùng namespace riêng. |
| Cases | 36 | 24 ACTIVE và 12 QUARANTINE; không phải 24 reviewed fact extractions. |
| Issues / issue edges | 17 / 7.859 | Keyword association có evidence ≠ ontology axiom; candidate-only khi chưa có semantic review. |
| Accepted relations / citations | 2.029 / 4.371 | Accepted relations không thiếu endpoint trong registry hiện tại (số 17 lịch sử không áp dụng); citations có 2.313 unresolved target. |
| Legal changes | 25 | 17 AMEND, 7 REPEAL, 1 REPLACE; 11 target RESOLVED/14 UNRESOLVED; temporal UNKNOWN toàn bộ. |

`inventory.json` chứa profile field presence, null counts và types của từng JSONL, không hardcode số liệu lịch sử. Dataset digest từ relative paths + size + SHA-256 tất cả file: `30ebe107f6a48803e32769f788f1982662d8000e55a343fe01dd768e0db8a79e`. Snapshot/hash trước và sau các lần kiểm tra giống nhau; `git diff -- Data` không có thay đổi tracked data. Hash không chứng minh nguồn pháp lý đúng, chỉ chứng minh input bất biến trong tác vụ.

## Các gate thực sự giới hạn graph

Policy screen cho phép tối đa 39 Document nodes: 24 judicial identity/source-only, 10 labor legal sources, 1 procedural metadata reference, 1 vocational reference và 3 supplementary references. Chỉ 10 document có `allow_provision_hierarchy=true`.

Phân hoạch 18.871 provisions theo lý do loại trừ đầu tiên (không đếm chồng): **4.067** qua policy screen; **12.019** bị chặn bởi document quarantine/ineligible; **2.785** có document ACTIVE nhưng hierarchy denied. Tổng=18.871. Tập quarantine riêng 896 record bị chặn bổ sung, không cộng vào 18.871. Trạng thái ACTIVE/URL VERIFIED không đủ để mở hierarchy cho toàn corpus.

Literal span audit: 18.225 provision text bằng đúng segment slice; 646 TEXT_MISMATCH, gồm **111 trong 4.067** qua policy screen. 38/646 có excluded_annotation_spans; chưa kiểm chứng đầy đủ transformation nên không tự kết luận lỗi văn bản hay tự sửa nguồn. Các ID được liệt kê trong `provision_slice_findings`. 3.956 policy-eligible exact slices vẫn chưa là số publish cuối vì còn gate parent closure/evidence/semantic. M1 phải xử lý mismatch bằng evidence/review hoặc để candidate, và báo child closure bị ảnh hưởng.

Literal evidence slice của accepted relations: 2.029/2.029 khớp; issue edges 7.859/7.859 khớp. Citations có 4.005 khớp, 366 thiếu coordinate_space được ghi unsupported, không suy đoạn còn thiếu. Các case evidence DOCUMENT_TEXT thiếu document_id trong span đã được join qua case.document_id, không bị báo sai là mất nguồn. Exact text chỉ xác minh vị trí, không xác minh ngữ nghĩa căn cứ.

Accepted relations có 569/2.029 cạnh mà cả hai endpoint vượt policy screen; 1.460 còn lại bị chặn endpoint policy. Issue edges 2.619/7.859 qua screen, 5.240 bị chặn. Citations 591/4.371 qua screen, 3.780 bị chặn/unresolved. Các nhóm này là **upper bound**, chưa qua review semantic, không được công bố thành cạnh trusted chỉ vì tên file accepted/provenance VERIFIED.

Tất cả 18.871 versions có temporal_status INHERITED_DOCUMENT/provision_temporal_verified=false. Metadata có 61 temporal_verified=true cũng không làm provision được verified. Tất cả 36 cases có case_extracted_facts_enabled=false; case sections gồm 24 LEGACY_UNREVIEWED và 12 UNRESOLVED_FULL_TEXT_PRESERVED. Fact v1 theo dữ liệu hiện có chỉ được bắt đầu bằng eligible Case nodes và báo fact extraction pending; không bịa Actors/Events/Assertions để làm đủ hình thức ba tầng.

Đường dẫn provenance/report cũ có thể trỏ tới file không tồn tại trong workspace. Không dùng URL/report path text như bằng chứng đã đọc nội dung hoặc như review approval mới. Chưa đánh giá đầy đủ page/image OCR và không tái kiểm tra website pháp luật; Milestone 0 không đưa kết luận pháp lý về hiệu lực hiện tại.

## Kiểm thử và tái lập

Chạy tại `D:\vn_labor_results\artifacts`:

```powershell
python -m unittest discover -s tests -v
python scripts/inventory_graph_inputs.py --root . --output outputs/milestone_0/inventory.json
python scripts/inventory_graph_inputs.py --root . --output outputs/milestone_0/inventory.rerun.json --compare outputs/milestone_0/inventory.json
Get-FileHash outputs/milestone_0/inventory.json, outputs/milestone_0/inventory.rerun.json -Algorithm SHA256
git diff --exit-code -- Data
```

Lần đầu dùng tempfile mặc định gặp lỗi ACL do Python 3.13 tạo thư mục mode 0700 trong Windows sandbox; test fixture đã đổi sang thư mục UUID thông thường trong workspace, cleanup chỉ khi resolved path nằm trong test workspace. Đây là lỗi môi trường test đã xử lý, không phải dữ liệu được bỏ qua. Lần cuối **12/12 tests OK**. Kiểm kê chạy thành công, rerun/hash comparison PASS; chi tiết ghi `VALIDATION.txt`. Các test này chỉ chứng minh hành vi công cụ M0, không chứng nhận graph builder chưa được triển khai.

## Đề nghị review và bước tiếp

Builder bàn giao để reviewer đọc-only: kiểm tra inventory thực, dataset hashes, baseline attribution/revision limitation, schema endpoint/semantic/temporal gates, command rerun và phạm vi M0. Các findings dữ liệu không bị che thành PASS cho khả năng publish graph. Sau verdict độc lập, ghi nguyên văn kết quả và sửa blocker nếu FAIL. Không tự bắt đầu M1 trong lượt người dùng chỉ yêu cầu M0.

Kết quả review độc lập đã nhận: **PASS_WITH_WARNINGS cho Milestone 0**, không có blocker P0/P1; xem nguyên văn tại [REVIEW.md](REVIEW.md). Hai cảnh báo P2 là newline Windows trong công cụ kiểm kê và index duplicate lấy dòng cuối khi audit joins (không làm sai screen của dataset hiện tại). Reviewer chạy lại 12/12 tests OK và xác nhận số liệu/hash. Đây là PASS cho kiểm kê và đề xuất schema M0, **chưa phải PASS graph runtime**; chưa triển khai M1. Các cảnh báo được ghi nhận để thực thi đúng khi triển khai exporter/builder sau này, không thay source/tests/schema trong bước lưu review này.

Bước chuẩn bị GitHub handoff tiếp theo được ghi tại [GITHUB_HANDOFF.md](GITHUB_HANDOFF.md): nhánh `feature/hier-graph`, pending commit/push và independent handoff review. Không thay dữ liệu nguồn, không sửa hai P2 trong M0; exact snapshot bao gồm ZIP cục bộ không upload nên tài liệu phân biệt rõ tái lập đầy đủ với kiểm tra 218 file Data đã track.
