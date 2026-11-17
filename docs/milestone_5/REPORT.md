# M5 draft — QA/export/URL sidecar

Final graph giữ nguyên byte nodes/edges từ M4:10.655/11.814. `outputs/final/` có5file bắt buộc và toàn bộ diagnostics/provenance/coverage/traversals. `final_release.py` chỉ đọc pinned integration/audit/QA/review/baseline; không network. Manifest/quality có layer/type counts,source dispositions/quarantine/candidates,temporal limits,test results,reproduction. Final reviewer report tách ngoài hash để tránh circularity.

Collector thật bounded39URLs một lần,TLS default verification,pypdf7.1.0 tối đa2trang:39HTTP200,3VERIFIED/36UNRESOLVED.3verified đòi exact trusted local bytes,reviewed source metadata vàfresh header number/title/authority.8header-incomplete rows có queue để reviewer xem proof/aliases;27source identity metadata chưa independent review và1HTML chưa đủ proof. Không tự broaden matcher hoặcpromote case facts. Optional manual URL identity approval đã có mocktests ràng buộc snapshot/doc/context/responsehash/quote/report; chưa có approval thật.

**86tests OK**, full219Data hashes khớp M0;QA/test log được freeze thành input có hash. Final two-build comparison vàallartifact checks tại `VALIDATION.txt`. QAproof code/test hashes ngăn dùng results cũ sau code change. M0–M4 source/catalog/artifacts giữ nguyên; chưa stage/commit M5 trước review.

Files mới chính: `src/legal_graph/{url_audit.py,final_release.py}`, `scripts/{collect_url_audit.py,build_final_graph.py,validate_final_inputs.py}`, `tests/test_final_release.py`, `configs/final_graph_v1.json`, `audit/`snapshots, `docs/HANDOFF.md`, `FINAL_CHECKLIST.md`, `BASELINE_PINNED.md`. Pin upstream review/test/report files giữLF để Git checkout không phá hashes. Collector dependency tạm ignore Git, không thuộc offline final runtime.
