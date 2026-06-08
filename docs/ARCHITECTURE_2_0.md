# NeuroScale 2.0 — Architecture

## Overview

NeuroScale 2.0 extends the core NeuroScale ML platform with an **autonomous SRE agent layer** built on Google Agent Development Kit (ADK). Three specialised agents collaborate via an Agent-to-Agent (A2A) protocol to detect, diagnose, and remediate Kubernetes incidents **without human intervention in the hot path**.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NeuroScale 2.0 — Agent Layer                     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  A2A Orchestrator                            │   │
│  │              (agents/orchestrator.py)                        │   │
│  └──────────────┬─────────────────┬──────────────┬─────────────┘   │
│                 │                 │              │                  │
│                 ▼                 ▼              ▼                  │
│  ┌──────────────────┐ ┌───────────────────┐ ┌──────────────────┐   │
│  │  Watcher Agent   │ │ Diagnostician     │ │ Operator Agent   │   │
│  │  watcher.py      │ │ Agent             │ │ operator.py      │   │
│  │                  │ │ diagnostician.py  │ │                  │   │
│  │  • Poll metrics  │ │ • Root-cause      │ │ • Create branch  │   │
│  │  • Detect anomaly│ │ • RAG runbook     │ │ • Commit YAML    │   │
│  │  • Score severity│ │ • Build plan      │ │ • Open MR        │   │
│  └────────┬─────────┘ └────────┬──────────┘ └────────┬─────────┘   │
│           │                    │                     │              │
└───────────┼────────────────────┼─────────────────────┼─────────────┘
            │                    │                     │
            ▼                    ▼                     ▼
┌───────────────┐   ┌────────────────────┐   ┌─────────────────────┐
│ Arize Phoenix │   │  Runbook RAG Store │   │  GitLab MCP Layer   │
│ MCP Client    │   │  (TF-IDF / Vertex) │   │  REST API v4        │
│ arize_mcp.py  │   │  rag_store.py      │   │  gitlab_mcp.py      │
└───────────────┘   └────────────────────┘   └─────────────────────┘
        │                    │                         │
        ▼                    ▼                         ▼
┌───────────────┐   ┌────────────────────┐   ┌─────────────────────┐
│ Arize Phoenix │   │  /runbooks/*.md    │   │  GitLab.com         │
│ Observability │   │  RB-001…RB-009     │   │  Branch / MR / HITL │
└───────────────┘   └────────────────────┘   └─────────────────────┘
```

---

## Agent Descriptions

### 1. Watcher Agent (`agents/watcher.py`)

**Role:** Continuous anomaly detection  
**Trigger:** Cron / A2A orchestrator loop  
**MCP tool used:** `get_model_metrics`, `list_monitors`, `get_alerts`

| Input | Output |
|-------|--------|
| Arize Phoenix metrics stream | List of `Anomaly` dicts with service, metric, value, threshold, severity |

**Decision logic:**
- Compares current metric values against configured thresholds
- Scores severity: `warning` / `critical`
- Returns empty list if system nominal (no-op pipeline)

---

### 2. Diagnostician Agent (`agents/diagnostician.py`)

**Role:** Root-cause analysis + remediation planning  
**Trigger:** Watcher output (anomaly list)  
**MCP tools used:** `get_feature_drift`, `get_explainability`, `search_runbooks` (RAG)

| Input | Output |
|-------|--------|
| Single `Anomaly` dict | `RemediationPlan` dict with diagnosis, runbook, steps, YAML patch, confidence |

**Decision logic:**
1. Classifies anomaly type (latency / OOM / drift / error rate)
2. Queries RAG store for matching runbook
3. Synthesises root-cause narrative
4. Generates concrete YAML patch
5. Assigns confidence score; sets `requires_human_approval` flag

---

### 3. Operator Agent (`agents/operator.py`)

**Role:** Autonomous remediation execution  
**Trigger:** Diagnostician output (remediation plan)  
**MCP tools used:** `create_branch`, `create_or_update_file`, `create_merge_request`

| Input | Output |
|-------|--------|
| `RemediationPlan` dict | Execution report with branch, commit SHA, MR URL, HITL status |

**Workflow:**
1. `create_branch` → `agent/fix-INC-{id}-{timestamp}`
2. `create_or_update_file` → commits YAML patch with compliance metadata
3. `create_merge_request` → opens MR with Kyverno compliance checklist
4. `HITLNotifier.notify()` → logs + webhooks on-call channel

---

## MCP Tool Registry

### Arize Phoenix MCP (`agents/tools/arize_mcp.py`)

| Tool | Description |
|------|-------------|
| `get_model_metrics` | Fetch latency, error rate, drift metrics per model |
| `list_monitors` | List active SLO monitors and thresholds |
| `get_alerts` | Get fired alerts with severity and timestamps |
| `get_feature_drift` | PSI / KS scores per feature |
| `get_explainability` | SHAP feature importance for anomaly context |
| `inject_anomaly` | Demo: inject synthetic anomaly for testing |

### GitLab MCP (`agents/tools/gitlab_mcp.py`)

Mirrors `@zereight/mcp-gitlab` tool schema via GitLab REST API v4.

| Tool | Description |
|------|-------------|
| `create_branch` | Create feature branch from `main` |
| `create_or_update_file` | Commit file with message |
| `create_merge_request` | Open MR with title, description, labels |
| `list_merge_requests` | List open MRs |
| `get_merge_request` | Fetch MR details |

---

## RAG / Runbook Store (`agents/tools/rag_store.py`)

**Production:** Vertex AI Search (Google Cloud)  
**Demo mode:** Local TF-IDF over `runbooks/*.md`

Runbook library:

| ID | Title | Triggers |
|----|-------|---------|
| RB-001 | High Latency — HPA Scaling Limit | `latency_p99_ms > 800` |
| RB-002 | OOM Kill — Memory Pressure | `memory_rss > 80%` |
| RB-005 | Model Drift — PSI Breach | `psi_score > 0.2` |
| RB-007 | Error Rate Spike — CrashLoopBackOff | `5xx_rate > 5%` |
| RB-009 | Kyverno Policy Violation | Any policy deny event |

---

## A2A Protocol

Agents communicate via plain Python function calls within a single process in demo mode. In production, each agent is a Cloud Run service exposing an ADK-compatible REST endpoint.

```
Orchestrator
  │
  ├─▶ Watcher.watch() → anomalies: List[Anomaly]
  │
  ├─▶ for anomaly in anomalies:
  │     Diagnostician.diagnose(anomaly) → plan: RemediationPlan
  │
  └─▶ for plan in plans:
        Operator.execute(plan) → report: ExecutionReport
```

**Pipeline context** (passed through all phases):
```json
{
  "run_id": "RUN-0001-1748188800",
  "started_at": "2025-05-25T10:00:00Z",
  "anomalies": [...],
  "diagnoses": [...],
  "operations": [...],
  "errors": [],
  "status": "REMEDIATED"
}
```

---

## HITL (Human-in-the-Loop) Gate

All MRs include a `requires_human_approval` flag. The Operator Agent:
1. Always opens the MR (never auto-merges without approval)
2. Notifies on-call via configurable webhook (`HITL_WEBHOOK_URL`)
3. Marks MR eligible for auto-merge if `confidence > 0.9`
4. Enforces 15-minute SLA for auto-merge approval window

---

## Kyverno Policy Enforcement

Every committed YAML patch and MR description includes a verified Kyverno compliance checklist:

- ✅ Resource limits (`cpu`, `memory`)
- ✅ Non-root user (`runAsNonRoot: true`)
- ✅ Read-only root filesystem
- ✅ No privileged containers
- ✅ Rolling update strategy
- ✅ PodDisruptionBudget verified

---

## Configuration (`agents/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `true` | Run without live credentials |
| `ARIZE_API_KEY` | — | Arize Phoenix API key |
| `ARIZE_SPACE_ID` | — | Arize space ID |
| `GITLAB_TOKEN` | — | GitLab personal access token |
| `GITLAB_PROJECT_ID` | — | Target project ID |
| `HITL_WEBHOOK_URL` | — | Slack/PagerDuty webhook URL |
| `POLL_INTERVAL_SECONDS` | `30` | Watcher poll frequency |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | Google ADK (Agent Development Kit) |
| Observability | Arize Phoenix |
| Source control automation | GitLab MCP / REST API v4 |
| Policy enforcement | Kyverno |
| RAG backend (demo) | scikit-learn TF-IDF |
| RAG backend (prod) | Vertex AI Search |
| Runtime | Python 3.11 on Cloud Run |
| Orchestration | Kubernetes + GKE |
| A2A protocol | ADK native (REST in prod, direct in demo) |
