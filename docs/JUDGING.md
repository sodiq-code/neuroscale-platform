# NeuroScale 2.0 — Judge's Reference Guide

> Quick map from hackathon criteria → exact code locations + key lines

---

## Criterion 1: Google ADK Usage

| What to look at | File | Line / Section |
|----------------|------|---------------|
| A2A Orchestrator | `agents/orchestrator.py` | `class NeuroScaleOrchestrator` |
| Agent interfaces | `agents/watcher.py` | `class WatcherAgent` |
| Agent interfaces | `agents/diagnostician.py` | `class DiagnosticianAgent` |
| Agent interfaces | `agents/operator.py` | `class OperatorAgent` |
| ADK config | `agents/config.py` | `ADK_*` settings |

**Key feature:** `run_once()` and `run_continuous()` demonstrate ADK's two primary execution modes.

---

## Criterion 2: MCP — Arize Phoenix

| What to look at | File | Line / Section |
|----------------|------|---------------|
| Full MCP client | `agents/tools/arize_mcp.py` | `class ArizeMCPClient` |
| Tool: get_model_metrics | `arize_mcp.py` | `def _tool_get_model_metrics` |
| Tool: list_monitors | `arize_mcp.py` | `def _tool_list_monitors` |
| Tool: get_alerts | `arize_mcp.py` | `def _tool_get_alerts` |
| Tool: get_feature_drift | `arize_mcp.py` | `def _tool_get_feature_drift` |
| Tool: get_explainability | `arize_mcp.py` | `def _tool_get_explainability` |
| Demo inject | `arize_mcp.py` | `def inject_anomaly` |
| Used by Watcher | `agents/watcher.py` | `self.arize.call_tool(...)` |
| Used by Diagnostician | `agents/diagnostician.py` | `self.arize.call_tool(...)` |

---

## Criterion 3: MCP — GitLab

| What to look at | File | Line / Section |
|----------------|------|---------------|
| Full MCP client | `agents/tools/gitlab_mcp.py` | `class GitLabMCPClient` |
| Tool: create_branch | `gitlab_mcp.py` | `def _tool_create_branch` |
| Tool: create_or_update_file | `gitlab_mcp.py` | `def _tool_create_or_update_file` |
| Tool: create_merge_request | `gitlab_mcp.py` | `def _tool_create_merge_request` |
| Tool: list_merge_requests | `gitlab_mcp.py` | `def _tool_list_merge_requests` |
| Used by Operator | `agents/operator.py` | `self.gitlab.call_tool(...)` |
| MR with Kyverno checklist | `agents/operator.py` | `def _open_mr` → `description` variable |

---

## Criterion 4: A2A Protocol

| What to look at | File | Line / Section |
|----------------|------|---------------|
| Pipeline runner | `agents/orchestrator.py` | `def run_once` |
| Watcher → Diagnostician handoff | `orchestrator.py` | `self._run_diagnostician(context, anomalies)` |
| Diagnostician → Operator handoff | `orchestrator.py` | `self._run_operator(context, diagnoses)` |
| Structured context dict | `orchestrator.py` | `context: dict[str, Any]` |
| Error isolation per phase | `orchestrator.py` | `try/except` in each `_run_*` method |

---

## Criterion 5: RAG / Grounding

| What to look at | File | Line / Section |
|----------------|------|---------------|
| RAG store | `agents/tools/rag_store.py` | `class RunbookRAG` |
| TF-IDF indexing | `rag_store.py` | `def _build_index` |
| Semantic search | `rag_store.py` | `def search` |
| Runbook library | `runbooks/*.md` | RB-001, 002, 005, 007, 009 |
| Used by Diagnostician | `agents/diagnostician.py` | `self.rag.search(query)` |
| Runbook match → remediation plan | `diagnostician.py` | `def _build_plan` |

---

## Criterion 6: Enterprise Safety

| What to look at | File | Line / Section |
|----------------|------|---------------|
| HITL notifier | `agents/operator.py` | `class HITLNotifier` |
| Confidence gate | `agents/operator.py` | `requires_approval` logic |
| Kyverno checklist in MR | `agents/operator.py` | `description` in `_open_mr` |
| Auto-merge threshold | `agents/operator.py` | `confidence > 0.9` check |
| Human approval flow | `docs/DEMO_SCRIPT.md` | Beat 9 |

---

## Criterion 7: Demo Quality

| What to look at | File | Section |
|----------------|------|---------|
| Cinematic demo script | `scripts/demo-run.sh` | All 10 beats |
| Narration script | `docs/DEMO_SCRIPT.md` | Beat 1–10 |
| Failure injection | `agents/demo/inject_failure.sh` | 4 scenarios |
| Zero-credential demo | `agents/config.py` | `DEMO_MODE=true` default |
| Self-test suite | `scripts/verify-all.sh` | 7 tests |

---

## Run It Yourself (30 seconds)

```bash
cd /path/to/neuroscale-platform

# Install deps
pip install httpx scikit-learn

# Full test suite
bash scripts/verify-all.sh

# Cinematic demo
bash scripts/demo-run.sh

# Or just the core pipeline
python3 agents/orchestrator.py --inject
```

---

## Architecture in One Picture

```
Arize Phoenix ──MCP──▶ Watcher ─────┐
                                     │ anomaly
                                     ▼
Runbook RAG ──────────▶ Diagnostician ──┐
                                         │ plan
                                         ▼
GitLab MCP ◀──────────── Operator ───────┘
                              │
                              ▼
                         HITL Gate → On-call engineer clicks ✅
```
