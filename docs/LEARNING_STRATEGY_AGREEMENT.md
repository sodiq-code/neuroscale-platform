# NeuroScale Learning Strategy Agreement

This document captures the learning/teaching method agreed for this project so execution does not drift into "just fixing" mode.

## Core agreement

1. Build and learning are equal goals.
2. Every week closes with a learning review, not only code changes.
3. Explanations must cover what, why, and trade-offs (not only commands).
4. Proof is required: each claim must map to observable evidence.

## Working mode

### Mode A: Build mode
- Implement the milestone outcome end-to-end.
- Keep changes minimal, deterministic, and GitOps-first.
- Validate in cluster with concrete checks.

### Mode B: Teach mode
- Explain architecture flow for the exact milestone.
- Explain failure paths and root-cause reasoning.
- Explain why alternatives were rejected.
- Provide interview-defensible language.

Both modes must run every week.

## Weekly close-out contract (required)

At the end of each week, produce:

1. Milestone DoD verification
- Which DoD lines are done/not done.
- Exact evidence commands and expected outputs.

2. System understanding map
- Components used this week.
- Control-plane and data-plane request flow.

3. Debugging narrative
- What failed.
- Why it failed.
- How it was fixed.
- How to prevent recurrence.

4. Design decisions log
- Decision made.
- Reason.
- Rejected options.

5. Interview script update
- 60-second summary.
- 5-minute deep explanation.

6. Next-week readiness
- Risks carried forward.
- Prerequisites for next milestone.

## Anti-drift rules

- Never mark a week complete without the learning close-out.
- Never present green status without a failure-path explanation.
- Never leave docs inconsistent with repo state.
