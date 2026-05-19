# Echolace_LLM_Router Secrets Operations

## Secret source
1Password vault entry `Echolace_LLM_Router/production` (authoritative) with break-glass copy in GitHub Actions environment secrets.

## Injection path
Injected as process environment variables at deploy time via runner secret context (see `ENVIRONMENT.md` and backend env vars in `docs/BACKENDS.md`).

## Rotation owner
LLM Platform on-call (primary) and Release Engineering backup.

## Secrets in scope
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `UNIVERSAL_OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `HUGGINGFACE_API_KEY`

## Emergency revocation steps
1. Page the rotation owner and incident commander immediately.
2. Disable exposed credential(s) at provider side (or revoke token/session) before issuing replacements.
3. Rotate credentials in the source of truth and propagate new values to deployment secret stores.
4. Restart/redeploy runtime workloads to force fresh secret injection.
5. Validate with smoke checks and confirm old credentials fail authentication.
6. Record incident timeline, blast radius, and follow-up tasks in release evidence.
