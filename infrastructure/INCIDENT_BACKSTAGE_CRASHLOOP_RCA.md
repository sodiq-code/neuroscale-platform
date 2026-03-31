# Incident Report: Backstage CrashLoopBackOff (RCA)

- Incident ID: NS-INC-2026-02-17-01
- Date: 2026-02-17
- Environment: k3d (local), namespace `backstage`
- Service: Backstage (`neuroscale-backstage`)
- Severity: SEV-2 (core developer portal unavailable/intermittent)
- Status: Resolved

---

## 1) Executive Summary

Backstage repeatedly restarted with `CrashLoopBackOff` after deployment changes. PostgreSQL remained healthy. The primary cause was incorrect Helm values hierarchy for a dependency chart, which prevented probe/resource tuning from being applied. Kubernetes then used default probe timings that were too aggressive for Backstage startup. After correcting values nesting and hardening probe/image settings, rollout converged and Backstage stabilized.

---

## 2) Business / Platform Impact

- Backstage UI/API unstable during the incident window.
- GitOps app health remained in progressing/degraded state during failing rollouts.
- Developer portal availability reduced until corrected rollout completed.

---

## 3) Detection

Detected by pod watch:

- `kubectl get pods -n backstage -w`
- Observed repeated restarts on Backstage pod (`CrashLoopBackOff` / restart count incrementing)

Corroborated by:

- Pod events (`Startup probe failed: connect: connection refused`)
- Deployment manifest showing default probe timings before fix

---

## 4) Root Cause Analysis (RCA)

### Primary Root Cause

Incorrect values path in parent Helm chart for dependency overrides.

- Parent chart key: `backstage` (dependency alias/name)
- Actual dependency values must be under: `backstage.backstage.*`
- Misconfigured earlier as: `backstage.appConfig` and `backstage.backend.*`

Effect:

- Intended custom probe/resource settings were ignored.
- Deployment used chart defaults (`startup/readiness/liveness` too strict for startup behavior).
- Pod restarted before app became healthy.

### Contributing Factors

1. Floating image tag (`latest`) increased variability risk.
2. Manual pod deletions during active rollout made symptom interpretation noisier.
3. No pre-sync rendered-manifest gate to verify probe/resource values in final Deployment.

---

## 5) Evidence Collected

1. Argo CD synced target revision successfully (GitOps path valid).
2. Live Deployment initially still showed default probes (proof values were not applied).
3. Pod describe showed startup probe failures and restart cycles.
4. After corrected nesting, Deployment revision changed and new ReplicaSet hash appeared.
5. New pod reached `1/1 Running` with `0` restarts.

---

## 6) Corrective Actions Implemented

Applied in [infrastructure/backstage/values.yaml](backstage/values.yaml#L1-L43):

1. Corrected hierarchy to dependency scope:
   - `backstage.backstage.appConfig`
   - `backstage.backstage.resources`
   - `backstage.backstage.startupProbe`
   - `backstage.backstage.readinessProbe`
   - `backstage.backstage.livenessProbe`

2. Probe hardening:
   - `startupProbe.initialDelaySeconds: 120`
   - `startupProbe.failureThreshold: 30`
   - `readinessProbe.initialDelaySeconds: 120`
   - `livenessProbe.initialDelaySeconds: 300`

3. Resource requests:
   - `cpu: 100m`
   - `memory: 512Mi`

4. Rollout/image stability:
   - Pinned image by digest
   - `pullPolicy: IfNotPresent`
   - `revisionHistoryLimit: 2`
   - `replicas: 1`

Supporting chart metadata reference: [infrastructure/backstage/Chart.yaml](backstage/Chart.yaml)

---

## 7) Validation Performed

- Verified live Deployment reflects custom probe/resource values.
- Verified new ReplicaSet created from corrected pod template.
- Verified old crashing pod terminated during rollout overlap.
- Final observed steady state:
  - Backstage: `1/1 Running`, restarts `0`
  - PostgreSQL: `1/1 Running`

---

## 8) Why “Same Issue” Appeared Briefly After Fix

During rolling update, old and new ReplicaSets coexisted:

- Old pod continued restarting until terminated.
- New pod took over and became healthy.

This overlap is expected and can look like a persistent failure if only watching restart lines without ReplicaSet transition context.

---

## 9) Preventive Actions (Required)

### CI/CD Guardrails

1. Add a pre-merge `helm template` check and assert final Deployment contains expected probe/resource fields.
2. Add a schema/path check for dependency values (`backstage.backstage.*`) to prevent mis-nesting.
3. Block use of floating `latest` in production-like overlays; require digest/tag pinning.

### Operational Guardrails

1. Avoid deleting all pods during rollout diagnosis unless explicitly required.
2. Diagnose using this order:
   - Argo sync revision
   - Live Deployment spec
   - Pod events/logs
   - ReplicaSet transition

---

## 10) Follow-up Tasks

- [ ] Add CI validation for rendered manifest probes/resources.
- [ ] Add GitOps runbook section to infrastructure docs.
- [ ] Add policy/check preventing dependency mis-nesting regressions.
- [ ] Consider separate values profiles (`dev`, `staging`, `prod`) with explicit probe defaults.

---

## 11) Runbook (Fast Triage)

1. `kubectl get pods -n backstage -w`
2. `kubectl describe pod -n backstage <pod>`
3. `kubectl logs -n backstage <pod> --previous --tail=200`
4. `kubectl get deploy neuroscale-backstage -n backstage -o yaml`
5. Verify expected values source in [infrastructure/backstage/values.yaml](backstage/values.yaml)
6. Verify dependency mapping in [infrastructure/backstage/Chart.yaml](backstage/Chart.yaml)

---

## 12) Final Resolution Statement

Incident resolved by correcting Helm dependency values hierarchy and tuning startup/readiness/liveness behavior to match Backstage initialization characteristics. Deployment converged successfully and service returned to stable operation.
