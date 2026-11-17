# Bàn giao graph offline

Dataset cuối tại **outputs/final/**:10.655nodes/11.814edges, canonical UTF-8 JSONL+manifest/quality report/URL sidecar. Rule10.604nodes/11.802edges; Ontology27nodes/2edges; Fact24Case nodes/0edges; cross10REGULATED_BY là **STATUTORY_DEFINITION**, không luật áp dụng cho Case.10concept definitions và2IS_A đã được reviewer approve;17issues vẫn source vocabulary.

Trạng thái nghiệm thu: **ACCEPTED_WITH_LIMITATIONS_FOR_OFFLINE_HANDOFF** theo review đọc mã nguồn/artifact GitHub tại `docs/milestone_5/REVIEW.md`. Đây **không phải** lần chạy lại độc lập toàn bộ 88 tests hay xác minh hiệu lực pháp luật.36case records chỉ24đủ policy để tạo identity nodes; extraction disabled và legacy sections chưa review nên0Actor/Event/FactAssertion.111eligible text/span mismatches và22descendants bị chặn;896quarantine records không được promote.11.223candidate source records và46.865reject/excluded records vẫn có reason/provenance.147queue records là overlay, không cộng thêm vào exclusions. Temporal inherited/unknown được giữ; không verified applicability claims.

Đọc `manifest.json` để biết input/code/config/review hashes, counts, tests và limitations; `nodes.jsonl`/`edges.jsonl` là canonical graph; `provenance.jsonl`, candidates/rejects/review_queue, coverage và traversal examples được giữ từ M4. Qualified property references và edge endpoints đã kiểm tra toàn graph. Online teammate chỉ cần tiêu thụ dữ liệu này; không API/frontend/embeddings/RAG implementation trong repo.

`url_audit.jsonl` join bằng Document node ID, giữ original URL, observed final URL/redirects,HTTP/check timestamp,response SHA-256, bounded header proof và VERIFIED/UNRESOLVED/BLOCKED. Lượt audit ban đầu 39 URL: 39 HTTP 200, **3 VERIFIED/36 UNRESOLVED/0 BLOCKED**. Sau bốn chấp thuận định danh đã ghi trong `audit/url_identity_approvals_v1.json`, **bộ đầu ra cuối có 7 VERIFIED/32 UNRESOLVED/0 BLOCKED**.200không đủ định danh.8 header matches chưa đầy đủ được đưa vào `audit/url_identity_review_queue.jsonl` để duyệt; bốn trường hợp sau đó đã được chấp thuận, các trường hợp còn lại không được tự động nâng trạng thái, không coi hạn chế detector là dữ liệu bất biến.27records thiếu source identity review giữ UNRESOLVED tới khi có proof độc lập;1HTMLchưa được review. `resolved_url` chỉ xuất hiện khi VERIFIED. URL validity không là hiệu lực pháp luật; NOT_FETCHED_M1/M3 trong graph properties là quan sát lịch sử checkpoint, sidecar là audit mới.

Tái lập final từ snapshots đã pin, **không network hoặc pip**:

```powershell
python -B scripts/build_final_graph.py
python -B scripts/build_final_graph.py --output outputs/final_rerun
python -B scripts/query_integrated_graph.py --graph outputs/final --concept fixed_term_labor_contract
python -B -m unittest discover -s tests -v
```

Cần đúng source/input bytes, upstream checkpoints, cached audit/QA/test logs/config/review artifacts trong repo; mismatch hash phải dừng thay vì tự thay pin. ZIP180MB không commit và không bắt buộc để đọc hoặc rebuild final từ cached QA; proof cuối đã kiểm toàn219Datafiles, trong đó218tracked sources. Muốn chạy lại toàn QA với cùng snapshot219 cần ZIP gốc đúng hash; không tự zip lại rồi coi bytes tương đương. `scripts/validate_final_inputs.py` tạo QA proof mới và test log mới; đây là input release mới, cần repin/review, không phải bước của build deterministic từ cached proof.

Chỉ standalone collector optional có network: `scripts/collect_url_audit.py`,4workers,20s socket timeout,max20MB,redirect≤5,TLS verification mặc định. Đã dùng pypdf7.1.0 đọc tối đa2trang; dependency miễn phí cài tạm `.codex_tmp/url_audit_deps`, ignore Git. Có thể cài `python -m pip install --target .codex_tmp/url_audit_deps pypdf==7.1.0 --no-input`; final builder không import dependency này. Nếu audit mới, ghi output file mới và review/pin snapshot mới; không overwrite source Data, không biến homepage/search/HTML200thành proof.

Baseline pin tại `docs/BASELINE_PINNED.md`/`audit/baseline_snapshot_v1.json`; không claim byte-equivalent M0 historical snapshot hoặc port XMU criminal-law classes. Final review tại `docs/milestone_5/REVIEW.md` ghi rõ phạm vi static repository/artifact review và giới hạn không tái chạy toàn bộ pipeline; manifest không hash chính review đó để tránh vòng tự tham chiếu.
