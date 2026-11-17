# Milestone 1 — Rule Graph offline

Trạng thái: **M1 PASS sau re-review độc lập repair attempt 1, không còn P0/P1**; xem [REVIEW.md](REVIEW.md). Chuẩn bị commit/push sau PASS tại thời điểm cập nhật báo cáo; log VALIDATION.txt giữ mốc chạy trước verdict. Đây là checkpoint Rule Graph; chưa phải hoàn thành cả ba tầng hoặc master Issue #1.

## Tệp triển khai và bàn giao

- `src/legal_graph/__init__.py`, `src/legal_graph/rule_graph.py`: runtime offline, strict input/index, policy/evidence/closure gates, typed graph validation, canonical export.
- `scripts/build_rule_graph.py`: CLI stdlib; `configs/rule_graph_v1.json`: cấu hình v1 không cho tắt trust gates.
- `tests/test_rule_graph.py`: 34 test M1 dùng fixture tổng hợp có nhãn, không phải legal evidence.
- `.gitignore`: thêm scratch/rerun M1; `.gitattributes`: giữ LF bytes của artifacts và M1 code/config, không đổi Data.
- `outputs/rule_graph/{nodes.jsonl,edges.jsonl,manifest.json,quality_report.json,rejects.jsonl,candidates.jsonl,provision_review_queue.jsonl}`.
- `docs/milestone_1/DESIGN.md`, `REPORT.md`, `VALIDATION.txt`: thiết kế thực thi, số liệu và bằng chứng chạy. Review report chỉ được ghi sau khi thực nhận verdict.

Không chỉnh Data, ID gốc, source text, M0 schema/source/tests hoặc báo cáo lịch sử. Chỉ stage/commit gói M1 sau khi reviewer đã PASS; không đưa Data/scratch/rerun vào commit.

## Kết quả trên dữ liệu thực

| Node/edge type | Số publish |
|---|---:|
| Document | 39 |
| Provision | 3.934 |
| ProvisionIdentity | 2.697 |
| ProvisionVersion | 3.934 |
| **Tổng nodes** | **10.604** |
| CONTAINS | 3.934 |
| HAS_IDENTITY | 3.934 |
| HAS_VERSION | 3.934 |
| **Tổng edges** | **11.802** |
| Extracted legal relations / verified applicability claims | **0 / 0** |

39 Document nodes gồm các hồ sơ được policy cho dùng identity/source metadata; không đồng nghĩa 39 văn bản đều cho phép provision hierarchy. Chỉ 10 Document có hierarchy flag true. Không có Case/Concept/Issue hoặc FactAssertion trong output M1.

Phân hoạch đầy đủ **18.871 provisions**, lý do đầu tiên không đếm chồng:

| Kết quả / primary reason | Records |
|---|---:|
| Publish | 3.934 |
| DOCUMENT_NOT_PUBLISHED | 12.019 |
| HIERARCHY_POLICY_DENIED | 2.785 |
| EVIDENCE_TEXT_MISMATCH | 111 |
| PARENT_NOT_PUBLISHED (child closure bổ sung) | 22 |
| **Tổng** | **18.871** |

Policy screen 4.067 = 3.956 literal exact + 111 mismatch. Chặn 111 mismatch và thêm 22 descendants → 3.934 publish. Queue có đúng 111 record, ID/evidence nguồn giữ nguyên; queue không cộng thêm vào excluded total. Các ID/root blocker có trong rejects và queue; không tự sửa cleaning/annotation để tăng coverage.

896 quarantine records nằm ở file riêng, không phải subset cộng lại của 18.871 provisions: tất cả excluded; 553 distinct IDs, 343 duplicate extra records được bảo toàn số đếm. 68/107 metadata bị loại DOCUMENT_NOT_ACTIVE. Identities outside closure: 12.954/15.651; versions outside closure: 14.937/18.871. Không xuất identity/version mồ côi để tăng node count.

| Nguồn quan hệ | Publish | Candidate | Reject | Primary reasons |
|---|---:|---:|---:|---|
| Accepted relations (2.029) | 0 | 507 | 1.522 | 1.516 endpoint not published; 6 wrong endpoint types; 6 Fact endpoint ngoài M1; 501 semantic review required |
| Citations (4.371) | 0 | 2.838 | 1.533 | 1.533 endpoint not published; 2.313 unresolved; 7 Fact endpoint ngoài M1; 17 unsupported coordinate space; 501 semantic review required |
| Legal changes (25) | 0 | 19 | 6 | 6 endpoint not published; 19 chưa có target identity đủ dùng (kể cả trường hợp source resolve ở cấp khác) |

Tổng candidate=3.364 records; rejected/excluded=46.853 records trên các nguồn node và relation được account. Không cộng các mức identity/version vào số provisions bị loại; đây là các bảng nguồn khác nhau. `primary_reasons` phân hoạch từng bảng; `overlapping_reason_labels` cho biết tất cả gate phát hiện và không được cộng thành tổng excluded. 0 legal relation được publish là hệ quả chưa có explicit semantic review catalog; việc accepted/evidence RESOLVED không trở thành approval mới.

## Chất lượng, thời gian và nguồn

Kiểm tra published graph: duplicate node/edge ID=0; dangling edge=0; missing qualified property references=0; endpoint type violations=0; hierarchy cycles=0; false verified applicability claims=0. Provision document/parent/identity/version property references đều được kiểm, không chỉ source/target edges.

7.868 published node assessments INHERITED_UNVERIFIED gồm Provision+Version; 2.697 Identity UNKNOWN; 39 Document DOCUMENT_SOURCE_UNREVIEWED. Những ngày/trạng thái/cờ kiểm chứng cũ được giữ như source properties, không thành khẳng định hiệu lực mới. URL chỉ normalized bằng strip, giữ original, NOT_FETCHED_M1; chưa giải quyết URL audit của master #1.

M1 dùng 13 JSONL input được hash trong manifest. Bằng chứng kiểm tra toàn bộ 219 Data files so với snapshot M0 và 218 tracked sources, Data diff=0, ghi ở VALIDATION.txt. ZIP cục bộ không upload và không phải dependency bắt buộc của runtime M1; manifest dùng các nguồn thực tiêu thụ, không giả vờ cần ZIP để build. Chưa pin XMU revision vì không port hành vi/code cụ thể; master #1 vẫn pending mục đó.

## Chạy và kiểm thử

Chạy từ repository root, Python 3.11+ standard library (đã thực thi Python 3.13.12; chưa chạy máy 3.11):

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/build_rule_graph.py --root . --output outputs/rule_graph
python -B scripts/build_rule_graph.py --root . --output outputs/rule_graph_rerun
git diff --exit-code -- Data
```

Sau đó so từng bytes/SHA-256 trong hai thư mục và artifact hashes với manifest; không chỉ so node count. Log thực tế, build_id và mọi output SHA-256 nằm `VALIDATION.txt`. Các artifacts canonical LF, không CRLF. File lớn nhất hiện dưới 50 MB/file, phù hợp giới hạn push GitHub; rerun/scratch được ignore.

**46/46 unit tests OK** gồm 12 M0 giữ nguyên và 34 M1: duplicate/conflict/raw-ID namespace collision, parent sau child, valid ARTICLE→CLAUSE→POINT, orphan/wrong endpoint/self-loop/cycle/cross-document parent, quarantine overlap, mismatch queue/parent closure, span bounds/owner/provenance, version join conflict, temporal no-false-verification, accepted-unreviewed candidate, positive explicit review, stale hash/coerced flag/missing attribution, wrong endpoint/out-of-source evidence dù review APPROVED, case source giữ ngoài M1, qualified property refs, URL no-fetch, LF/two builds/iteration shuffle, config bypass fail-closed và từ chối output trong Data. Fixture review chỉ dùng trong tests; không tự tạo review cho corpus thật.

## Bàn giao review

Review vòng 1 và repairs P1-01/P1-02 lưu ở [REVIEW_ROUND_1.md](REVIEW_ROUND_1.md); checkpoint tự động ở [PROGRESS.md](../PROGRESS.md). Reviewer đã xác nhận repairs và PASS tại [REVIEW.md](REVIEW.md); bước kế tiếp là M2 theo workflow tự động, sau bàn giao commit/push M1.

Đề nghị graph_reviewer kiểm tra độc lập source/config/tests, từng output/hash/count partition, queue 111, closure 22, provenance/typed refs và temporal honesty. Runtime `quality_report.validation_verdict=PASS` chỉ là kết quả validator nội bộ, không phải verdict độc lập. Nếu FAIL, builder sửa đúng blocker và reviewer kiểm lại trước commit/push/comment Issue #2. Không chuyển M2/M3 hoặc tuyên bố master #1 hoàn tất trong M1.
