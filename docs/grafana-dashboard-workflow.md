# Grafana Dashboard Workflow — Claude Code + MCPs

## Overview

This document covers how to create and update Grafana dashboards for the Claude Code productivity stack using Claude Code with the Grafana MCP and Prometheus MCP connected. The workflow replaces manual JSON editing and point-and-click dashboard building with a prompt-driven loop that reads live data, writes validated JSON, and pushes directly to Grafana.

**Prerequisites**

- Claude Code installed and running
- Grafana and Prometheus running (Docker Compose stack)
- Grafana service account token with Editor role
- Both MCPs configured (see Setup below)

---

## Setup

### 1. Prometheus MCP

```bash
claude mcp add-json "prometheus" \
  '{"command":"docker","args":["run","-i","--rm","-e","PROMETHEUS_URL","ghcr.io/pab1it0/prometheus-mcp-server:latest"],"env":{"PROMETHEUS_URL":"http://localhost:9090"}}'
```

### 2. Grafana MCP

```bash
claude mcp add-json "grafana" \
  '{"command":"docker","args":["run","--rm","-i","-e","GRAFANA_URL","-e","GRAFANA_SERVICE_ACCOUNT_TOKEN","grafana/mcp-grafana","-t","stdio"],"env":{"GRAFANA_URL":"http://localhost:3000","GRAFANA_SERVICE_ACCOUNT_TOKEN":"<your-grafana-service-account-token>"}}'
```

Create the service account token in Grafana: **Administration → Service accounts → Add service account token**. Editor role is sufficient for all dashboard operations. Use `--disable-write` on the Grafana MCP if you want to prevent Claude Code from pushing changes without a manual review step.

### 3. Verify both MCPs are active

```bash
claude mcp list
```

Both `prometheus` and `grafana` should appear with status `connected`.

---

## The Core Workflow

Every dashboard session follows the same four-step loop:

```
Discover → Inspect → Generate → Push
```

### Step 1 — Discover

Claude Code uses the Prometheus MCP to enumerate what metrics actually exist in your instance before writing any queries.

**Prompt:**

```
List all available metric names in Prometheus that contain "claude" or "github".
For each metric, show its label names and a sample of label values.
```

Claude Code will call `list_prometheus_metric_names`, then `list_prometheus_label_names` and `list_prometheus_label_values` per metric. The output gives you the exact strings to use in PromQL — no guessing at `claude_code_tokens_total` vs `claudecode_token_count`.

Save the output or keep it in context. You will reference it in every subsequent prompt.

### Step 2 — Inspect existing dashboards

Before creating anything new, pull what already exists.

**Prompt:**

```
Search for all dashboards in Grafana. For each one, get its UID and a summary.
```

Claude Code calls `search_dashboards` then `get_dashboard_summary` per result. This tells you what panels exist, what queries they use, and what the current variable config looks like — without pulling the full JSON.

To inspect a specific dashboard's panel queries:

```
Get the panel queries for dashboard UID <uid>.
```

This calls `get_dashboard_panel_queries` and returns panel titles, datasource UIDs, and raw PromQL — the exact reference you need before adding or modifying panels.

### Step 3 — Generate

With live metric names from Step 1 and existing panel structure from Step 2, prompt Claude Code to build or modify the dashboard JSON.

**Adding a new panel (example):**

```
Add a time series panel to dashboard UID <uid> showing
"lines of code per output token" per developer.

Use this PromQL:
  sum by (developer_email) (increase(lines_added_total[7d]))
  /
  sum by (developer_email) (increase(tokens_output_total[7d]))

Apply the existing $developer_email variable filter.
Place it after the "edit acceptance rate" panel.
```

**Creating a dashboard from scratch:**

```
Create a new dashboard called "Claude Code — Team Overview".

Use the following metrics (confirmed from Prometheus):
  - <metric names from Step 1>

Include these panels:
  1. Stat — total token cost this week (all users, sum)
  2. Bar chart — token cost per commit by developer (7d)
  3. Time series — edit acceptance rate over time, per developer
  4. Table — all six derived metrics, current week, one row per developer

Add a $developer_email query variable using:
  label_values(<primary_metric>, developer_email)

Apply {developer_email=~"$developer_email"} to all per-user panels.
Team aggregate panels should not filter by user.
```

Claude Code will produce the dashboard JSON. At this point it exists only in context — it has not been pushed yet.

### Step 4 — Push

**Prompt:**

```
Push this dashboard to Grafana. Use update_dashboard.
Target folder: "Claude Code" (create it if it doesn't exist).
```

Claude Code calls `create_folder` if needed, then `update_dashboard` with the JSON. Grafana returns a URL. Verify the result:

```
Generate a deeplink to the dashboard we just pushed.
```

The `generate_deeplink` tool returns a direct URL to the dashboard, including any variable presets you want to encode.

---

## Common Operations

### Rename or reorder panels

```
In dashboard UID <uid>, rename the panel "Token Cost" to "Token Cost (USD)"
and move it to position row 1, column 1.
```

Claude Code fetches the current JSON via `get_dashboard_by_uid`, applies the change, and pushes back with `update_dashboard`.

### Add per-user variable to an existing dashboard

```
Dashboard UID <uid> has no user filter variable.
1. List the label values for developer_email from metric <metric_name>.
2. Add a query variable $developer_email using label_values(<metric>, developer_email).
   Set it to refresh on dashboard load. Hide it from the URL.
3. Apply {developer_email="$developer_email"} to all panels that have
   a developer_email label. Leave aggregate panels unchanged.
4. Push the updated dashboard.
```

### Fix a broken panel query

```
Panel "PR Cycle Time" in dashboard UID <uid> is returning no data.
1. Get its current query.
2. Run that query against Prometheus and show the result.
3. List label names for github_pr_cycle_time_seconds.
4. Rewrite the query to fix any label mismatches and push the update.
```

This is where both MCPs are most valuable together — the Grafana MCP retrieves the broken query, the Prometheus MCP executes it and diagnoses why it returns nothing, and Claude Code rewrites and pushes the fix in one session.

### Render a panel image for review

```
Render panel <panel_id> from dashboard UID <uid> as a PNG
for the last 7 days.
```

Calls `get_panel_image`. Useful for spot-checking a panel without opening a browser, or for including in a report or PR comment. Requires the Grafana Image Renderer service to be configured in the stack.

### Annotate a deployment or config change

```
Create an annotation on dashboard UID <uid> at the current timestamp.
Tag it "deploy". Text: "Rolled out UUID→email relabelling in OTel Collector."
```

Calls `create_annotation`. The annotation appears as a vertical marker on all time series panels.

---

## Keeping Dashboards in Version Control

Grafana MCP write operations mutate the live instance directly. To keep dashboards in version control alongside the Docker Compose stack:

**After any push, export to file:**

```
Get dashboard UID <uid> as full JSON and write it to
grafana/dashboards/<dashboard-name>.json
```

Claude Code calls `get_dashboard_by_uid` and writes the file. Commit it. The existing provisioning config (mounted via Docker Compose volume) will reload it on next container start.

Do not store the `id` field from the exported JSON — strip it before committing so Grafana assigns a new one on import. The `uid` field is what matters for stable references.

---

## What Claude Code Cannot Do via MCP

These require manual action or tooling outside this workflow:

- **Per-user enforcement** — Grafana has no native mechanism to lock a user to their own email in the variable dropdown. The `$developer_email` variable relies on convention. The Admin MCP tools (`list_users_by_org`, `list_all_roles`) can help you audit who has what access, but cannot enforce query-level data isolation.
- **Schema v2 dashboards** — `update_dashboard` targets the Classic schema. Do not enable the `kubernetesDashboards` feature flag on your instance unless you are prepared to manage v2 JSON manually; it is still experimental as of Grafana 12/13.
- **Grafana user account creation** — user provisioning is done via the Grafana API or UI, not the MCP.
- **Alert notification routing beyond read** — `alerting_manage_routing` is available but test your alert rules manually before relying on them.

---

## Reference — MCP Tools Used in This Workflow

| Tool                           | MCP        | Used For                                      |
| ------------------------------ | ---------- | --------------------------------------------- |
| `list_prometheus_metric_names` | Prometheus | Discover available metrics                    |
| `list_prometheus_label_names`  | Prometheus | Discover label keys per metric                |
| `list_prometheus_label_values` | Prometheus | Discover label values (e.g. email list)       |
| `query_prometheus`             | Prometheus | Validate PromQL before embedding in panels    |
| `search_dashboards`            | Grafana    | Find existing dashboards by name              |
| `get_dashboard_summary`        | Grafana    | Inspect dashboard structure without full JSON |
| `get_dashboard_by_uid`         | Grafana    | Pull full dashboard JSON for editing          |
| `get_dashboard_panel_queries`  | Grafana    | Read existing panel queries as reference      |
| `update_dashboard`             | Grafana    | Push new or updated dashboard JSON            |
| `create_folder`                | Grafana    | Create folder before first push               |
| `generate_deeplink`            | Grafana    | Get direct URL to dashboard or panel          |
| `get_panel_image`              | Grafana    | Render panel as PNG for review                |
| `create_annotation`            | Grafana    | Mark deployments or config changes            |
| `list_datasources`             | Grafana    | Get datasource UIDs for panel JSON            |
