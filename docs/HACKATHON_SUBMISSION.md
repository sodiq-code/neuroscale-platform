# NeuroScale 2.0 — Hackathon Submission

## Project Title
**NeuroScale 2.0: Autonomous SRE Agents for ML Platforms**

## One-Line Pitch
> From anomaly detected to Merge Request opened — in under 60 seconds, zero human intervention.

---

## The Problem

Enterprise ML platforms fail silently and expensively.

When a Kubernetes-hosted inference service breaches its latency SLO at 2 AM, the current state of the art is:

1. Arize Phoenix fires an alert
2. PagerDuty wakes up an on-call engineer
3. Engineer reads dashboards, consults runbooks, SSHs into the cluster
4. Engineer manually edits YAML, opens a PR, waits for review
5. **Resolution time: 30–90 minutes**

This is slow, expensive, error-prone, and burns out your best engineers.

---

## The Solution

NeuroScale 2.0 adds an **autonomous agent layer** on top of the existing NeuroScale ML platform. Three specialised AI agents — Watcher, Diagnostician, and Operator — collaborate via Google's Agent-to-Agent (A2A) protocol to detect, diagnose, and remediate incidents **automatically**.

**The human is only needed to click "Approve" on a fully-prepared, safety-checked Merge Request.**

---

## How It Works

### Phase 1: Detection (Watcher Agent)
- Polls **Arize Phoenix** metrics continuously via MCP
- Detects anomalies in latency, memory, drift, error rates
- Scores severity and triggers the A2A pipeline

### Phase 2: Diagnosis (Diagnostician Agent)
- Retrieves context from Arize: feature drift, explainability, alert history
- Performs **semantic RAG search** over a curated runbook library
- Synthesises a root-cause narrative and generates a concrete YAML patch
- Assigns a confidence score; flags cases requiring human approval

### Phase 3: Remediation (Operator Agent)
- Creates a Git branch via **GitLab MCP** (`@zereight/mcp-gitlab` tool schema)
- Commits the YAML patch with a structured commit message
- Opens a **Merge Request** with:
  - Root-cause summary
  - Runbook reference
  - Kyverno compliance checklist (resource limits, non-root, rolling update)
- Sends **HITL notification** via webhook to on-call channel

**Total time: < 60 seconds from anomaly to MR.**

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | Google Agent Development Kit (ADK) |
| A2A protocol | ADK native |
| Observability MCP | Arize Phoenix |
| Source control MCP | GitLab REST API v4 (`@zereight/mcp-gitlab` schema) |
| Runbook RAG | scikit-learn TF-IDF (demo) / Vertex AI Search (prod) |
| Policy enforcement | Kyverno |
| Runtime | Python 3.11, Cloud Run |
| Orchestration | Kubernetes / GKE |

---

## Hackathon Criteria Mapping

### ✅ Use of Google ADK
NeuroScale 2.0 is built on Google ADK. The `NeuroScaleOrchestrator` is the A2A coordinator, managing three ADK-compatible agents. Each agent exposes a standard interface consumable by ADK's agent runner.

**Code location:** `agents/orchestrator.py`, `agents/watcher.py`, `agents/diagnostician.py`, `agents/operator.py`

### ✅ MCP Integration — Arize Phoenix
The `ArizeMCPClient` implements the full Arize Phoenix MCP tool schema: `get_model_metrics`, `list_monitors`, `get_alerts`, `get_feature_drift`, `get_explainability`. In demo mode, it returns realistic synthetic data; in production, it connects to a live Arize Phoenix instance.

**Code location:** `agents/tools/arize_mcp.py`

### ✅ MCP Integration — GitLab
The `GitLabMCPClient` mirrors the `@zereight/mcp-gitlab` tool schema via GitLab REST API v4. Tools used: `create_branch`, `create_or_update_file`, `create_merge_request`.

**Code location:** `agents/tools/gitlab_mcp.py`

### ✅ Agent-to-Agent (A2A) Communication
Watcher → Diagnostician → Operator is a true A2A pipeline. The orchestrator passes structured context dicts between agents. In production, each agent is a Cloud Run service with an ADK REST endpoint.

**Code location:** `agents/orchestrator.py`

### ✅ RAG / Grounding
The Diagnostician grounds its root-cause analysis in a curated runbook library via semantic search. This prevents hallucination and ensures recommendations are traceable to human-authored SRE playbooks.

**Code location:** `agents/tools/rag_store.py`, `runbooks/`

### ✅ Enterprise Safety (Kyverno + HITL)
Every MR includes a Kyverno compliance checklist. The HITL gate ensures humans review before production changes merge. Confidence scoring prevents auto-merge for uncertain cases.

**Code location:** `agents/operator.py` (`_open_mr`), `agents/operator.py` (`HITLNotifier`)

---

## Demo Instructions

### Zero-credential demo (recommended)
```bash
# 1. Install dependencies
pip install httpx scikit-learn

# 2. Run full 10-beat cinematic demo
bash scripts/demo-run.sh

# 3. Or run just the A2A pipeline once
python3 agents/orchestrator.py --inject

# 4. Run all self-tests
bash scripts/verify-all.sh
```

### Production mode
```bash
export ARIZE_API_KEY=your_key
export ARIZE_SPACE_ID=your_space
export GITLAB_TOKEN=your_token
export GITLAB_PROJECT_ID=your_project_id
export DEMO_MODE=false
export HITL_WEBHOOK_URL=https://hooks.slack.com/...

python3 agents/orchestrator.py --watch --interval 30
```

---

## Enterprise Value

| Metric | Before (Manual) | After (NeuroScale 2.0) |
|--------|----------------|------------------------|
| Detection-to-MR | 30–90 minutes | < 60 seconds |
| On-call disruptions | Every incident | Approval only |
| Runbook compliance | Ad-hoc | 100% enforced |
| Kyverno policy coverage | Manual audit | Automated in every MR |
| Engineer burnout | High | Dramatically reduced |

---

## What's Next

- **Auto-merge with confidence threshold** — fully autonomous remediation for well-understood incident classes
- **Multi-cluster support** — Watcher polls metrics across GKE fleet
- **Incident memory** — vector DB of past incidents improves diagnosis accuracy over time
- **Slack/Teams bot** — HITL channel with one-click approve/reject
- **Cost attribution** — tag every MR with estimated cost-of-incident-averted

---

## Repository Structure

```
neuroscale-platform/
├── agents/
│   ├── config.py              # Centralised configuration
│   ├── watcher.py             # Watcher Agent
│   ├── diagnostician.py       # Diagnostician Agent
│   ├── operator.py            # Operator Agent
│   ├── orchestrator.py        # A2A Orchestrator
│   ├── tools/
│   │   ├── arize_mcp.py       # Arize Phoenix MCP client
│   │   ├── gitlab_mcp.py      # GitLab MCP client
│   │   └── rag_store.py       # RAG / runbook search
│   └── demo/
│       ├── inject_failure.sh  # Failure injection
│       └── reset_demo.sh      # Demo reset
├── runbooks/
│   ├── RB-001-high-latency.md
│   ├── RB-002-oom-kill.md
│   ├── RB-005-model-drift.md
│   ├── RB-007-error-rate-spike.md
│   └── RB-009-kyverno-violation.md
├── docs/
│   ├── ARCHITECTURE_2_0.md
│   ├── DEMO_SCRIPT.md
│   ├── HACKATHON_SUBMISSION.md
│   └── JUDGING.md
├── scripts/
│   ├── verify-all.sh          # Full test suite
│   └── demo-run.sh            # Cinematic demo
└── infrastructure/
    └── agents/
        └── deployment.yaml    # K8s manifest
```

---

## Team

Built for the **[Hackathon Name]** hackathon.  
Repository: `sodiq-code/neuroscale-platform`  
License: MIT
