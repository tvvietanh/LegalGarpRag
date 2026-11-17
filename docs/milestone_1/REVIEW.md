# M1 — tóm tắt re-review độc lập

**VERDICT = PASS cho M1 sau repair attempt 1. Không còn P0/P1.** Đây là bản tóm tắt kết quả graph_reviewer do parent chuyển lại; reviewer read-only, không sửa code/dữ liệu hoặc tự triển khai repairs.

- Reviewer chạy **46/46 tests OK**.
- P1-01: positive control có 1 legal edge; đổi nội dung target cùng ID với review cũ → 0 legal edge, candidate có SEMANTIC_REVIEW_DEPENDENCIES_STALE. Endpoint/context snapshots được kiểm tra.
- P1-02: contradictory document coordinates bị chặn DOCUMENT_COORDINATE_TEXT_MISMATCH; exploit relation bị ENDPOINT_NOT_PUBLISHED và EVIDENCE_UNVERIFIED_SOURCE_COORDINATES, không còn literal/semantic VERIFIED sai.
- Cả 7 artifacts hai run giống byte, UTF-8 LF; artifact hashes và source-code hashes khớp manifest.
- Corpus thực: **10.604 nodes / 11.802 structural edges**, queue111, child closure22,0 legal relations và0 verified applicability claims; không có duplicate/dangling/invalid qualified references.
- Toàn bộ **219 Data file hashes giữ nguyên**; nguồn tracked không thay đổi.
- Build ID đã kiểm tra: `build:f71786db649ab02db090e6623d8aee314169bbc4eb62204125c464ee3961ac1a`.

Findings vòng1 vẫn được giữ tại [REVIEW_ROUND_1.md](REVIEW_ROUND_1.md) để lưu lịch sử FAIL và repair. PASS này chỉ cho Rule Graph M1; M2–M5, pin revision baseline và URL identity audit vẫn phải thực hiện theo checkpoint, không suy thành hoàn thành master #1.
