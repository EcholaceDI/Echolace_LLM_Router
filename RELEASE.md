# Release Map

This file maps the global release checklist to exact files/scripts for this project.

Template: [`../../../docs/release-checklist-template.md`](../../../docs/release-checklist-template.md)

| Template Gate | Project Mapping (Exact Script/File) | Evidence to Attach |
|---|---|---|
| Versioning | Update version in `pyproject.toml` or project metadata file. | Diff/commit that updates version metadata. |
| Changelog | Update `CHANGELOG.md` at project root. | Link to changelog section for this release. |
| Security Scan | `pip-audit -r requirements.txt` | Command output (CI log or saved artifact). |
| Test Evidence | `pytest` | Test summary + command output. |
| Packaging | `python -m build` | Artifact name(s) + checksum/digest. |
| Rollback | Reinstall prior artifact / checkout previous release tag. | Rollback steps tested + outcome. |
| Ownership Signoff | Record approvals in release PR comments. | Named approvers and approval timestamps. |

## Release Execution Notes
- Release owner:
- Target version:
- Target date:
- Artifact location:
- Rollback reference:

## RC0 Readiness Update (2026-04-02)

- Release owner: Codex release automation
- Target version: 0.10.0rc0
- Target date: 2026-04-02
- Artifact location: `release-evidence/0.10.0rc0/` (logs + checksum manifest)
- Rollback reference: `release-evidence/0.10.0rc0/rollback_steps.md`

### Publish Readiness Decision

**Decision: DOWNGRADED TO ACTIVE STATUS (NOT READY TO TAG).**

Blockers:

1. `pip-audit -r requirements.txt` failed because `pip-audit` is not installed in the environment.
2. `pytest` failed during collection due to missing module `llm_router.security`.
3. `python -m build` failed because `build` is not installed in the environment.
4. Prior-tag rollback validation is blocked because no local Git tags are available for checkout.

## RC Verification Commands + Evidence

Run from project root:

| Script | Exact command | Evidence location |
|---|---|---|
| lint | `npm run lint` | [`release-evidence/0.10.0rc0/test-and-lint.log`](release-evidence/0.10.0rc0/test-and-lint.log) |
| test | `npm run test` | [`release-evidence/0.10.0rc0/pytest.txt`](release-evidence/0.10.0rc0/pytest.txt) |
| build | `npm run build` | [`release-evidence/0.10.0rc0/build.txt`](release-evidence/0.10.0rc0/build.txt) |
| release:verify | `npm run release:verify` | [`release-evidence/0.10.0rc0/test-and-lint.log`](release-evidence/0.10.0rc0/test-and-lint.log) |

