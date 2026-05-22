# NeuroScale — Video Demo Guide

> **Recommendation:** Record a single-take, unedited terminal video of `bash scripts/smoke-test.sh`. Let the test speak for itself.
>
> **Reference recording:** `assets/smoke-test-demo.mp4` — a pre-recorded single-take terminal proof of the full smoke-test run (PASS 21 / FAIL 0).

---

## Why This Approach

The smoke test IS the demo. It validates every milestone automatically:

| Time | What Judges See |
|------|----------------|
| 0:00–0:05 | `bash scripts/smoke-test.sh` typed and executed |
| 0:05–0:15 | Prerequisites pass — cluster is reachable |
| 0:15–0:45 | Milestone A: GitOps spine — ArgoCD healthy, drift self-heal in ~20s |
| 0:45–1:10 | Milestone B: AI serving — KServe ready, prediction returns `{"predictions":[1,1]}` |
| 1:10–1:30 | Milestone C: Golden Path — Backstage up, scaffolder output exists |
| 1:30–2:00 | Milestone D: Guardrails — Kyverno denies non-compliant manifest live |
| 2:00–2:30 | Milestone F: Production hardening — ApplicationSet, quotas, OpenCost, root-container denial |
| 2:30–2:40 | Final results: **PASS 21 / FAIL 0 / SKIP 1** |

No editing. No narration. No flashy transitions. The terminal output is the mathematical proof.

---

## How to Record

### Option 1: asciinema (Terminal Recording)

```bash
# Install
pip install asciinema

# Record
asciinema rec demo.cast -c "bash scripts/smoke-test.sh"

# Upload (public link)
asciinema upload demo.cast
```

### Option 2: Screen Recording (for DEV post embed)

```bash
# On macOS: Cmd+Shift+5 → Record selected area → select terminal
# On Linux: OBS Studio or SimpleScreenRecorder
# On Windows: Win+G → Record

# Steps:
# 1. Maximize terminal window
# 2. Start recording
# 3. Type: bash scripts/smoke-test.sh
# 4. Let it run to completion
# 5. Stop recording
```

### Option 3: Quick Validation (No Recording)

```bash
# Just run it — the output itself is the proof
bash scripts/smoke-test.sh

# Paste the output into your DEV post as a code block
```

---

## Key Rules

1. **Single take** — no cuts, no edits
2. **Show the command being typed** — judges need to see `bash scripts/smoke-test.sh`
3. **Let the full output scroll** — every PASS line builds confidence
4. **End on the summary** — `PASS 21 / FAIL 0` is your closing argument
5. **Under 3 minutes** — the smoke test itself runs in ~2 minutes

---

## Pre-Recording Checklist

```bash
# Ensure cluster is healthy
kubectl cluster-info

# Ensure all pods converged (wait 2-3 min after bootstrap)
kubectl -n argocd get applications

# Clear terminal
clear

# Record
bash scripts/smoke-test.sh
```
