# Project Metadata (`.echolace-project.yaml`)

This project uses a small YAML file at the repository root: `.echolace-project.yaml`.

It is intended as *vault metadata* for governance and operational tracking (not runtime configuration for the router).

Location:
- `.echolace-project.yaml`

## Current fields

Example:

```yaml
project_id: 07-production-applications-echolace-llm-router
bucket: 07_Production_Applications
owner: unassigned
status: production
last_reviewed: '2026-03-01'
readiness_score: 8
next_decision_date: '2026-03-31'
```

### `project_id` (string)
Stable identifier for this project across the vault.

### `bucket` (string)
Vault classification / district bucket used for reporting and navigation.

### `owner` (string)
Human or team owner (or `unassigned` if not yet assigned).

### `status` (string)
Lifecycle state, usually one of:
- `incubation`
- `active`
- `production`
- `archived`

### `last_reviewed` (string, date)
Last governance review date, stored as a string (typically `YYYY-MM-DD`).

### `readiness_score` (integer)
An at-a-glance maturity score used for governance decisions.

### `next_decision_date` (string, date)
When the next review or promotion decision should happen.

## Notes

- This file should not contain secrets.
- Runtime configuration for LLM providers is handled via environment variables and (optionally) external secret managers.

