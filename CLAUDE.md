# CLAUDE.md

## Project

Claude Code productivity tracking stack for a team of 3–8 developers at Kilowott. Forks
the Anthropic `claude-code-monitoring-guide` base repo and extends it with UUID→email
identity attribution, per-repo project tagging, GitHub PR enrichment, and automated
weekly reporting. Correlates Claude Code OTel telemetry with GitHub activity to surface
per-developer and per-project productivity signals. Deployed via Docker Compose — Phase 0
is local validation; Phase 1 pushes to a GCP VM.

## Stack

- Docker Compose — orchestration (5 services when complete)
- OpenTelemetry Collector (`otel/opentelemetry-collector-contrib`) — ingestion, relabelling, transforms
- Prometheus — metric storage (15s scrape, 200h retention)
- Grafana — dashboards, native user auth, per-user panel filtering
- nginx — reverse proxy + TLS (prod only; excluded locally via override)
- GitHub poller — Python service, GitHub API, OTel metric emission (Phase 3)
- Claude Code CLI — weekly report generation via `claude -p`

## Dev commands

```bash
docker compose up -d            # start local stack
docker compose ps               # check service health
docker compose logs otel-collector
curl "http://localhost:9090/api/v1/query?query=..."   # query Prometheus
bash scripts/weekly-report.sh   # generate weekly report (Phase 0+)
```

## Architecture

```
otel-collector-config.yaml   — OTel pipeline: OTLP in → Prometheus out
prometheus.yml               — scrape config (otel-collector:8889, prometheus:9090)
docker-compose.yml           — service definitions
grafana/
  provisioning/datasources/  — auto-wires Prometheus datasource on start
  provisioning/dashboards/   — dashboard loader (allowUiUpdates: true locally)
  dashboards/                — dashboard JSON files
docs/                        — phase docs, handover notes, plan
nginx/                       — reverse proxy config [Phase 1, to create]
github-poller/               — Dockerfile + poller.py [Phase 3, to create]
scripts/                     — weekly-report.sh, historical-import.py [to create]
```

Data flow: dev machine OTel → Collector (4317/4318) → Prometheus → Grafana

Report flow: GCP Prometheus (SSH tunnel or nginx endpoint) → weekly-report.sh → `claude -p` → report

## Business logic

- **Identity** — UUID→email relabelling at OTel Collector ingest; raw UUIDs never reach Prometheus
- **Attribution** — per-repo `.envrc` sets `OTEL_RESOURCE_ATTRIBUTES="project=<repo-name>"`; sessions outside a repo default to `project=unknown` via Collector transform
- **Visibility** — Grafana native user auth; `${__user.email}` dashboard variable gates individual panels; team aggregates visible to all
- **GitHub enrichment** — poller fetches PR cycle time, diff size, review counts via GitHub API; emits as OTel metrics into same pipeline
- **Reporting** — `weekly-report.sh` queries Prometheus API on GCP, passes telemetry + GitHub metrics JSON to `claude -p`
- **Historical import** — one-time script parses `~/.claude/projects/` JSONL; emits metrics tagged `data_source=historical`; token cost not reconstructed

## Related systems

- **GitHub API** — personal access token; poller fetches PR metadata per repo
- **GCP VM** — Docker Compose deployment target; Prometheus exposed for report script via SSH tunnel or nginx-proxied endpoint

## Development approach

Work through phases in order (0 → 1 → 2 → 3 → 4). Commit after each logical step.
Phase 0 (current): local stack + dashboard validation + report script working end-to-end.
Do not advance to Phase 1 until local stack is confirmed healthy.

## Conventions

- New filenames: `YYYY_MM_DD_HHMM-` prefix in IST (UTC+5:30, 24-hour clock)
- All documents: `.md`, headers start at H1, diagrams in Mermaid, code in fenced blocks
- Secrets: `.env` only — never committed; `.env.example` is the committed template

## Known inconsistencies

- `docker-compose.yml:39` — `GF_SECURITY_ADMIN_PASSWORD=admin` hardcoded; must move to `.env`
- `nginx/`, `github-poller/`, `scripts/` referenced in `docs/HANDOVER.md` but not yet on disk

## Out of scope

- Do not modify upstream base repo files without explicit instruction
- Do not provision or configure the GCP VM — that is Phase 1
- Do not commit `.env`, `docker-compose.override.yml`, or any file containing credentials

## Audit Config

- package_manager: none
- test_runner: none
- lint_cmd: none configured
- src_dirs: grafana/, docs/
- exclude_dirs: prometheus_data/, grafana_data/
- docstring_style: none
