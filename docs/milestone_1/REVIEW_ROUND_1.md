# M1 — review độc lập vòng 1

**VERDICT = FAIL**, 2 P1; không được commit/push hoặc chuyển M2 trước khi sửa và re-review. Đây là tóm tắt findings do parent chuyển từ graph_reviewer read-only, không phải builder tự đánh giá.

- **P1-01 — review stale theo endpoint/context.** `review_check` trước sửa chỉ bind relation row/file và source/target IDs. Repro: fixture p1→p2 REFERENCES đã reviewed; đổi p2.text từ bc→ab và tọa độ/span hợp lệ 0:2, giữ ID/relation/review; cạnh vẫn semantic VERIFIED. Cần snapshot hash endpoint và evidence/context dependencies, không coi ID không đổi là nội dung không đổi.
- **P1-02 — document coordinates chưa xác minh.** Provision SEGMENT_TEXT chỉ được kiểm ở segment nhưng document offsets sau đó được dùng làm giới hạn legal evidence. Repro: p2=bc ở segment1:3, đổi document offsets của provision/span thành0:2 (ab), relation DOCUMENT_TEXT0:1=a vẫn có thể literal/semantic VERIFIED. Cần kiểm mọi supplied coordinate space và không dùng source bounds chưa verified.

Reviewer vòng 1 xác nhận 40 tests OK, 7 artifacts hai run giống byte, 10.604 nodes/11.802 edges, queue111/closure22, toàn bộ219 Data hashes bất biến. Những kết quả đó không xóa hai implementation blockers trên.

## Repair attempt 1 — chờ xác minh độc lập

P1-01: catalog bắt buộc `dependency_snapshots` gồm hash file/record của source/target, ancestor provisions, identity/version/span/segment và metadata/processed document liên quan. Thiếu/stale giữ candidate; review không override endpoint/evidence gates. Hash-only snapshots giữ deterministic order, không lặp toàn văn. File hash cố ý bảo thủ: sửa row khác trong cùng file cũng làm review stale.

P1-02: mọi supplied SEGMENT_TEXT/DOCUMENT_TEXT phải cắt đúng text của provision, đúng owner/bounds; legacy char aliases phải nhất quán. Published nodes ghi coordinate_verification; validator chặn supplied space chưa verified. Legal evidence còn kiểm lại source bounds thực cắt đúng source provision, kể cả khi source chưa qua publication gate.

Sáu regression tests bổ sung tái hiện hai repro, missing dependencies, đổi source/target/context cùngID có positive control trước đổi, hai coordinate spaces và aliases. Tổng46 tests (34M1+12M0). Kết quả chạy cuối, source-code/output hashes và Data immutability ở `VALIDATION.txt`; **reviewer chưa xác nhận repairs tại thời điểm lưu bản này**.
