# Echolace_LLM_Router Release Checklist

## Release Evidence Convention
- Use a project-local, versioned evidence folder: `release-evidence/<version>/`.
- For `0.10.0rc0`, required artifacts live in `release-evidence/0.10.0rc0/`:
  - `test-and-lint.log`
  - `build-artifacts.md` + `artifact-checksums.txt`
  - `security-scan.log`
  - `rollback-validation.md`
  - `signoff-record.md`
- Sign-off cannot be marked complete until all required evidence links below are populated and valid.
- Every release must include evidence artifacts in that version folder (tests, build output, security scan output, rollback notes).
- Owner sign-off is invalid until all required evidence links below are real, non-placeholder links into `release-evidence/<version>/`.

Reference: [../RELEASE_GATES.md](../RELEASE_GATES.md)

## Release Gates
- [ ] Reproducible build documented and verified in clean environment
- [ ] Smoke tests documented and passing for release candidate
- [ ] Runtime documentation complete and current
- [x] Secret handling documentation complete and current
- [x] Rollback notes complete, validated, and linked to last-known-good version

## Evidence Links
> Evidence links must be non-empty before sign-off checkboxes can be marked complete.
- Test + lint log: [release-evidence/0.10.0rc0/test-and-lint.log](release-evidence/0.10.0rc0/test-and-lint.log)
- Build artifacts list: [release-evidence/0.10.0rc0/build-artifacts.md](release-evidence/0.10.0rc0/build-artifacts.md)
- Artifact checksums: [release-evidence/0.10.0rc0/artifact-checksums.txt](release-evidence/0.10.0rc0/artifact-checksums.txt)
- Security scan output: [release-evidence/0.10.0rc0/security-scan.log](release-evidence/0.10.0rc0/security-scan.log)
- Rollback validation notes: [release-evidence/0.10.0rc0/rollback-validation.md](release-evidence/0.10.0rc0/rollback-validation.md)
- Signoff record: [release-evidence/0.10.0rc0/signoff-record.md](release-evidence/0.10.0rc0/signoff-record.md)
> Evidence links must be concrete artifact links before sign-off checkboxes can be marked complete.
- Test logs: [release-evidence/<version>/test-logs.txt](release-evidence/<version>/test-logs.txt)
- Build output summary: [release-evidence/<version>/build-summary.md](release-evidence/<version>/build-summary.md)
- Security scan output: [release-evidence/<version>/security-scan.txt](release-evidence/<version>/security-scan.txt)
- Rollback test notes: [release-evidence/<version>/rollback-test-notes.md](release-evidence/<version>/rollback-test-notes.md)
- Runtime docs: [ENVIRONMENT.md](ENVIRONMENT.md)
- Secret handling docs: [docs/operations/SECRETS.md](docs/operations/SECRETS.md)
- Rollback runbook: [docs/operations/ROLLBACK.md](docs/operations/ROLLBACK.md)
- Operational runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md)

- Rollback rehearsal (2026-04-02): PASS — [release-evidence/0.10.0rc0/rollback-rehearsal-2026-04-02.md](release-evidence/0.10.0rc0/rollback-rehearsal-2026-04-02.md)

- Tabletop drill record (2026-04-13): COMPLETE — [release-evidence/0.10.0rc0/tabletop-drill-2026-04-13.md](release-evidence/0.10.0rc0/tabletop-drill-2026-04-13.md)

## Owner Sign-off
- [ ] Engineering Owner sign-off *(requires all evidence links above)*
- [ ] QA/Validation sign-off *(requires all evidence links above)*
- [ ] Operations/Release sign-off *(requires all evidence links above)*

Sign-off date (YYYY-MM-DD):
Release version/tag: v0.10.0rc0
