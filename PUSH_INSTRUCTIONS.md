# Push Instructions

Two commits need to be pushed to `https://github.com/sodiq-code/neuroscale-platform`:

```bash
cd /path/to/neuroscale-platform

# Set up credentials (use your GitHub PAT)
git remote set-url origin https://<YOUR_TOKEN>@github.com/sodiq-code/neuroscale-platform.git

# Push both commits
git push origin main
```

## What's in the commits

### Commit 1: `558ee4c` — Main submission assets
- `BEFORE.md` + `AFTER.md` — transformation narrative
- `DEMO_CHEATSHEET.md` — deterministic demo sequence
- `SOCIAL_MEDIA.md` — LinkedIn, Twitter, Discord copy
- `docs/runbook.md` — operational runbook
- `docs/COPILOT_MOMENT_1_ARCHITECTURE.md`
- `docs/COPILOT_MOMENT_2_CI_GUARDRAILS.md`
- `docs/COPILOT_MOMENT_3_OPERATIONAL_RECOVERY.md`
- `assets/*.png` — 8 visual assets

### Commit 2: `a45fae6` — Video demo guide
- `VIDEO_DEMO.md` — single-take recording instructions
- `assets/smoke-test-demo.mp4` — reference terminal recording
