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
- [ ] `GEMINI_API_KEY` in `backend/.env.local` (get from https://aistudio.google.com/apikey)
- [ ] `TAVILY_API_KEY` in `backend/.env.local` (get from https://app.tavily.com)
- [ ] `pnpm -C web install` succeeds (added in Phase 0 Task 0.5)

## Dev-local Postgres

```bash
docker run --name supplai-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplai -p 5432:5432 -d postgres:16
```
