# Bàn giao Milestone 0 cho Lead Architect

Trạng thái chuẩn bị: nhánh `feature/hier-graph`, base `019949659cd6f5d4bfdd2608b3506e9282a9b390` của `origin/main`, repository [tvvietanh/LegalGarpRag](https://github.com/tvvietanh/LegalGarpRag). **Handoff review độc lập đã PASS; chuẩn bị commit/push tại thời điểm cập nhật tài liệu.** Báo cáo kiểm tra trước đó trong `HANDOFF_VALIDATION.txt` giữ mốc lịch sử chưa review/chưa commit/chưa push. Không triển khai M1 trong bước bàn giao này.

M0 đã được reviewer độc lập đánh giá **PASS_WITH_WARNINGS**, không blocker P0/P1; xem [REVIEW.md](REVIEW.md). Đây là kết quả kiểm kê và thiết kế, chưa là PASS cho graph runtime. Xem [REPORT.md](REPORT.md) để đọc dữ liệu thực, [SCHEMA_PROPOSAL.md](SCHEMA_PROPOSAL.md) để review mô hình ba tầng, [BASELINE_XMU.md](BASELINE_XMU.md) để kiểm tra attribution và giới hạn chưa pin revision XMU.

## Phạm vi commit dự kiến

Chỉ stage bằng danh sách tường minh, không `git add .`:

```text
.gitignore
.codex/config.toml
.codex/agents/graph_builder.toml
.codex/agents/graph_reviewer.toml
AGENTS.md
README_SETUP.md
docs/GRAPH_CONTRACT.md
docs/milestone_0/BASELINE_XMU.md
docs/milestone_0/SCHEMA_PROPOSAL.md
docs/milestone_0/REPORT.md
docs/milestone_0/REVIEW.md
docs/milestone_0/VALIDATION.txt
docs/milestone_0/GITHUB_HANDOFF.md
docs/milestone_0/HANDOFF_VALIDATION.txt
outputs/milestone_0/inventory.json
scripts/inventory_graph_inputs.py
tests/test_inventory_graph_inputs.py
```

Các hướng dẫn/config sẵn có được giữ nội dung; `.codex/` chỉ gồm ba cấu hình vai trò dùng chung, không credential hoặc đường dẫn máy. `VALIDATION.txt` chỉ chuẩn hóa prefix executable máy thành `python` trong phần trình bày lệnh và ghi chú thao tác đó; giữ kết quả kiểm thử cũ. Bước này không sửa source/tests/schema hoặc hai cảnh báo P2 của M0.

Không stage bất kỳ file `Data/` nào. ZIP nguồn cục bộ `Data/01_raw_data.zip` 180.081.453 byte được ignore, không upload hoặc xóa. 218 file Data đã có trong base commit giữ nguyên byte; bản copy `inventory.rerun.json`, cache và fixture tạm cũng không commit. Canonical `inventory.json` là báo cáo metadata kiểm kê, không chứa bản sao toàn văn nguồn.

## Tái lập và đối chiếu dữ liệu

Runtime kiểm kê/tests dùng Python standard library, không network; phiên bản đã chạy là Python 3.13.12. Lệnh chạy từ root repository:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/inventory_graph_inputs.py --root . --output outputs/milestone_0/inventory.rerun.json --compare outputs/milestone_0/inventory.json
Get-FileHash outputs/milestone_0/inventory.json, outputs/milestone_0/inventory.rerun.json -Algorithm SHA256
git diff --exit-code -- Data
git diff --cached --exit-code -- Data
```

Exact snapshot của M0 gồm **219 file**, bao gồm ZIP cục bộ không nằm trong Git. Vì vậy clone mới chỉ có 218 file Data: không thể kỳ vọng full dataset digest khớp canonical snapshot nếu chưa có đúng ZIP nguồn. Không cần tải ZIP để đọc/review schema hoặc chạy unit tests. Có thể chạy inventory **không có `--compare`** để kiểm kê dataset clone, rồi đối chiếu từng `files[path,bytes,sha256]` với 218 entry tương ứng trong canonical report; ghi rõ ZIP absent, không sửa snapshot gốc và không coi thiếu ZIP là thay đổi 218 nguồn đã track. Muốn chạy exact `--compare` phải có ZIP gốc đúng checksum ghi trong inventory; không tự dựng lại ZIP có bytes khác.

Hai inventory hiện có cùng SHA-256 `92a8d824401336c831ca417e4b43a2c0bec2fab8ae620a4d2a1b29794a7bd893`; full input digest `30ebe107f6a48803e32769f788f1982662d8000e55a343fe01dd768e0db8a79e`. P2 newline Windows vẫn còn: byte hash là kết quả môi trường này, object comparison là cách đối chiếu khi newline khác hệ điều hành. Không tuyên bố tái lập byte xuyên hệ điều hành đã đạt.

## Ưu tiên Issues và công việc tiếp theo

Parent đã kiểm tra GitHub REST read-only `issues?state=open&per_page=100`: **0 open Issues/PR tại thời điểm chuẩn bị**. Không có Issue được giao để tự suy ưu tiên. Read-only `git ls-remote --heads origin main feature/hier-graph` chỉ thấy main tại base SHA trên; nhánh feature chưa có trên remote. Kết nối mặc định bị sandbox proxy chặn; read-only kiểm tra ngoài sandbox thành công. Chưa kiểm chứng quyền ghi bằng push.

Khi Lead Architect có phản hồi/Issues: ưu tiên blocker P0/P1 về trust boundary, evidence, provenance, temporal và hierarchy; tiếp theo Issue phụ thuộc schema đã được xác nhận; sau đó P2 và coverage theo milestone. Hai P2 đang mở từ review M0 là (1) newline serialization và (2) inventory index lấy dòng duplicate cuối khi audit joins. Cần thực thi LF và reject duplicate/conflict đúng thiết kế khi xây builder/exporter, không dùng công cụ inventory hiện tại làm runtime publisher.

Nếu được giao M1 sau review, bước tối thiểu là thực thi Rule Graph gates: 111 policy-eligible literal mismatches và child closure, duplicate/collision rejection, endpoint allow-list và temporal uncertainty. Không đẩy 896 quarantine records hoặc dữ liệu chưa review vào graph để tăng coverage. Không xây API/frontend hoặc bắt đầu M1 trong commit bàn giao M0.

## Phụ lục — tóm tắt review bàn giao độc lập

**VERDICT = PASS cho gói bàn giao GitHub Milestone 0.** Không có blocker mới P0/P1. Reviewer độc lập xác nhận đúng 17 staged files, branch `feature/hier-graph` và origin `tvvietanh/LegalGarpRag`; không Data/ZIP/cache/credentials staged; diff check PASS; `python -B -m unittest discover -s tests -v` 12/12 OK; 219 Data files hash khớp inventory, 218 tracked source files bất biến; tài liệu công khai 219 vs 218 và newline Windows. Verdict kỹ thuật M0 vẫn **PASS_WITH_WARNINGS** với 2 P2 tại [REVIEW.md](REVIEW.md). Reviewer không sửa file, commit, push.

Đây là bản tóm tắt verdict độc lập do parent chuyển lại sau khi reviewer hoàn tất, không phải builder tự chứng nhận. Kết quả commit/push và SHA remote sẽ được xác minh và báo sau thao tác thực tế.
