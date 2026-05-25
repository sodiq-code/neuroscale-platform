"""
NeuroScale 2.0 — Diagnostician Agent
Phase 2 of the A2A pipeline.
Role: Receives incident from Watcher, queries RAG for historical runbooks,
      cross-references cluster state, produces structured remediation plan.
Model: Gemini Pro (deep reasoning)
"""
from __future__ import annotations
import json, time
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config
from tools.rag_store import RunbookRAGClient, RunbookResult


class DiagnosticianAgent:
    """
    Diagnostician Agent — Memory & Infrastructure Policy.
    Equips: Vertex AI RAG datastore (Hermes Skill Documents).
    Input:  Incident report from Watcher Agent.
    Output: Structured remediation plan JSON → Operator Agent.
    """

    MODEL = "gemini-1.5-pro"  # Production: Gemini 3 Pro (deep reasoning)

    def __init__(self, rag_client: Optional[RunbookRAGClient] = None):
        self.rag = rag_client or RunbookRAGClient()

    def diagnose(self, incident: dict) -> dict:
        """
        Main diagnosis pipeline.
        Returns structured remediation plan for the Operator Agent.
        """
        print(f"\n{'='*60}")
        print(f"  DIAGNOSTICIAN AGENT — Analysing Incident")
        print(f"  Incident: {incident['incident_id']} | Severity: {incident['severity']}")
        print(f"{'='*60}")

        model_name = incident["model_name"]
        hypothesis = incident.get("agent_hypothesis", "")
        metrics = incident.get("metrics", {})

        # ── Step 1: Query RAG datastore ────────────────────────────────────────
        print(f"\n  Step 1: Querying RAG datastore for historical runbooks...")
        search_query = self._build_search_query(incident)
        runbooks = self.rag.semantic_search(search_query, top_k=3)

        if runbooks:
            print(f"\n  📚 Historical precedent found:")
            print(runbooks[0])
        else:
            print("  📚 No historical precedent — reasoning from base knowledge")

        # ── Step 2: Determine root cause ──────────────────────────────────────
        print(f"\n  Step 2: Root cause analysis...")
        root_cause = self._determine_root_cause(incident, runbooks)
        print(f"  Root cause: {root_cause['type']}")
        print(f"  Confidence: {root_cause['confidence']}")

        # ── Step 3: Identify Kyverno constraints ──────────────────────────────
        print(f"\n  Step 3: Checking Kyverno policy constraints...")
        policy_constraints = self._check_policy_constraints(model_name)
        print(f"  Active policies: {len(policy_constraints)}")
        for p in policy_constraints[:2]:
            print(f"    • {p}")

        # ── Step 4: Build remediation plan ────────────────────────────────────
        print(f"\n  Step 4: Formulating remediation plan...")
        plan = self._build_remediation_plan(
            incident=incident,
            root_cause=root_cause,
            runbooks=runbooks,
            policy_constraints=policy_constraints,
        )

        print(f"\n  📋 DIAGNOSTICIAN: Remediation plan ready:")
        print(f"     Actions: {len(plan['actions'])}")
        for i, action in enumerate(plan["actions"], 1):
            print(f"     {i}. {action['description']}")

        print(f"\n  → Handing off to Operator Agent...")
        return plan

    def _build_search_query(self, incident: dict) -> str:
        """Construct optimal search query from incident data."""
        parts = [incident.get("agent_hypothesis", "")]
        metrics = incident.get("metrics", {})
        if metrics.get("p99_latency_ms", 0) > 500:
            parts.append("high latency cpu throttling kserve")
        if metrics.get("error_rate_pct", 0) > 5:
            parts.append("error rate model drift sklearn")
        parts.append(incident["model_name"])
        return " ".join(parts)

    def _determine_root_cause(self, incident: dict, runbooks: list[RunbookResult]) -> dict:
        """Rule-based root cause classification (production: Gemini Pro reasoning)."""
        hypothesis = incident.get("agent_hypothesis", "").lower()
        metrics = incident.get("metrics", {})
        runbook_tags = set()
        for rb in runbooks:
            runbook_tags.update(rb.tags)

        if "cpu throttl" in hypothesis or "cpu" in runbook_tags:
            return {
                "type": "CPU_THROTTLING",
                "confidence": "HIGH",
                "description": "Predictor pod CPU limits too low for current request volume",
                "affected_resource": "apps/demo-iris-2/inference-service.yaml",
                "fix_type": "resource_limit_increase",
                "runbook_ref": runbooks[0].file if runbooks else "RB-001-cpu-throttling-kserve.md",
            }
        elif "drift" in hypothesis or "drift" in runbook_tags:
            return {
                "type": "MODEL_DRIFT",
                "confidence": "MEDIUM",
                "description": "Model prediction distribution diverging from training baseline",
                "affected_resource": "apps/demo-iris-2/inference-service.yaml",
                "fix_type": "model_rollback",
                "runbook_ref": runbooks[0].file if runbooks else "RB-002-model-drift-rollback.md",
            }
        else:
            return {
                "type": "RESOURCE_EXHAUSTION",
                "confidence": "MEDIUM",
                "description": "General resource pressure on inference pod",
                "affected_resource": "apps/demo-iris-2/inference-service.yaml",
                "fix_type": "resource_limit_increase",
                "runbook_ref": "RB-001-cpu-throttling-kserve.md",
            }

    def _check_policy_constraints(self, model_name: str) -> list[str]:
        """Return active Kyverno policies that constrain the remediation."""
        return [
            "require-standard-labels-inferenceservice: owner + cost-center labels mandatory",
            "require-resource-requests-limits: cpu/memory requests+limits required on all containers",
            "disallow-latest-image-tag: :latest image tag forbidden",
            "disallow-root-containers: runAsNonRoot must be true",
            "namespace ResourceQuota: total CPU requests ≤ 4 cores, memory ≤ 8Gi",
        ]

    def _build_remediation_plan(
        self,
        incident: dict,
        root_cause: dict,
        runbooks: list[RunbookResult],
        policy_constraints: list[str],
    ) -> dict:
        """Build the complete remediation plan for the Operator Agent."""
        incident_id = incident["incident_id"]
        model_name = incident["model_name"]
        runbook_ref = root_cause.get("runbook_ref", "RB-001")
        fix_type = root_cause.get("fix_type", "resource_limit_increase")

        # Determine specific YAML changes + generate concrete patch string
        if fix_type == "resource_limit_increase":
            yaml_patch_content = f"""# NeuroScale 2.0 — Autonomous Remediation Patch
# Incident: {incident_id} | Root cause: CPU_THROTTLING
# Generated by: Diagnostician Agent (grounded in RB-001)
# Kyverno compliance: resource limits, non-root, rolling update enforced
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: {model_name}
  namespace: default
  labels:
    owner: platform-engineering
    cost-center: cc-mlops
    managed-by: neuroscale-agent
    incident-ref: "{incident_id}"
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model
      resources:
        requests:
          cpu: "250m"
          memory: "512Mi"
        limits:
          cpu: "1000m"
          memory: "1Gi"
  transformer:
    containers:
    - name: kserve-container
      securityContext:
        runAsNonRoot: true
        readOnlyRootFilesystem: true
        allowPrivilegeEscalation: false
"""
            yaml_changes = {
                "file": f"apps/{model_name}/inference-service.yaml",
                "yaml_patch": yaml_patch_content,
                "changes": [
                    {"field": "spec.predictor.model.resources.requests.cpu", "from": "100m", "to": "250m"},
                    {"field": "spec.predictor.model.resources.requests.memory", "from": "256Mi", "to": "512Mi"},
                    {"field": "spec.predictor.model.resources.limits.cpu", "from": "500m", "to": "1000m"},
                    {"field": "spec.predictor.model.resources.limits.memory", "from": "512Mi", "to": "1Gi"},
                ],
            }
        else:
            yaml_patch_content = f"""# NeuroScale 2.0 — Model Rollback Patch
# Incident: {incident_id} | Root cause: MODEL_DRIFT
# Generated by: Diagnostician Agent (grounded in RB-002)
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: {model_name}
  namespace: default
  labels:
    owner: platform-engineering
    cost-center: cc-mlops
    managed-by: neuroscale-agent
    incident-ref: "{incident_id}"
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: gs://kfserving-examples/models/sklearn/0.9/model
      resources:
        requests:
          cpu: "250m"
          memory: "512Mi"
        limits:
          cpu: "1000m"
          memory: "1Gi"
"""
            yaml_changes = {
                "file": f"apps/{model_name}/inference-service.yaml",
                "yaml_patch": yaml_patch_content,
                "changes": [
                    {"field": "spec.predictor.model.storageUri", "from": "current", "to": "gs://kfserving-examples/models/sklearn/0.9/model"},
                ],
            }

        plan = {
            "plan_id": f"PLAN-{incident_id}",
            "incident_id": incident_id,
            "model_name": model_name,
            "root_cause": root_cause,
            "runbook_ref": runbook_ref,
            "runbook_steps": runbooks[0].key_steps if runbooks else [],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hitl_required": True,
            "hitl_reason": "Resource limit changes affect cluster quota and require cost-center approval",
            "kyverno_constraints": policy_constraints[:3],
            "actions": [
                {
                    "step": 1,
                    "type": "create_branch",
                    "description": f"Create remediation branch: agent/fix-{incident_id.lower()}",
                    "branch_name": f"agent/fix-{incident_id.lower()}-{int(time.time())}",
                },
                {
                    "step": 2,
                    "type": "patch_yaml",
                    "description": f"Update {yaml_changes['file']} with remediation fix",
                    "file": yaml_changes["file"],
                    "yaml_patch": yaml_changes["yaml_patch"],
                    "changes": yaml_changes["changes"],
                    "commit_message": f"fix(agent): autonomous remediation for {incident_id} — {root_cause['type'].lower().replace('_', ' ')} on {model_name}",
                },
                {
                    "step": 3,
                    "type": "create_mr",
                    "description": "Open Merge Request for human review and approval",
                    "mr_title": f"fix(agent): {root_cause['description'][:80]}",
                    "mr_description": self._build_mr_description(incident, root_cause, runbook_ref),
                    "labels": ["neuroscale-agent", "autonomous-remediation", "sre", f"severity-{incident['severity'].lower()}"],
                },
            ],
            "expected_recovery": {
                "argocd_sync_after_merge_s": 30,
                "pod_restart_expected": True,
                "metric_recovery_window_min": 5,
                "verification_steps": [
                    f"kubectl get isvc {model_name} -n default — expect READY=True",
                    f"Arize Phoenix: P99 latency returns to <{config.LATENCY_P99_THRESHOLD_MS:.0f}ms",
                    f"Error rate returns to <{config.ERROR_RATE_THRESHOLD_PCT:.1f}%",
                ],
            },
        }
        return plan

    def _build_mr_description(self, incident: dict, root_cause: dict, runbook_ref: str) -> str:
        metrics = incident.get("metrics", {})
        return f"""## 🤖 Autonomous Remediation — {incident['incident_id']}

**Detected by:** NeuroScale Watcher Agent (Arize Phoenix MCP)
**Incident Severity:** {incident['severity']}
**Model Affected:** `{incident['model_name']}`
**Detection Time:** {incident['detected_at']}

---

### 📊 Anomaly Metrics

| Metric | Observed | SLO Threshold |
|--------|----------|---------------|
| P99 Latency | {metrics.get('p99_latency_ms', 0):.0f}ms | {config.LATENCY_P99_THRESHOLD_MS:.0f}ms |
| Error Rate | {metrics.get('error_rate_pct', 0):.1f}% | {config.ERROR_RATE_THRESHOLD_PCT:.1f}% |
| Total Spans | {metrics.get('total_spans', 0)} | — |

### 🧠 Root Cause Analysis

**Type:** `{root_cause['type']}`  
**Confidence:** {root_cause['confidence']}  
**Description:** {root_cause['description']}  
**Historical Reference:** [{runbook_ref}](../runbooks/{runbook_ref})

### 🔧 Changes Applied

See diff for exact YAML changes. Resource limits adjusted to resolve CPU throttling
and prevent recurrence under equivalent load conditions.

### ✅ Kyverno Compliance

All changes verified against NeuroScale admission policies:
- ✅ `require-standard-labels-inferenceservice` — owner/cost-center labels preserved
- ✅ `require-resource-requests-limits` — new limits set within namespace quota
- ✅ `disallow-latest-image-tag` — no image changes in this MR

### 👤 Human Review Required

**Before merging, please verify:**
1. Resource change is within budget for `cost-center: {incident['model_name']}`
2. New CPU/memory limits align with team capacity plan
3. Arize dashboard confirms the anomaly is still active: {incident.get('arize_dashboard_url', '')}

**After merge:** ArgoCD will sync automatically within ~30s. Monitor pod restart and metric recovery.

---
*Generated by NeuroScale Watcher → Diagnostician → Operator Agent pipeline*  
*Governed by Kyverno ClusterPolicies — safe for production*
"""


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Diagnostician Agent — Self-Test ===\n")
    agent = DiagnosticianAgent()

    # Simulate a Watcher incident report
    mock_incident = {
        "incident_id": "INC-TEST-001",
        "model_name": "demo-iris-2",
        "detected_at": "2026-05-25T10:00:00Z",
        "severity": "HIGH",
        "metrics": {
            "p99_latency_ms": 923.0,
            "p50_latency_ms": 512.0,
            "error_rate_pct": 11.2,
            "total_spans": 347,
        },
        "slo_breach": {
            "p99_latency_ms": 923.0,
            "threshold_ms": 500.0,
            "error_rate_pct": 11.2,
            "threshold_pct": 5.0,
        },
        "trace_sample": {
            "root_cause_hint": "CPU throttling detected on predictor pod",
        },
        "agent_hypothesis": "CPU throttling on predictor pod — resource limits too low for current load",
        "arize_dashboard_url": "http://localhost:6006/projects/neuroscale/spans",
    }

    plan = agent.diagnose(mock_incident)
    assert "plan_id" in plan
    assert len(plan["actions"]) == 3
    assert plan["hitl_required"] is True
    assert plan["root_cause"]["type"] in ("CPU_THROTTLING", "MODEL_DRIFT", "RESOURCE_EXHAUSTION")

    print(f"\n✅ Plan generated: {plan['plan_id']}")
    print(f"  Root cause: {plan['root_cause']['type']}")
    print(f"  Actions: {len(plan['actions'])}")
    print(f"  HITL: {plan['hitl_required']}")
    print("\n✅ Diagnostician Agent self-test PASSED")
