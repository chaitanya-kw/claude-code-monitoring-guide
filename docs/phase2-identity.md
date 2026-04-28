# Phase 2: Identity and Attribution

## What this does

- All Claude Code metrics carry a `user_email` label automatically (emitted by the CLI).
- A `project` label is added at ingest time by the OTel Collector, sourced from the `OTEL_RESOURCE_ATTRIBUTES=project=<name>` env var set in each repo's `.envrc`. Sessions without this env var are tagged `project=unknown`.
- Grafana native auth is enabled; the per-user dashboard defaults to the logged-in user's email via the `user_email` variable.

## Setting up per-repo attribution with direnv

Each developer installs [direnv](https://direnv.net/) once:

```bash
# Ubuntu/Debian
sudo apt install direnv

# Add to ~/.bashrc or ~/.zshrc:
eval "$(direnv hook bash)"   # or zsh
```

For each repo you want to track, copy `.envrc.example` into the repo root and edit it:

```bash
cp /path/to/claude-code-monitoring-guide/.envrc.example ~/your-repo/.envrc
# Edit .envrc: set project=<your-repo-name>
direnv allow ~/your-repo
```

From then on, any Claude Code session started from inside `~/your-repo/` will emit metrics tagged `project=<your-repo-name>`.

## Team rollout checklist

1. Each dev installs direnv and hooks it into their shell.
2. Each dev adds an `.envrc` (from the example template) to every repo they work in.
3. Each dev runs `direnv allow` once per repo.
4. Sessions outside any repo with an `.envrc` will appear as `project=unknown` — acceptable.

## Grafana user accounts

The admin creates one Grafana account per developer at `http://localhost:3000` (or the prod URL):

- **Admin → Users → New user** — set email to match what Claude Code emits as `user_email`.
- Each user logs in with their own credentials; the **Claude Code — Per User** dashboard defaults to their own data.
- The `user_email` dashboard variable is also a dropdown: admins can switch to any user's view.

Anonymous access is disabled (`grafana.ini` → `[auth.anonymous] enabled = false`). All users must log in.

## Label schema reference

Labels present on all Claude Code metrics after Phase 2:

| Label | Source | Notes |
|---|---|---|
| `user_email` | Claude Code CLI | Primary identity signal |
| `project` | OTel Collector (from resource attr) | Defaults to `unknown` |
| `session_id` | Claude Code CLI | Per-session deduplication |
| `user_id` | Claude Code CLI | Numeric internal ID |
| `organization_id` | Claude Code CLI | |
| `terminal_type` | Claude Code CLI | |

Additional labels vary by metric (e.g. `model`, `type` on token metrics).
