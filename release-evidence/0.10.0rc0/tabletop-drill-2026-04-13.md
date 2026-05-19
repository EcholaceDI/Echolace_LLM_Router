# Echolace_LLM_Router Tabletop Rollback Drill Record

- **Date:** 2026-04-13
- **Drill type:** Tabletop rollback rehearsal
- **Release candidate:** rc0
- **Facilitator:** Release Engineering
- **Participants:** Incident Lead, Operator, QA Observer, Scribe

## Scenario
A release-candidate deploy introduced sustained elevated error rates on a critical workflow and triggered customer-facing alerts.

## Completed checklist
- [x] Scenario selected and scope confirmed.
- [x] Participants assigned (Incident Lead, Operator, Scribe, Observer).
- [x] Rollback trigger validated against objective metrics.
- [x] Last-known-good artifact/tag and checksum verified.
- [x] Rollback steps executed in rehearsal timeline.
- [x] Post-rollback validation checks completed.
- [x] Follow-up actions captured with owners and due dates.

## Timing
- **Detection to rollback decision:** 7 minutes
- **Rollback execution window:** 11 minutes
- **Post-rollback validation window:** 30 minutes

## Outcome
PASS — The team met rollback RTO expectations and restored baseline service health in rehearsal.

## Follow-ups
1. Add automated evidence checksum verification in pre-deploy checks (Owner: Release Engineering, Due: 2026-04-20).
2. Add alert routing backup contact for off-hours drills (Owner: Operations, Due: 2026-04-22).
