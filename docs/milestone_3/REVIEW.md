# M3 — tóm tắt review độc lập

**VERDICT = PASS_WITH_SOURCE_LIMITATIONS, không P0/P1.** Parent chuyển kết quả graph_reviewer read-only; reviewer không chỉnh code/dữ liệu.

Reviewer xác nhận68tests OK,7artifacts hai build khớp byte/LF/hashes.36source cases →24Case nodes,12excluded,36review queue,0edges; không Actor/Event/FactAssertion hoặc legacy court/date/facts được nhập thành trusted claims.24full-text hash/offset references đúng nguồn. Ngay cả flags enabled trong fixture vẫn cần reviewed extraction artifact, không tự sinh facts. Data/M1/M2 giữ nguyên.

Build `build:f322efb9003b73ebe1212e843dcb6084e2b74e61067a87a0b8ba6cc3a85c4e1c`; manifest SHA-256 `2ee5da45303e76f2ad8b0f662378f02d92695310e2ecd5acd12eae3d46628ede`.

Giới hạn nguồn: fact extraction pending, source flags disabled và legacy sections chưa review. PASS này chấp nhận Case-level graph trung thực, không xác nhận allegation/finding/decision hoặc hoàn tất semantic fact extraction. Bước tiếp theo M4 tích hợp các bundle đã review.
