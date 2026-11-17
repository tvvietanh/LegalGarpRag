# Cloud Orchestrator — preparation, not activation

Status: **DRAFT / NOT RUNNING**. This branch does not start Codex, consume OpenAI API, touch the user's computer/terminal, or enable automatic issue processing.

## Purpose
A future unattended workflow will process the [Master Issue #1](https://github.com/tvvietanh/LegalGarpRag/issues/1), working through milestones M1 (Rule), M2 (Ontology), M3 (Fact), M4 (cross-layer), M5 (handoff) and URL identity verification. It must not work on the separate online QA agents.

## Proposed orchestration contract
1. Controller reads **trusted fixed repository configuration**, not arbitrary instructions embedded in issue/PR bodies.
2. Builder runs on a disposable cloud runner in an isolated worktree with minimum necessary permissions. It produces a patch and test evidence, never directly modifies `main`.
3. Reviewer runs in an independently checked-out, read-only environment. It validates code, input policy, graph envelope/IDs/endpoints, source spans, temporal claims, quarantines, and URL identity checks. Reviewer returns a machine-readable verdict with severity and evidence.
4. Controller retries at most 3 times on repairable failures. Persist checkpoint keyed by `issue_number + source_commit + milestone`, detect duplicates, and halt on unclear legal sources, unresolved permission, insufficient verified facts, rate limits or exhausted budget.
5. Open a *draft PR* with diff and validation logs for human approval; never auto-merge. Update master Issue with milestone status and links, **without** calling a reviewer response sufficient proof of a valid graph.
6. Final acceptance requires `outputs/final/nodes.jsonl`, `edges.jsonl`, `manifest.json`, `quality_report.json`, URL audit report and `docs/HANDOFF.md`, all reproducible from tracked inputs; if large outputs cannot be committed, upload them as release/artifact with checksums and retrieval guide.
7. The workflow may run on future issue changes only after an audited implementation, explicit owner approval and secret configuration.

## URL safety and quality requirements
- Use legal document-specific URLs; never substitute a search page or site's homepage.
- Check HTTP response and redirect, and independently match document number/title/issuer to the legal source. A 200 response alone is **not** verified identity.
- Preserve original URL, alternative URL, UTC `checked_at`, identity evidence and status VERIFIED/UNRESOLVED/BLOCKED.
- If an automated client is blocked but a browser link might work, mark BLOCKED pending human click, not VERIFIED.
- No fabricated URL, no inference of validity of legal provisions from document URL. Link verification and legal temporal validity are separate.

## Trust and execution safeguards
- Do not send raw issue/PR text to a code-executing agent as system instruction: extract bounded, explicitly allowed fields and treat external text as untrusted.
- OpenAI API key is a GitHub Actions **secret**, never a repository variable or committed file. OpenAI API usage is billed independently of ChatGPT Plus.
- On future Codex jobs, use `openai/codex-action@v1` on disposable Ubuntu runners, `safety-strategy: drop-sudo`, narrow permission profile, `actions/checkout` with `persist-credentials: false`. Separate credential-bearing GitHub operations from model-executed steps. Pin revisions after auditing them.
- Never expose write-capable repository tokens to untrusted worktrees. Do not permit arbitrary shell scripts from an Issue.
- Use `permissions` scoped separately to specific jobs and restrict triggering principals; prefer a protected environment and explicit approval for the first live run.
- Never change `Data/`, automatically merge to `main`, or disable sandbox controls.
- Limit API budget, duration, per-issue attempts and concurrency. Publish non-sensitive logs and redacted errors.

## Implemented now
- `.github/workflows/graph-orchestrator-preflight.yml`: **manual only**, uses no secrets, parses the existing Codex TOML configuration, checks `GRAPH_CONTRACT.md`, and runs current unit tests. No Codex calls or GitHub write permissions.
- No unattended Builder/Reviewer orchestration has been deployed or tested.

## Next owner approvals before enabling automation
1. Review and merge the draft PR into the desired feature branch (not `main`).
2. Confirm intended cost ceiling and allowed cloud model; configure an OpenAI API key securely in GitHub Actions Secrets if needed.
3. Approve a subsequent PR implementing bounded Builder/Reviewer/controller jobs with a dry run using fake GitHub/AI adapters.
4. Validate sandbox and redaction, then manually enable and test one milestone. Only afterward allow eligible issue-triggered runs.

The current ChatGPT conversation itself cannot act as an always-on supervisor. This design calls distinct cloud agents instead.
