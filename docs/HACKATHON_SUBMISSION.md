# NeuroScale 2.0 — Hackathon Submission
### Google Cloud Rapid Agent Hackathon | May–June 2026

---

## Project Title
**NeuroScale 2.0: Autonomous AI SRE Agents for Self-Healing ML Platforms**

## One-Line Pitch
> *"From anomaly detected to Merge Request opened — in under 60 seconds, with zero unsafe changes reaching production."*

---

## The Problem

**Enterprise ML platforms fail silently and expensively.**

When a Kubernetes-hosted inference service breaches its P99 latency SLO at 2 AM:

1. Arize Phoenix fires an alert
2. PagerDuty wakes up the on-call engineer
3. Engineer SSHs in, reads dashboards, consults runbooks manually
4. Engineer edits YAML, opens a PR, waits for review
5. **Resolution time: 30–90 minutes. Cost: $100K+/hour in downtime.**

This is slow, expensive, error-prone, and burns out your best engineers. The industry has automated monitoring — but not remediation. That gap is what NeuroScale 2.0 closes.

---

## The Solution

NeuroScale 2.0 adds an **autonomous agent layer** on top of the NeuroScale ML platform — an existing production-grade Kubernetes/KServe/ArgoCD/Kyverno infrastructure.

**Three specialised AI agents collaborate via Google's Agent-to-Agent (A2A) protocol to detect, diagnose, and remediate incidents automatically:**

```
Arize Phoenix (sensory) → Watcher Agent → Diagnostician Agent → Operator Agent → GitLab MR → ArgoCD → Healed
```

The human is only needed to click **"Approve"** on a fully-prepared, Kyverno-compliant Merge Request — with root cause, runbook reference, and confidence score already filled in.

---

## How It Works

### The Sensory-Motor-Brain-Immune Architecture

| Layer | Component | Role |
|-------|-----------|------|
| **Nervous system** | Arize Phoenix MCP | Senses, perceives, alerts — real-time model observability |
| **Brain** | Diagnostician + RAG | Reasons, grounds in history, plans — Gemini + Vertex AI |
| **Hands** | GitLab MCP | Acts, remediates, commits — infrastructure mutation via GitOps |
| **Immune system** | Kyverno | Rejects unsafe AI actions — non-negotiable governance layer |

---

### Phase 1: Detection — Watcher Agent (`agents/watcher.py`)
- Continuously polls **Arize Phoenix** via MCP (`get_model_metrics`, `list_monitors`, `get_alerts`)
- Evaluates P99 latency, error rate, memory pressure, model drift signals
- Scores severity (CRITICAL / WARNING / INFO) and compiles structured incident report
- Passes to Diagnostician via A2A structured context dict

**Demo output:**
```
🚨 ANOMALY DETECTED | service=demo-iris-2 | latency_p99_ms=1087ms (threshold: 500ms)
   Severity: CRITICAL | Hypothesis: CPU throttling — resource limits too low
   → Handing off to Diagnostician Agent...
```

---

### Phase 2: Diagnosis — Diagnostician Agent (`agents/diagnostician.py`)
- Retrieves additional context from Arize: feature drift scores, explainability data
- Performs **semantic RAG search** over 9 Hermes Skill Documents (SRE runbooks)
  - Production: powered by **Vertex AI Search** 
  - Demo: TF-IDF over `runbooks/` directory — same interface, zero credentials required
- Classifies root cause (CPU_THROTTLING, MODEL_DRIFT, RESOURCE_EXHAUSTION)
- Generates **concrete YAML patch** (KServe InferenceService manifest)
- Assigns confidence score; flags all cases for HITL review
- Builds Kyverno-compliant manifest (resource limits, non-root, labels enforced)

**Demo output:**
```
📖 RB-001 | score=0.847 | CPU Throttling on KServe InferenceService
   Root cause: Predictor pod CPU limits too low for current request volume
   Confidence: 90% | HITL required: Yes
   YAML patch: apps/demo-iris-2/inference-service.yaml
```

---

### Phase 3: Remediation — Operator Agent (`agents/operator_agent.py`)
- Creates Git branch via **GitLab MCP** (`create_branch`)
- Commits the Kyverno-compliant YAML patch (`create_or_update_file`)
- Opens **Merge Request** with structured description including:
  - Root cause summary + runbook reference
  - Kyverno compliance checklist (resource limits, non-root, rolling update)
  - Confidence score + auto-merge eligibility
- Sends **HITL notification** (log + configurable webhook)

**Demo output:**
```
🤖 AGENT CREATED MERGE REQUEST
   MR !41 | fix(INC-1779734283): automated remediation [RB-001]
   URL: https://gitlab.com/neuroscale-platform/-/merge_requests/41
   Status: AWAITING_APPROVAL | HITL notified: Yes
```

---

## Google Cloud Integration

NeuroScale 2.0 is built **on and for Google Cloud**:

| Google Cloud Service | Role in NeuroScale 2.0 |
|---------------------|------------------------|
| **Google ADK** | Agent orchestration framework — A2A protocol implementation |
| **Gemini 1.5 Pro** | Agent reasoning model (production) — root cause analysis |
| **Vertex AI Search** | Production RAG datastore for runbook retrieval |
| **Google Kubernetes Engine (GKE)** | Production cluster runtime for agent pods |
| **Cloud Run** | Production deployment target for each agent |
| **Artifact Registry** | Agent container image storage |

**Demo mode runs locally with zero cloud credentials.** Production mode connects to live GCP services via the same clean interface.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | **Google Agent Development Kit (ADK)** |
| A2A protocol | ADK native structured context |
| Agent model | **Gemini 1.5 Pro** (production) |
| Observability MCP | **Arize Phoenix** (`get_model_metrics`, `list_monitors`, `get_alerts`, `get_feature_drift`, `get_explainability`) |
| Source control MCP | **GitLab REST API v4** (`@zereight/mcp-gitlab` tool schema) |
| Runbook RAG | TF-IDF (demo) / **Vertex AI Search** (production) |
| Policy enforcement | **Kyverno** |
| Inference runtime | **KServe** on GKE |
| GitOps | **ArgoCD** |
| Runtime | Python 3.11 / Cloud Run |

---

## Hackathon Criteria — Explicit Mapping

### ✅ Beyond Chat
NeuroScale 2.0 takes **real infrastructure actions**:
- Creates actual Git branches (`git checkout -b agent/fix-INC-...`)
- Commits actual YAML patches to the repository
- Opens actual Merge Requests with structured descriptions
- This is not a Q&A system — it operates production infrastructure

### ✅ Multi-Step Planning
5-phase autonomous workflow per incident:
1. **Detect** — Arize Phoenix metrics polling via MCP
2. **Diagnose** — RAG-grounded root cause analysis
3. **Plan** — Kyverno-compliant YAML patch generation
4. **Execute** — GitLab branch + commit + MR via MCP
5. **Notify** — HITL webhook + confidence-scored approval request

Each phase is a distinct agent with distinct tools, distinct reasoning, and distinct output schema — connected by ADK's A2A structured context protocol.

### ✅ Partner Power (Dual MCP)
**Arize Phoenix MCP** — 5 tools implemented:
- `get_model_metrics` → anomaly detection
- `list_monitors` → active SLO monitors
- `get_alerts` → fired alert history
- `get_feature_drift` → PSI score monitoring
- `get_explainability` → SHAP feature attribution

**GitLab MCP** — 4 tools implemented (mirrors `@zereight/mcp-gitlab`):
- `create_branch` → isolated fix branch
- `create_or_update_file` → YAML patch commit
- `create_merge_request` → HITL-ready MR
- `list_merge_requests` → audit trail

**This dual-MCP closed loop is unique**: Arize senses the problem, GitLab fixes it. Two partner integrations, one coherent story.

---

## The Kyverno Safety Story — Why This Wins Enterprise

This is the differentiator that takes NeuroScale 2.0 from "cool hack" to "production-ready platform."

> *"Even if our Gemini model hallucinates a catastrophic deployment — no resource limits, root user, privileged container — Kyverno's admission controllers will reject it before it touches the cluster. The AI reasons freely; governance is non-negotiable."*

**Every agent-generated MR includes:**
- Resource limits (`cpu`, `memory`) — required by `require-resource-requests-limits` policy
- Non-root user (`runAsNonRoot: true`) — required by `disallow-root-containers` policy
- Standard labels (`owner`, `cost-center`) — required by `require-standard-labels-inferenceservice` policy
- Rolling update strategy — required by `rolling-update-strategy` policy

The AI doesn't bypass governance. Governance is a first-class citizen of the agent's reasoning.

---

## Competitive Advantages Over 10,900 Participants

| Competitor Type | Their Weakness | NeuroScale 2.0 Edge |
|----------------|---------------|---------------------|
| **Chatbot builders** | Fail "Beyond Chat" — no real actions | Real GitLab MRs, real cluster operations |
| **Single-agent teams** | Linear execution, no A2A | 3-phase A2A topology with structured handoffs |
| **Single MCP teams** | Limited partner integration | Dual-MCP closed sensory-motor loop |
| **Infrastructure teams** | Build solid but can't tell the story | Sensory-motor-brain-immune narrative instant |
| **Cloud-native teams** | Start from zero for hackathon | Extending a production-grade platform |

**The decisive edge**: NeuroScale 2.0 extends a *real, working, production-grade platform* with a *real, working agent layer*. This is not a prototype — it's demonstrably deployable today.

---

## Demo — Zero Credentials Required

### Fastest path (30 seconds):
```bash
git clone https://github.com/sodiq-code/neuroscale-platform
cd neuroscale-platform
pip install httpx scikit-learn

# Full verification suite
bash scripts/verify-all.sh      # → 7/7 PASS

# Cinematic 10-beat demo
bash scripts/demo-run.sh        # → full A2A pipeline end-to-end
```

### What you'll see:
1. Three agents boot online
2. System polls Arize Phoenix — healthy baseline confirmed
3. Failure injected (P99 latency spike)
4. Watcher detects anomaly via Arize MCP
5. Diagnostician retrieves matching runbook via RAG
6. YAML patch generated (Kyverno-compliant manifest)
7. GitLab branch created, YAML committed, MR opened
8. HITL notification sent with confidence score
9. Cluster ready for human approval → ArgoCD sync → healed
10. Total time: < 60 seconds

### Production mode:
```bash
export ARIZE_API_KEY=your_key
export ARIZE_SPACE_ID=your_space
export GITLAB_TOKEN=your_token
export GITLAB_PROJECT_ID=your_project_id
export DEMO_MODE=false

python3 agents/orchestrator.py --watch --interval 30
```

---

## Enterprise Value

| Metric | Before (Manual SRE) | After (NeuroScale 2.0) |
|--------|---------------------|------------------------|
| Detection-to-MR time | 30–90 minutes | **< 60 seconds** |
| On-call disruptions | Every incident | **Approval only** |
| Runbook compliance | Ad-hoc, inconsistent | **100% enforced via RAG** |
| Kyverno policy coverage | Manual audit | **Automated in every MR** |
| Mean time to resolution (MTTR) | 30–90 min | **5–10 min (after approval)** |
| Incident documentation | Manual, often skipped | **Auto-generated in every MR** |
| Engineer burnout risk | High (2 AM pages) | **Dramatically reduced** |

---

## What's Next

- **Auto-merge with confidence threshold** — fully autonomous remediation for P(correct) > 0.95
- **Multi-cluster Watcher** — fleet-wide anomaly detection across GKE regions
- **Incident memory (vector DB)** — RAG improves as it learns from past incidents
- **Slack/Teams HITL bot** — one-click approve/reject from your phone
- **Vertex AI Evaluation** — trajectory_exact_match scoring of agent decisions
- **Cost attribution** — every MR tagged with estimated cost-of-incident-averted

---

## Repository Structure

```
neuroscale-platform/
├── agents/
│   ├── config.py              # Centralised config (DEMO_MODE=true default)
│   ├── watcher.py             # Watcher Agent — Arize anomaly detection
│   ├── diagnostician.py       # Diagnostician Agent — RAG + YAML patch
│   ├── operator_agent.py      # Operator Agent — GitLab MCP + HITL
│   ├── orchestrator.py        # A2A Orchestrator (run_once / run_continuous)
│   ├── tools/
│   │   ├── arize_mcp.py       # Arize Phoenix MCP (5 tools + demo injection)
│   │   ├── gitlab_mcp.py      # GitLab MCP (4 tools, REST v4 schema)
│   │   └── rag_store.py       # RAG store (TF-IDF demo / Vertex AI prod)
│   └── demo/
│       ├── inject_failure.sh  # 4-scenario failure injection
│       └── reset_demo.sh      # Reset to clean baseline
├── runbooks/                  # 9 Hermes Skill Documents (RAG corpus)
│   ├── RB-001-cpu-throttling-kserve.md
│   ├── RB-002-model-drift-rollback.md
│   ├── RB-005-kserve-not-ready.md
│   ├── RB-007-argocd-sync-recovery.md
│   └── RB-009-kyverno-policy-debugging.md
├── docs/
│   ├── ARCHITECTURE_2_0.md    # System architecture + Mermaid diagram
│   ├── DEMO_SCRIPT.md         # 10-beat narration for video
│   ├── HACKATHON_SUBMISSION.md
│   └── JUDGING.md             # Criterion → code location map
├── scripts/
│   ├── verify-all.sh          # 7/7 self-test suite
│   └── demo-run.sh            # Cinematic demo runner
└── infrastructure/
    └── agents/
        └── deployment.yaml    # GKE/Cloud Run K8s manifest
```

---

## Team

**Sodiq Jimoh** — Platform Engineer  
Repository: `sodiq-code/neuroscale-platform`  
Hackathon: **Google Cloud Rapid Agent Hackathon** (GitLab + Arize tracks)  
Submission deadline: June 11, 2026
