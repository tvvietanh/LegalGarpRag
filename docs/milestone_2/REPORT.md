# M2 — Ontology Graph, catalog đã được review độc lập

Trạng thái cuối: **PASS M2** sau khi reviewer kiểm tra approved exports; xem [FINAL_REVIEW.md](FINAL_REVIEW.md). Các mô tả chờ quickcheck bên dưới lưu mốc trước xác minh cuối. Không sửa REVIEW.md gốc vì đã bind approval hash.

Bundle gồm **10 LegalConcept +17 LegalIssue**, **2 IS_A +10 REGULATED_BY**. Reviewer đã PASS thiết kế/implementation và approve exact catalog hash/10concept IDs/12edge IDs tại [REVIEW.md](REVIEW.md). Sau khi lưu quyết định thật vào `ontology/curation_approval_v1.json`, hai lần rebuild chuyển semantic release status thành **APPROVED**;10concepts và12edges semantic VERIFIED trong phạm vi định nghĩa đã review. Đang chờ reviewer kiểm tra nhanh approved exports trước commit; không khẳng định hiệu lực hiện tại.

Nguồn curated: các provision đã publish trong18/VBHN-VPQH, doc_d98ede4425ed3133: Điều3 khoản1/2/3/5/7/8/9; Điều13 khoản1; Điều20 khoản1 điểm a/b. Mười khái niệm: người lao động, người sử dụng lao động, tổ chức đại diện người lao động tại cơ sở, quan hệ lao động, cưỡng bức lao động, phân biệt đối xử, quấy rối tình dục tại nơi làm việc, hợp đồng lao động và2loại hợp đồng. Taxonomy chỉ2loại→hợp đồng lao động, evidence có khoản20.1 phân loại và điểm định nghĩa trực tiếp dưới khoản đó. Không suy thêm taxonomy từ keywords. Grounding có semantics STATUTORY_DEFINITION, không khẳng định hiệu lực hiện tại hoặc luật áp dụng cho vụ việc.

Catalog `ontology/curated_concepts_v1.json` chứa nguyên văn definitions, inclusion/exclusion boundaries, scope và exact quotes/offsets. Mọi evidence bind canonical Rule node SHA-256, source owner/record/file hashes và toàn M1 manifest hash; thiếu/stale/sai quote/owner/offset bị fail. Catalog hash draft: `696a2a3df89fd2e7c368d2def4730a8e8c28c7a57a2a6518cead4199a929a4b0`. M1 source/tests/artifacts giữ nguyên; M2 dùng module mới và tái sử dụng helper hẹp.

17 issues chỉ SOURCE_VOCABULARY, chưa có định nghĩa source đầy đủ. Toàn bộ **7.859 keyword associations** giữ candidate, không thành IS_A/REGULATED_BY. Mẫu hash-row grouping giữ record_count, không mất duplicate record. Coverage/evidence report ghi riêng proposed/accepted concept count,10definition-grounded provisions trên3.934Rule provisions và0keyword axioms.

Runtime `src/legal_graph/ontology_graph.py`, CLI `scripts/build_ontology_graph.py`, tests `tests/test_ontology_graph.py`. Outputs checkpoint: `outputs/ontology_graph/{nodes.jsonl,edges.jsonl,manifest.json,quality_report.json,coverage_report.json,evidence.jsonl,candidates.jsonl,rejects.jsonl}`. 10cross grounding edges khai báo Rule external dependencies và11external evidence/endpoint nodes; validator giải endpoint với M1 snapshot. M4 mới union bundle, không bịa duplicate Rule nodes vào M2.

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/build_ontology_graph.py --approval ontology/curation_approval_v1.json --review-report docs/milestone_2/REVIEW.md
python -B scripts/build_ontology_graph.py --approval ontology/curation_approval_v1.json --review-report docs/milestone_2/REVIEW.md --output outputs/ontology_graph_rerun
```

**57tests OK** (46trước+11M2),8draft artifacts hai build byte-identical/LF; log gốc ở `VALIDATION.txt`. Hai approved builds và targeted regression11/11 có log tại `APPROVED_VALIDATION.txt`. Tests gồm thiếu definition/boundary/evidence, wrong owner/quote/offset, stale Rule/node snapshot, duplicate/endpoint/cycle, keyword VERIFIED không là axiom, approval thiếu/stale/catalog hash/ID/report/coerced bool, deterministic export và nguồn bất biến. Approval trong tests chỉ SYNTHETIC_TEST_ONLY; approval corpus được lưu riêng từ reviewer thật.

Sau reviewer approve semantic catalog, parent chuyển verdict cùng exact catalog hash/concept IDs/edge IDs; builder mới ghi approval artifact và review report thật. Runtime yêu cầu `--approval` và `--review-report`, bind cả catalog/M1 hash, exact concept/edge ID sets, reviewer_role=graph_reviewer, independent_review=true và review report SHA-256. Rebuild sẽ chuyển curation_status INDEPENDENTLY_REVIEWED/semantic VERIFIED, rồi reviewer kiểm tra nhanh approval/hash/status. Không sửa catalog sau approval mà vẫn dùng review cũ.

M2 không sửa Data, không Fact Graph/online API/model. Input issue/association hashes được kiểm với snapshot M0; full219hash đã xác minh ở M1 được tái sử dụng, finalM5 sẽ kiểm lại toàn snapshot. Pin baseline mới do parent thu thập choM5 chưa được dùng để port code trongM2. Tiếp theo sau PASS là M3 Case Graph trung thực theo policy.
