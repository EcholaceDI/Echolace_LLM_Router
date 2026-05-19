# Echolace_LLM_Router Rollback Runbook

## Trigger criteria
- Release introduces production-impacting regressions (error rate, latency, or functional breakage).
- Security or data integrity concern requires immediate return to last-known-good release.

## Rollback procedure
1. Freeze deploy pipeline and declare rollback in incident channel.
2. Identify last-known-good artifact/tag from release evidence.
3. Redeploy prior artifact and reset release pointer/tag.
4. Run smoke checks and verify critical user flows.
5. Keep heightened monitoring for at least 30 minutes after rollback.

## Verification checks
- Service health checks return green.
- Core smoke command from `ENVIRONMENT.md` passes.
- No new critical alerts for two consecutive monitoring windows.

## Rehearsal requirement
- Run at least one rollback rehearsal per release candidate and log evidence in `RELEASE_CHECKLIST.md`.
