# NeuroScale 2.0 — Demo Script
### 10-Beat Narration for Video Recording

> **Total runtime:** ~4 minutes  
> **Run alongside:** `bash scripts/demo-run.sh`  
> **Key message:** Zero-touch incident response — detection to MR in under 60 seconds

---

## Beat 1: The Problem (0:00 – 0:25)

> *Show: slide or title card*

"It's 2 AM. Your inference engine just blew past its P99 latency SLO. Your on-call engineer gets paged. They SSH in, check dashboards, read through a runbook, manually edit a YAML file, open a PR, wait for review. Forty minutes later, the incident is resolved.
  
**We built NeuroScale 2.0 to make that story obsolete.**"

---

## Beat 2: System Boot (0:25 – 0:45)

> *Show: terminal, `bash scripts/demo-run.sh` running*

"Three autonomous agents come online — a Watcher, a Diagnostician, and an Operator. They communicate via Google's Agent-to-Agent protocol. No humans in the detection-to-fix loop."

```
  ● Watcher Agent       … ready
  ● Diagnostician Agent … ready
  ● Operator Agent      … ready
  ● A2A Orchestrator    … ready
```

---

## Beat 3: Normal Baseline (0:45 – 1:00)

> *Show: first poll output — no anomalies*

"The system starts healthy. Watcher polls Arize Phoenix — all metrics within SLO bounds. No action taken. This is the happy path."

---

## Beat 4: Inject the Failure (1:00 – 1:20)

> *Show: inject_failure.sh output*

"Now we simulate a production incident. We inject a P99 latency spike — 1850 milliseconds, against an 800ms threshold. This is the kind of event that would wake up your team at 2 AM."

```
💥 Injecting failure: inference-engine latency_p99_ms → 1850ms
   (threshold: 800ms | SLO breach imminent)
```

---

## Beat 5: Watcher Detects (1:20 – 1:40)

> *Show: Watcher output with 🚨 anomaly*

"Within seconds, the Watcher agent detects the anomaly via Arize Phoenix's MCP interface. It scores the severity as **critical** and passes the structured anomaly object to the Diagnostician."

```
🚨 ANOMALY  service=inference-engine  metric=latency_p99_ms  value=1850.0  threshold=800.0
```

---

## Beat 6: RAG Runbook Retrieval (1:40 – 2:00)

> *Show: RAG search results*

"The Diagnostician doesn't guess. It searches our runbook library using TF-IDF semantic retrieval — in production, powered by Vertex AI Search. It finds the best-matching runbook in milliseconds."

```
📄 RB-001    score=0.847  High Latency — HPA Scaling Limit
📄 RB-002    score=0.412  OOM Kill — Memory Pressure Diagnosis
📄 RB-005    score=0.231  Model Drift — PSI Score Breach
```

---

## Beat 7: Root Cause Analysis (2:00 – 2:25)

> *Show: Diagnostician output with diagnosis and plan*

"Runbook RB-001 matches. The Diagnostician synthesises the root cause: the HPA has hit its ceiling because resource limits are missing from the deployment spec. Confidence: 91%. It generates the exact YAML patch needed."

```
🔍 Root cause  : HPA ceiling hit; pods cannot scale due to missing resource limits
📖 Runbook     : RB-001
🎯 Confidence  : 91.0%
   ✓ Add cpu/memory resource limits to deployment.yaml
   ✓ Lower HPA minReplicas to 3
   ✓ Verify Kyverno policy compliance
```

---

## Beat 8: Operator Executes (2:25 – 2:55)

> *Show: Operator output with branch, commit, MR URL*

"The Operator agent takes over. It creates a Git branch, commits the YAML fix — **with a Kyverno compliance checklist baked into the MR description** — and opens a Merge Request. All autonomously."

```
⚙️  Branch  : agent/fix-INC-DEMO-1748188800
📝 Commit  : a1b2c3d
🔀 MR URL  : https://gitlab.com/demo/neuroscale/-/merge_requests/42
🔔 Status  : AWAITING_APPROVAL
```

---

## Beat 9: HITL Gate (2:55 – 3:15)

> *Show: HITL notification payload*

"We're not fully removing the human. We're removing the human from the **detection and investigation** steps. The MR is ready to review — not to investigate. The on-call engineer clicks approve, not SSH."

```
🔔 HITL NOTIFICATION SENT
   incident_id: INC-DEMO-1748188800
   mr_url: https://gitlab.com/demo/neuroscale/-/merge_requests/42
   confidence: 0.910
   auto_merge_in: Yes (confidence > 90%) — 15 minute SLA
```

---

## Beat 10: The Punchline (3:15 – 3:45)

> *Show: summary box*

"Detection-to-MR: under 60 seconds. Zero lines of runbook manually executed. Kyverno compliance enforced automatically. And when confidence exceeds 90%, the system can auto-merge within a 15-minute SLA window — while the on-call engineer sleeps.

**This is NeuroScale 2.0.**"

```
╔══════════════════════════════════════════════════════════════════╗
║  ✅ DEMO COMPLETE                                                ║
║                                                                  ║
║  Watcher → Diagnostician → Operator → HITL                      ║
║  Detection-to-MR: < 60 seconds                                  ║
║  Human effort: 0 lines of runbook manually executed             ║
║  Kyverno compliance: enforced automatically                     ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Q&A Prep

**Q: What happens if the agent is wrong?**  
A: Confidence gate — anything under 90% is flagged for mandatory human review. The MR is opened, the human decides. The agent can never break production unilaterally.

**Q: How does it know which runbook to use?**  
A: TF-IDF semantic search over our runbook library in demo mode; Vertex AI Search in production. Same interface, swappable backend.

**Q: What about security?**  
A: Every MR includes a Kyverno compliance checklist. The agent enforces `runAsNonRoot`, resource limits, and rolling update strategy in every commit.

**Q: Does this work without live credentials?**  
A: Yes. `DEMO_MODE=true` (the default) runs the entire pipeline without Arize or GitLab credentials — anomalies are simulated, MRs are returned as realistic demo objects.

**Q: How does A2A work?**  
A: In demo, agents communicate via direct Python calls in a single process. In production, each agent is a Cloud Run service with an ADK-compatible REST endpoint. The orchestrator is the A2A coordinator.
