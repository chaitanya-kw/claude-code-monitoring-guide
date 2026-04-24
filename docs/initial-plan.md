# Claude Code Productivity Tracking — Plan Summary

## Goal

Surface relative productivity signals for a team of 3–8 developers by correlating Claude Code telemetry with GitHub activity. No absolute targets — the system tracks how workflow and tooling changes affect productivity over time.

---

## Data Sources

**Claude Code** — native OTel telemetry emitted via env vars set system-wide on each dev's machine. Captures tokens, cost, sessions, commits, PRs, lines of code, edit acceptance rate, active time.

**GitHub** — a poller service that fetches PR cycle time, diff size, and review counts via the GitHub API, emitting them as OTel metrics into the same pipeline.

---

## Identity and Project Attribution

Each dev sets the standard OTel telemetry env vars in their shell profile. A per-repo `.envrc` (committed to each repo, loaded via `direnv`) sets:

```bash
export OTEL_RESOURCE_ATTRIBUTES="project=<repo-name>"
```

UUID→email mapping is applied at ingest via OTel Collector relabelling so all metrics are labelled by email from the start. Sessions outside a repo get `project=unknown` via a Collector transform default.

---

## Stack

The Anthropic `claude-code-monitoring-guide` repo as the base — forked and deployed to a GCP VM via Docker Compose.

| Component      | Role                                      |
| -------------- | ----------------------------------------- |
| OTel Collector | Ingestion, relabelling, transform         |
| Prometheus     | Metric storage                            |
| Grafana        | Dashboards, user auth, per-user filtering |
| nginx          | Reverse proxy, TLS                        |
| GitHub poller  | Fifth Compose service, enrichment metrics |

---

## Authentication and Visibility

Grafana native user auth — one login per dev. Per-user data filtering via a dashboard variable tied to the logged-in user's email, applied to every panel query. Team-level aggregates visible to everyone. Individual breakdowns gated per user.

---

## Metrics

All metrics available per user and per project, with week-on-week trends.

| Metric                           | Derivation                                                           |
| -------------------------------- | -------------------------------------------------------------------- |
| Token cost per commit            | `sum(cost) / sum(commits)` by user                                   |
| Session-to-commit ratio          | `sum(sessions) / sum(commits)` by user                               |
| Edit acceptance rate             | `accepted / total edit decisions` by user                            |
| Active time per commit           | `sum(active_time) / github_commits` by user                          |
| PR cycle time vs session density | PR open→merge duration joined with Claude active time in that window |
| Lines of code per output token   | `sum(lines_added) / sum(tokens_output)` by user                      |

---

## Historical Context

A one-time import script parses `~/.claude/projects/` JSONL files and emits approximate historical metrics (session count, tool call composition, session duration per project) tagged `data_source=historical`. Token counts and cost are not reconstructed. Historical data is filterable in all dashboard panels.

---

## Phases

### Phase 1 — Infrastructure

GCP VM provisioned, base Docker Compose stack deployed (OTel Collector, Prometheus, Grafana, nginx), TLS configured, OTel ingestion confirmed from at least one dev machine.

### Phase 2 — Identity and Attribution

UUID→email relabelling in OTel Collector config, Grafana user accounts created, per-user dashboard variable filtering wired, `.envrc` rolled out to all repos and devs, `direnv` set up on all machines.

### Phase 3 — GitHub Enrichment

GitHub poller added as a fifth Compose service, dashboards extended with GitHub-derived panels, derived metric for PR cycle time vs. session density implemented.

### Phase 4 — History and Rollout

Historical import script written and run on all dev machines, baselines established, full team onboarded, monitoring review cadence set.

---

## References

- Base stack: https://github.com/anthropics/claude-code-monitoring-guide
- Dashboard reference: https://github.com/ColeMurray/claude-code-otel
- Dev setup reference: https://gist.github.com/chaitanya-kw/816e7d1a3356fcd5561603dd4b013514
- Native analytics (requires Owner access): https://claude.ai/analytics/claude-code
