# NeuroScale 2.0 — Hackathon Build Task

## Goal
Win Google Cloud Rapid Agent Hackathon (June 11, 2026) — GitLab + Arize buckets

## Winning Core (must all work perfectly)
- [x] GitOps remediation loop (ArgoCD) — EXISTS
- [x] Kyverno governance — EXISTS
- [x] KServe inference — EXISTS
- [ ] Arize MCP — Watcher Agent (NEW)
- [ ] GitLab MCP — Operator Agent (NEW)
- [ ] A2A multi-agent orchestrator (NEW)
- [ ] RAG memory from Hermes runbooks (NEW)
- [ ] HITL approval flow (NEW)
- [ ] Cinematic demo script (NEW)
- [ ] Devpost submission assets (NEW)

## What We're Building (NeuroScale 2.0)
```
agents/
├── orchestrator.py         # ADK orchestrator — Watcher→Diagnostician→Operator
├── watcher.py              # Arize MCP poller — anomaly detection
├── diagnostician.py        # RAG query + remediation plan
├── operator.py             # GitLab MCP — creates branch + MR
├── tools/
│   ├── arize_mcp.py        # Arize Phoenix MCP client
│   ├── gitlab_mcp.py       # GitLab MCP client
│   └── rag_store.py        # Vertex AI RAG / local runbook search
├── config.py               # All env vars
└── demo/
    ├── inject_failure.sh   # Simulate latency spike / model drift
    ├── seed_data.py        # Pre-seed Arize with anomaly traces
    └── reset_demo.sh       # Reset cluster to clean state

runbooks/                   # Hermes Skill Documents for RAG
scripts/
├── demo-run.sh             # Full cinematic demo runner
└── verify-all.sh           # Phase-by-phase verification

infrastructure/agents/      # Kubernetes manifests for agent deployment
docs/
├── HACKATHON_SUBMISSION.md
├── DEMO_SCRIPT.md
└── ARCHITECTURE_2_0.md
```

## Phases
1. Agent framework (orchestrator + mocked tools) — verify imports clean
2. Arize MCP client (Phoenix API) — verify anomaly detection works
3. GitLab MCP client (REST API) — verify MR creation works
4. RAG/runbook search — verify retrieval returns relevant runbook
5. Full A2A flow end-to-end — verify 10-beat demo runs deterministically
6. Demo hardening — inject failure, recover, repeat 10x
7. Submission assets — README, architecture diagram, JUDGING.md, Devpost copy
