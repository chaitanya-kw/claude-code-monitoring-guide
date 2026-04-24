# Handover — Claude Code Productivity Tracking

## Context

This project implements a Claude Code productivity tracking stack for a team of 3–8 developers at Kilowott. The full plan is in the project file `2026_04_24_1302-claude-code-productivity-plan.md` — read that first.

---

## What has been done

- The Anthropic `claude-code-monitoring-guide` repo has been **forked** to the user's personal GitHub account and cloned locally.
- Upstream remote is registered with push disabled:
  - `origin` → user's fork (fetch + push)
  - `upstream` → `https://github.com/anthropics/claude-code-monitoring-guide.git` (fetch only, push disabled)
- The base stack has been confirmed working locally in a previous setup (proof of concept complete). The current clone is a clean fork — nothing beyond the base repo is in place yet.

---

## What needs to be done next

Work through the following steps in order. Commit after each logical step.

### Repo hygiene
- Add `.env`, `docker-compose.override.yml`, `grafana/data/`, `prometheus/data/` to `.gitignore`
- Create `.env.example` with vars for Grafana, OTel, Prometheus, and GitHub poller
- Copy to `.env` and fill in local values (`.env` is gitignored)

### Directory scaffold
Create if missing:
- `grafana/provisioning/datasources/`
- `grafana/provisioning/dashboards/`
- `grafana/dashboards/`
- `nginx/`
- `github-poller/`

### Local dev override
Create `docker-compose.override.yml` (gitignored) — exposes Grafana on 3000, Prometheus on 9090, OTel on 4317/4318 directly, excludes nginx locally.

### Grafana provisioning
- `grafana/provisioning/datasources/prometheus.yaml` — wires Prometheus as datasource automatically, no manual setup needed
- `grafana/provisioning/dashboards/dashboards.yaml` — dashboard loader with `allowUiUpdates: true` for local dev

### Verify local stack
`docker compose up -d` — all services healthy, Grafana loads with Prometheus datasource pre-wired.

### Phase 1 — Infrastructure files
- `nginx/nginx.conf` — prod reverse proxy + TLS
- `nginx/nginx.local.conf` — local plain HTTP reference
- `docs/phase1-infra.md` — GCP VM provisioning requirements

### Phase 2 — Identity and attribution files
- OTel Collector config: UUID→email relabelling, `project=unknown` default transform
- `grafana/grafana.ini` — disable anonymous auth, enable user management
- Starter dashboard JSON with `${__user.email}` variable wired into all panel queries
- `.envrc` template for per-repo project attribution
- `docs/phase2-identity.md` — direnv setup instructions for devs

### Phase 3 — GitHub enrichment files
- `github-poller/` — Dockerfile, `poller.py`, OTel metric emission
- `docker-compose.yml` additions for the poller as a fifth service
- Dashboard JSON additions for GitHub-derived panels
- `docs/phase3-github.md`

### Phase 4 — History and rollout files
- `scripts/historical-import.py` — parses `~/.claude/projects/` JSONL, emits metrics tagged `data_source=historical`
- `docs/phase4-rollout.md` — per-dev onboarding checklist
- `docs/review-cadence.md` — monitoring review template

---

## Environment

- OS: Pop!_OS Linux
- Stack: Docker Compose
- Editor: nvim
- GCP: existing project, VM not yet provisioned
- Secrets: plain `.env` file (on VM, never committed)
- GitHub: personal account, private fork

---

## Conventions

- Filenames for created files: prefix `YYYY_MM_DD_HHMM-` in IST (UTC+5:30, 24-hour clock)
- All documents `.md`
- Code in fenced blocks
- Diagrams in Mermaid
- Headers start at H1
