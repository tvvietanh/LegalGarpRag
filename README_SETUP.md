# Codex dual subagents — Installation and usage

1. Unzip this package into the *root* of your `LegalGarpRag` repository, preserving `.codex/agents/`. On Windows enable viewing hidden folders if needed. Do not overwrite an existing AGENTS.md or `.codex/config.toml` without merging your content first.
2. Use Codex Desktop, CLI, or supported Codex IDE integration from the repository root. Close/reopen the Codex session so the project custom roles are discovered. The two agent roles are `graph_builder` and `graph_reviewer`.
3. Ensure project source data is physically available in repo under `Data/` or at repo root (`02_processed_data`, etc.). This package contains *configuration and instructions only*, not 172 MB of user raw data.
4. Paste the following Vietnamese orchestration message into the main Codex chat:

   Hãy dùng đúng 2 custom subagents: graph_builder (chỉ agent này được chỉnh code) và graph_reviewer (chỉ đọc và kiểm thử). Đọc AGENTS.md và docs/GRAPH_CONTRACT.md. Chỉ xây offline Rule Graph, Ontology Graph, Fact Graph và cross-layer graph của luật lao động Việt Nam từ dữ liệu có sẵn. So sánh cấu trúc nghiên cứu với XMUDeepLIT/LegalGraphRAG nhưng không sao chép máy móc luật hình sự Trung Quốc. Làm theo 5 milestone (inventory/schema, Rule, Ontology, Fact, integration/export). Sau MỖI milestone hãy chờ builder hoàn tất, nhờ reviewer kiểm tra độc lập; FAIL thì builder sửa rồi reviewer kiểm lại. Không triển khai API, agent online hoặc frontend. Báo cáo chính xác file đã thay đổi, test chạy và PASS/FAIL. Bắt đầu milestone 0: inventory/schema, KHÔNG viết tất cả cùng lúc.

5. Verify the actual roles using Codex's agent controls or by asking the parent agent to list available custom subagents. Support depends on the Codex client/version and account. If not detected, update Codex and verify directory location.
6. For data handoff, your online teammate only needs graph_v1/ JSONL+manifest and docs/GRAPH_CONTRACT.md; Neo4j is an optional downstream import.

Documentation: https://learn.chatgpt.com/docs/agent-configuration/subagents .
