# Đề xuất schema v1 cho graph offline

Trạng thái: **đề xuất Milestone 0**, chưa có runtime graph builder. Tài liệu này chi tiết hóa `docs/GRAPH_CONTRACT.md`, không đổi dữ liệu nguồn hoặc tuyên bố các trường output đã tồn tại trong input. Không có API/frontend/model endpoint. Mỗi milestone triển khai phải được graph_reviewer kiểm tra độc lập trước bước sau.

## Envelope, ID và dữ liệu gốc

Node bắt buộc `{id, type, layer, properties}`; edge bắt buộc `{id, source_id, target_id, type, layer, properties}`. `properties` là object; type/layer/endpoint theo allow-list bên dưới; reject field sai kiểu hoặc ID trống, không ép chuỗi bool thành bool. Layer node chỉ `rule|ontology|fact`; layer cạnh nội tầng tương ứng, cạnh xuyên tầng dùng `cross`.

ID node = `<layer>:<kind>:<encoded source ID>`, phần source ID dùng percent-encoding UTF-8 với `safe=""` và giữ nguyên hoa/thường; không trim, không đổi ID nguồn. Kind cố định: document, provision, identity, version, issue, concept, case, actor, event, assertion, evidence. Bản ghi hiện có dùng khóa thật, không dùng tên/số điều làm ID. Ví dụ `rule:provision:prov_4852d4aeb374ee44` khác `rule:version:prov_4852d4aeb374ee44`: cả 18.871 provision và version đang dùng chung raw IDs. Một raw ID trùng trong **cùng** namespace là lỗi; không dùng last-write-wins.

Actor/Event/Assertion/EvidenceSpan chưa có nguồn cấu trúc được duyệt. Khi bổ sung, dùng ID ổn định từ hồ sơ review bất biến, có scope case; không entity-resolve actor giữa các case bằng tên. Nếu cần ID nội sinh: SHA-256 canonical JSON của `[case_id, kind, source_record_id, coordinate_space, start, end, assertion_kind]`; hash không chứa nhãn có thể sửa hoặc timestamp chạy. Không tạo các node này trong M0.

Edge ID = `edge:` + SHA-256 của canonical JSON `[schema_version, layer, type, source_id, target_id, evidence_key]`. `evidence_key` là source dataset/path + source record ID + span; record không có khóa như issue_edges dùng hash nội dung canonical row, không dùng số dòng. Cạnh cấu trúc dùng khóa nguồn cha/con. Hai bằng chứng khác nhau được lưu như hai cạnh có ID khác nhau; cạnh cùng identity lặp phải được phát hiện, đếm duplicate và chỉ hợp nhất khi bytes/properties tương đương, ghi lineage của mọi dòng. Cùng identity nhưng properties mâu thuẫn phải reject/fail, không ghi đè.

Mỗi node/cạnh có `properties.source_record_id`, `source_path`, `source_sha256`, `source_record_sha256`, `provenance`, `verification`. Giữ material source fields trong `properties.source_properties` với kiểu gốc; giữ explicit null nếu nguồn có null, không bịa null cho key thiếu. Các field normalized là phần riêng, luôn có mapping/derivation version. Số dòng được ghi làm locator để tìm nguồn, **không** tham gia ID. Hash file giúp phát hiện nguồn thay đổi; hash row giúp giữ ID khi chỉ đổi thứ tự input. Không cần nhúng toàn văn lặp vào mọi cạnh.

## Rule Graph

| Type / kind | Nguồn và properties trọng yếu | Điều kiện công bố |
|---|---|---|
| Document / document | `04_metadata/documents.jsonl:document_id`; source_group, classification, graph_role, title, source references, import policy; date claims nằm riêng | ACTIVE + graph_eligible=true + policy.allow + allow_document_and_source_nodes đều true; thiếu cờ là deny. Metadata-only role vẫn chỉ là nguồn tham chiếu. |
| Provision / provision | `02_processed_data/provisions.jsonl:provision_id`; document_id, level ARTICLE/CLAUSE/POINT, canonical_path, parent_id, text, span, segment_id, order | Document qua gate trên và allow_provision_hierarchy=true; không có trong quarantine; span gate và chain cha hợp lệ. |
| ProvisionIdentity / identity | `06_temporal/provision_identities.jsonl:provision_identity_id`; instrument_id/canonical_path, temporal_status | Chỉ closure từ provision được publish, không thêm toàn bộ identity mồ côi. Không đồng nhất số điều giữa văn bản khác nhau. |
| ProvisionVersion / version | `06_temporal/provision_versions.jsonl:provision_version_id`; identity, source_document_version_id, source temporal fields | Chỉ từ provision được publish; joins nhất quán với document và identity; không diễn giải thành verified applicability. |

| Edge type | Hướng và endpoint được phép | Bằng chứng / hạn chế |
|---|---|---|
| CONTAINS | Document→Provision(ARTICLE); Provision(ARTICLE)→Provision(CLAUSE); Provision(CLAUSE)→Provision(POINT) | parent_id trực tiếp và cùng document; cấp khác chỉ đưa candidate để review. Không tạo cha thiếu. Cấm cycle/self-loop. |
| HAS_IDENTITY | Provision→ProvisionIdentity | FK provision_identity_id, lưu record join. |
| HAS_VERSION | ProvisionIdentity→ProvisionVersion | FK trong version; không dùng Provision→Version cùng type cạnh gây mơ hồ. Provision lưu qualified version node ID trong properties, có kiểm tra join. |
| CITES / REFERENCES | Document→Document, Provision→Provision, Provision→Document | Chỉ text viện dẫn đã đối chiếu, target resolve duy nhất và được duyệt semantic mapping; tham chiếu không đồng nghĩa áp dụng. Case CITES nằm phần xuyên tầng. |
| AMENDS / REPEALS / REPLACES | Document→Document, Provision→ProvisionIdentity | Hướng văn bản/điều sửa đổi tới đối tượng bị thay đổi. Cần review operation, scope, target và chứng cứ pháp lý; không map tự động Provision→Provision từ accepted list. |

LegalRule để ngoài allow-list v1; checklist không tự thành Rule. `hierarchy_headings.jsonl` thực có `id`, label Chapter/Section và span, **không có parent_id**. V1 giữ các heading này dưới metadata bố cục document và provenance; `chapter`/`section` trên provision chỉ là nhãn. Không tạo node Chapter/Section hoặc edge hierarchy từ thứ tự/nhãn khi chưa có reviewed structural mapping. Nếu M1 cần hai loại node đó phải version schema và review trước. Cây chính vẫn dùng parent_id thật của provisions.

## Ontology Graph

| Type | Nội dung | Gate |
|---|---|---|
| LegalIssue | Khóa `issue_id`, issue_key, label_vi từ 17 records hiện có; vocabulary_status=`SOURCE_VOCABULARY`, definition_status=`PENDING` nếu chưa có định nghĩa | Được dùng như vocabulary chủ đề có provenance; không biến label thành khái niệm chuẩn hóa đã duyệt. |
| LegalConcept | ID curated riêng; definition_vi, inclusion/exclusion criteria, scope, definition evidence, curator/review record | Phải có định nghĩa, ranh giới và evidence đã review; hiện repo chưa có catalog concept đủ điều kiện, không tự tạo từ keywords. |

`IS_A`: LegalConcept→LegalConcept, subtype tới supertype, không cycle/self-loop, reviewed necessary conceptual inclusion; không dùng LegalIssue làm lớp hình thức. `RELATED_TO`: LegalIssue↔LegalIssue hoặc LegalConcept↔LegalConcept, mỗi edge là một hướng; chỉ dùng khi curated weak association có lý do rõ, không suy transitive. ActorType/ActionType chưa bật.

`ABOUT_ISSUE`: Provision/Document/Case→LegalIssue, layer=cross; tương đương yếu của RELATES_TO_ISSUE/HAS_ISSUE, không đổi thành REGULATED_BY. `provenance_status=VERIFIED` trên 7.859 heuristic keyword edges chỉ chứng minh locatable text; chưa chứng minh liên hệ semantic được duyệt. Giữ toàn bộ trong candidate/review output; publish từng cạnh khi có review record explicit. Có thể công bố issue vocabulary trong M2 dù chưa có mapping đủ điều kiện; báo coverage=0 với lý do.

## Fact Graph

| Type | Properties trọng yếu | Gate |
|---|---|---|
| Case | `case_id`, document_id, source full_text reference, case classification, source review policy; section text lưu là legacy source material | Case và metadata cùng document đều ACTIVE/eligible/allow, allow_document_and_source_nodes; 24 là upper bound hiện tại. Không sử dụng court/date legacy như verified nếu thiếu own-header evidence. |
| Actor | case scope, role, source mention, resolved identity status | Chỉ reviewed extraction có bằng chứng chỉ đúng actor; tên giống nhau không đủ để merge. |
| Event | case scope, action/event label, time assertion, participants | Chỉ từ reviewed spans; ngày sự kiện không suy từ decision_date. |
| FactAssertion | exact statement/normalized proposition, assertion_kind, asserted_by, review status, evidence | assertion_kind là ALLEGATION / COURT_FINDING / ADJUDICATION; không nâng allegation thành finding. |
| EvidenceSpan (tùy chọn) | source document/case/segment, coordinate_space, offsets, text hash, page bounds | Shared source locator, không phải chứng cứ tự tạo. |

Cạnh nội tầng: Case→FactAssertion `HAS_ASSERTION`; Case→Event `HAS_EVENT`; Case→Actor và Event→Actor `INVOLVES`; FactAssertion/Event/Actor→EvidenceSpan `SUPPORTED_BY`. Assertion attribution dùng properties `assertion_kind`, `attributed_actor_id` (chỉ khi có actor đã publish), `court_source_case_id`, không bật thêm ALLEGED_BY/FOUND_BY_COURT/DECIDED_BY gây endpoint mơ hồ. Mọi extracted assertion phải có speaker/status và verified evidence. Không có reviewed extraction thì chỉ Case node, `fact_extraction_status=PENDING_REVIEW`, report **fact extraction pending**. Hiện cả 36 case đều `case_extracted_facts_enabled=false`; không tự bật hoặc đọc facts/reasoning/decision thành assertions. Policy deny chiếm ưu tiên ngay cả nếu evidence đủ literal.

## Liên kết xuyên tầng

| Type | Hướng / endpoint | Nội dung được phép |
|---|---|---|
| INSTANCE_OF | Actor/Event/FactAssertion→LegalConcept | Reviewed classification; chưa có concept/đối tượng thì 0 cạnh. Không Case→LegalConcept nếu chưa có type CaseCategory riêng. |
| REGULATED_BY | LegalConcept/LegalIssue→Provision | Bằng chứng quy phạm và review về phạm vi điều chỉnh; không đảo cạnh keyword để tạo cạnh này. |
| CITES | Case→Provision/Document | Trích dẫn gốc được định vị, target duy nhất, policy endpoint và semantic review; citation ≠ applicability. |
| ABOUT_ISSUE | Case/Document/Provision→LegalIssue | Liên hệ chủ đề yếu đã review, không axiom phân lớp. |

Allow-list chỉ bật các cặp endpoint trong các bảng; các cặp khác hoặc type lạ bị reject có lý do. Không suy luật áp dụng cho case từ citation, issue keyword, similarity hoặc ngày xử án.

## Provenance và chứng cứ

`properties.provenance` là list evidence records: source path/hash; source record ID/hash/line locator; original document/case/provision IDs; method, generator/version, confidence nếu thực có; `coordinate_space`; segment/document offsets, page_start/end/source_unit_type khi có; evidence_text và evidence hash. Giữ source evidence_status và source provenance_status độc lập với output verification status.

Verification dimensions riêng: `structural`, `literal_evidence`, `semantic`, `temporal`, `review_record_id` (chỉ khi có). Values VERIFIED / UNVERIFIED / NOT_APPLICABLE; input RESOLVED không tự map thành tất cả VERIFIED. Structural FK chỉ cần join validation; extracted legal edge/assertion phải semantic VERIFIED và evidence verified bằng review artifact có reviewer, decision, input hash, source IDs. Candidate có thể có literal VERIFIED nhưng semantic UNVERIFIED.

Span dùng 0-based Unicode code point, end-exclusive sau khi kiểm tra convention thực. SEGMENT_TEXT join segment_id; DOCUMENT_TEXT không có document_id trong evidence_span của nhiều case edges, phải join `source_id → cases.document_id → processed documents.document_id`, không tìm bằng substring toàn corpus. Kiểm tra owner document và bounds. Không normalize nguồn rồi giữ tọa độ cũ.

646 provision text không bằng slice segment, gồm 111 policy-eligible; 38/646 có excluded_annotation_spans nhưng chưa đủ để chấp thuận transformation. M1 giữ text gốc bất biến và phân tích transformation có lineage. Mặc định các provision mismatch là candidate-only tới khi có review chứng minh tọa độ/cleaning hợp lệ. Không tự sửa text/span. Nếu cha bị chặn thì toàn child closure phụ thuộc cha cũng chưa publish; các số 4.067/3.956 chỉ là screen trước gate chain, không cam kết output count.

## Temporal model

Giữ `properties.temporal.source` nguyên field nguồn (valid_from/to, temporal_status, temporal_evidence, provision_temporal_verified, coverage_as_of; document effective_from/to và status). `properties.temporal.assessment` độc lập: `INHERITED_UNVERIFIED`, `UNKNOWN`, hoặc `VERIFIED_PROVISION` khi có review evidence theo đúng provision/version. Không ghi ngày normalized verified vào source field. Document temporal_verified không lan xuống provision.

V1 không tạo effective-date edge từ toàn bộ 18.871 INHERITED_DOCUMENT versions, không khẳng định "có hiệu lực ngày X". 25 legal_changes đều temporal UNKNOWN; 11 RESOLVED targets vẫn chỉ là candidates. Nếu có verified intervals sau này: ISO YYYY-MM-DD, [from,to) chỉ khi nguồn xác nhận convention, lưu source date semantics; thiếu end không được hiểu tự động còn hiệu lực; checked_as_of là mốc kiểm chứng, không phải thời điểm build. Mọi mapping/interval có điểm chưa rõ phải giữ unknown, không lấy ngày hiện tại để hoàn thiện dữ liệu. Không tự đóng interval cũ từ REPLACES khi chưa review scope/date.

## Gates, output và deterministic build dự kiến

Thứ tự: read/hash inputs → validate schema/IDs → policy eligibility → provenance/span → structural closure → reviewed semantic/temporal relations → endpoint/type/cycle checks → deterministic export. Không sửa Data, không đẩy quarantine vào trusted. Nếu ID namespace collision hay conflicting duplicate trong published candidates: fail build. Dangling candidate phải ghi reject (ID nguồn, lý do, nguồn hash) thay vì biến thành stub node. Quarantined rows được đếm theo record và distinct IDs; không dedupe rồi che mất số bị loại.

Output cuối dự kiến (M5): `outputs/graph_v1/nodes.jsonl`, `edges.jsonl`, `manifest.json`, `quality_report.json`; bổ sung `rejects.jsonl` và `candidates.jsonl` để giải thích không publish. Không tạo file nodes/edges rỗng ở M0 gây hiểu nhầm graph đã hoàn tất.

Canonical JSON UTF-8, ensure_ascii=false, sort_keys=true, separators=(comma,colon), newline LF và newline cuối file; sort records bằng qualified ID; list evidence được sort theo evidence_key. Không phụ thuộc input order, hash seed, cwd/absolute path hay thời gian chạy. Cùng data/config/schema/review catalog cho bytes/IDs giống nhau. Không nối timestamp runtime vào hashed output. Review/config và tool source hashes là manifest dependencies.

Manifest: schema_version, dataset/config/review/source code digests, relative input file paths/hash/record counts, node/edge totals by layer/type, excluded/reject counts, coverage denominators, status, hash output files; deterministic build_id từ input/config/review/schema digests. Quality report: duplicate/dangling/type violations, eligibility violations, evidence and semantic review coverage, unverified temporal counts, candidate/reject reason partition và overlapping labels riêng; review verdict ghi đúng phạm vi milestone. Cạnh bị loại nhiều lý do dùng primary_reason theo thứ tự gate cộng reason_codes list; tổng primary_reason bằng tổng excluded, label counts không cộng thành tổng.

## Kế hoạch kiểm thử và milestone

M0 chỉ kiểm kê/schema và công cụ read-only; tests hiện có không chứng minh runtime graph đúng. M1 fixture cần namespace provision/version trùng raw ID; input cha sau con; missing parent/cycle/cross-document parent; policy thiếu/false; quarantine trùng ID; span wrong owner/bounds/cleaning pending; references accepted nhưng chưa semantic review; INHERITED_DOCUMENT không trở thành verified. M2 fixture kiểm IS_A cycle, định nghĩa thiếu, keyword VERIFIED vẫn candidate. M3 fixture case eligible nhưng facts disabled; allegation ≠ court finding; missing speaker/evidence; duplicate actor names khác case. M4 fixture endpoint allow-list và cross-layer scope. M5 shuffle inputs, build hai lần, compare bytes/hashes, zero duplicate/dangling, count partitions/reject completeness và handoff contract.

Thứ tự thực hiện sau M0 được chấp nhận: Rule → Ontology → Fact → cross-layer gates → export/handoff. Mỗi bước builder hoàn tất, reviewer read-only review, FAIL trả đúng blockers cho builder rồi review lại. Gate chất lượng có thể cho graph thưa: không tăng coverage bằng việc suy luận căn cứ không có trong nguồn.
