# Dedalus VM systemd units

One unit per agent VM — `scout-vm`, `analyst-vm`, `strategist-vm`. Each runs
the matching `backend.agents.<name>.main` module under the `supplai` user and
writes checkpoint state to `/var/lib/supplai/state.json` (the path granted by
`StateDirectory=supplai`).

## Per-VM bootstrap (run once per VM)

```bash
# 1. Create service user + state dir
sudo useradd --system --home /opt/supplai --shell /usr/sbin/nologin supplai
sudo mkdir -p /opt/supplai /etc/supplai /var/lib/supplai
sudo chown -R supplai:supplai /opt/supplai /var/lib/supplai

# 2. Install uv into /usr/local/bin (required by ExecStart path)
curl -LsSf https://astral.sh/uv/install.sh | sudo sh
sudo mv ~/.local/bin/uv /usr/local/bin/uv

# 3. Drop the .env file — see backend/.env.example for required keys
sudo install -m 0600 -o supplai -g supplai env /etc/supplai/env

# 4. Deploy code + unit (see infra/scripts/deploy.sh)
./infra/scripts/deploy.sh <vm-host> scout
```

## Deploy

`infra/scripts/deploy.sh` rsyncs the repo to `/opt/supplai`, drops the matching
unit into `/etc/systemd/system/`, and runs `systemctl daemon-reload && enable
--now supplai-<agent>.service`. Idempotent — rerun after each code change.

## Operate

```bash
systemctl status supplai-scout      # health
journalctl -u supplai-scout -f      # tail logs
systemctl restart supplai-scout     # triggers checkpoint-resume codepath
```

## Verify restart persistence (Task 12.3)

After a signal lands, `systemctl restart supplai-scout && sleep 5` then run
`scripts/smoke.py` from the operator box — `/health.uptime_s` should reset
while the downstream DB row count must not grow (no duplicate signals).

## Notes

- `StateDirectory=supplai` causes systemd to create `/var/lib/supplai` with
  mode `0755` owned by `User=`. The agent writes `state.json` mode `0600` via
  the atomic `os.replace` path in `AgentBase._save_state`.
- `Restart=on-failure` with `RestartSec=3` means a crash is absorbed quietly.
  Manual `systemctl stop` is *not* a failure → it won't trigger a restart.
- SIGTERM on stop: the agent's `main.py` registers
  `loop.add_signal_handler(SIGTERM, stop)` so checkpoint flush runs before
  exit. The base class alone does not wire this — see each agent's `main.py`.
