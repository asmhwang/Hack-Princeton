# `infra/` — Dedalus deployment

Task 12.1 + 12.3 (Plan A.7.a). Four Dedalus Machines run the suppl.ai swarm:

| Name           | Role                                    | Unit                        |
|----------------|-----------------------------------------|-----------------------------|
| `scout-vm`     | Scout agent (5 source tasks)            | `supplai-scout.service`     |
| `analyst-vm`   | Analyst agent (Gemini tool loop)        | `supplai-analyst.service`   |
| `strategist-vm`| Strategist agent (OpenClaw actions)     | `supplai-strategist.service`|
| `db-vm`        | Postgres 16 + FastAPI + WS relay        | (API colocated; no agent)   |

## 1. Provision

```bash
export DEDALUS_API_KEY=...            # from https://dedaluslabs.ai/dashboard
uv run python infra/provision.py      # creates all 4 Machines, writes infra/machines.json
uv run python infra/provision.py --dry-run   # preview without calling API
```

Idempotent: reruns reuse existing Machines (409 → look up by name). On
`NoReadyHosts` delete orphan VMs in the Dedalus dashboard and rerun.

## 2. Deploy agents

Per-VM bootstrap (once — see `infra/systemd/README.md` for the full sequence):

```bash
./infra/scripts/deploy.sh <vm-host> scout
./infra/scripts/deploy.sh <vm-host> analyst
./infra/scripts/deploy.sh <vm-host> strategist
```

`deploy.sh` rsyncs the repo to `/opt/supplai`, drops the matching unit into
`/etc/systemd/system/`, and runs `daemon-reload + enable --now`. Idempotent
— rerun on every code change.

## 3. Smoke check

```bash
uv run python scripts/smoke.py \
  --scout      http://scout-vm:9101/health \
  --analyst    http://analyst-vm:9102/health \
  --strategist http://strategist-vm:9103/health \
  --api        http://db-vm:8000/health
```

Exit 0 iff every endpoint returns `200 {"ok": true}`. Non-zero exit fails CI.

## 4. Restart persistence (Task 12.3 judging gate)

```bash
uv run python scripts/restart_persistence_test.py --ssh-user root
```

SSHes to each agent VM, asserts the pre-restart `state.json` matches
post-restart, and checks that no duplicate signals land after `systemctl
restart`. See script `--help` for per-VM inventory override.

## Files

```
infra/
  provision.py              # Dedalus Machine provisioning (idempotent)
  machines.json             # generated inventory (gitignored)
  scripts/
    deploy.sh               # rsync + systemctl deploy per VM
  systemd/
    README.md               # per-VM bootstrap + operate notes
    supplai-scout.service
    supplai-analyst.service
    supplai-strategist.service
```
