# M3 — Case-level Fact Graph, chờ review

Trạng thái cuối: reviewer độc lập **PASS_WITH_SOURCE_LIMITATIONS**, không P0/P1; xem [REVIEW.md](REVIEW.md). Các mô tả chờ review bên dưới là mốc trước verdict. Chuẩn bị commit/push M3 và tiếp M4 tự động.

Đã dựng **24 Case nodes,0 edges**, từ36case records thực.12cases bị loại theo policy;36records có review queue. Không Actor/Event/FactAssertion, không chuyển allegation thành finding hoặc quyết định. Đây là kết quả **PASS_WITH_SOURCE_LIMITATIONS của validator nội bộ**, chưa có verdict độc lập M3.

Case và metadata đều phải ACTIVE/eligible với allow/allow_document_and_source_nodes=true; missing/false/coerced bool deny. Metadata phải là JUDICIAL và qualified Document endpoint đã publish trong M1. Cases/metadata hashes phải khớp đúng M1 input snapshot. Original case IDs được namespace `fact:case:`; external document references có manifest dependency và Rule node hash.

Tất cả36case_extracted_facts_enabled=false; source sections gồm24LEGACY_UNREVIEWED và12UNRESOLVED_FULL_TEXT_PRESERVED. Vì thế graph chỉ giữ source identity observations, provenance và full-text hash/span references. Không copy facts/reasoning/decision/features/court/decision_date từ legacy fields vào trusted Case properties. Court/date review và temporal applicability vẫn UNVERIFIED; title/case_number chỉ source identity observations, không dùng để suy facts. Ngay cả flags=true trong fixture, thiếu reviewed extraction artifact vẫn không sinh assertions.

Tệp: `src/legal_graph/fact_graph.py`, `scripts/build_fact_graph.py`, `tests/test_fact_graph.py`; outputs `outputs/fact_graph/{nodes.jsonl,edges.jsonl,manifest.json,quality_report.json,candidates.jsonl,rejects.jsonl,review_queue.jsonl}`. Candidates/edges trống là kết quả có chủ đích;24identity nodes và36workflow queue records là artifact thật, không phải hứa triển khai extraction. Queue không chứa invented facts;12excluded có reason/provenance riêng.

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/build_fact_graph.py
python -B scripts/build_fact_graph.py --output outputs/fact_graph_rerun
```

**68tests** gồm57trước+11M3; logs và artifact SHA-256 ở `VALIDATION.txt`. M3 tests kiểm quarantine/deny flags/source group, legacy fields bị chặn, enabled flags không bypass review, duplicate/stale inputs, missing Rule Document refs, fulltext references, LF/two builds và Data immutability. M1/M2 code/catalog/outputs giữ nguyên. Data consumed hashes khớp M0/M1; không network/API/frontend hoặc source writes.

Sau reviewer PASS, commit/push M3 rồi tiếp M4 union ba bundles và verified groundings M2. Không tự gắn Case→Concept/Provision chỉ từ title, keyword hoặc citation chưa review. Final delivery phải công khai Fact extraction pending thay vì coi Case identity nodes là facts đã được xét xử xác lập.
