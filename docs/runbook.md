# Runbook — suppl.ai

Operational + dev-env notes. Updated as blockers surface.

## Blocked Dependencies

| Package | Blocker | Unblocks (phase) | Tracked in |
|---|---|---|---|
| `openclaw` | Not on PyPI under that name — awaiting Eragon-provided install path (VCS URL or private index) | Phase 7 (Strategist action layer) | `pyproject.toml` line with `# openclaw` TODO |

## Before you start

Checklist for a fresh teammate cloning the repo:

- [ ] `uv sync --all-groups` succeeds
- [ ] Postgres 16 running on `localhost:5432` (dev password `postgres`)
- [ ] `GEMINI_API_KEY` in `backend/.env.local` (get from https://aistudio.google.com/apikey, paste in shared 1Password vault)
- [ ] `TAVILY_API_KEY` in `backend/.env.local` (get from https://app.tavily.com, paste in shared 1Password vault)
- [ ] Dedalus credits claimed — each teammate at https://dedaluslabs.ai/hackprinceton-s26 ($50 × 3 = $150 total)
- [ ] Vercel account linked to the `suppl-ai` GitHub repo (preview deploys on every PR)
- [ ] `pnpm -C web install` succeeds (added in Phase 0 Task 0.5)

## Secrets handling

- All API keys live in **1Password shared vault** among the 3 teammates
- Never commit `.env.local` or `.env.*.local` (gitignored; gitleaks scans on every commit)
- Rotate keys via the respective provider dashboards if leaked; update 1Password and redeploy

## Dev-local Postgres

```bash
docker run --name supplai-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplai -p 5432:5432 -d postgres:16
```
