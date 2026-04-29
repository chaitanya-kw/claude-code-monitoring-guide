# Claude Code Productivity Dashboard Specification

## Context

Grafana dashboards for Claude Code usage tracking across the Kilowott development team. Metrics flow from Claude Code → OTel Collector → Prometheus (numeric counters) and Loki (structured log events). GitHub enrichment is not in scope for this build.

All developers are on seat-based plans. Cost reflects workflow intensity, not billing. Focus at individual and team lead level is **tokens and time**. Cost is the primary lens at Senior Project Manager level and above.

---

## Design Principles

**Graph > Table > Stat.** Use a graph wherever the data has a time dimension or comparison across categories. Table only for inherently multi-column data. Stat card only for single point-in-time totals with no meaningful trend shape.

**Hero panel.** Each dashboard has exactly one hero panel — the most important indicator for that audience. Top row, larger than all others. All other panels are supporting context.

---

## Data Sources

| Datasource | UID          | URL                      |
| ---------- | ------------ | ------------------------ |
| Prometheus | `prometheus` | `http://prometheus:9090` |
| Loki       | `loki`       | `http://loki:3100`       |

---

## Metric Reference (summary)

### Prometheus

| Metric                                      | Key labels beyond common set                                                                |
| ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `claude_code_token_usage_tokens_total`      | `type` (`input`, `output`, `cacheRead`, `cacheCreation`), `model`, `effort`, `query_source` |
| `claude_code_cost_usage_USD_total`          | `model`, `effort`, `query_source`                                                           |
| `claude_code_lines_of_code_count_total`     | `type` (`added`, `removed`)                                                                 |
| `claude_code_code_edit_tool_decision_total` | `decision` (`accept`, `reject`), `tool_name`, `language`, `source`                          |
| `claude_code_session_count_total`           | `start_type`                                                                                |
| `claude_code_commit_count_total`            | common only                                                                                 |
| `claude_code_pull_request_count_total`      | common only                                                                                 |

Common labels on all metrics: `user_email`, `project`, `session_id`, `terminal_type`, `otel_scope_version`

Token type values: `input` (non-cached prompt), `output` (completion), `cacheRead` (served from cache, cheap), `cacheCreation` (written to cache, paid once).

`query_source` values: `main` (main REPL thread), `subagent` (spawned subagent), `auxiliary` (background work). Subagent fraction indicates agentic usage depth.

### Loki — `claude-code` service

Stream labels (index, use in `{}`): `service_name`, `service_version`, `project`, `os_type`

Structured metadata (use after `| logfmt`): `user_email`, `session_id`, `model`, `event_name`, `duration_ms`, `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `tool_name`, `success`, `effort`, `query_source`, `tool_input_size_bytes`, `tool_result_size_bytes`, `decision_type`, `decision_source`

| Event           | When emitted              | Key fields                                                                                                                                  |
| --------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `api_request`   | Each Anthropic API call   | `duration_ms`, `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `model`, `effort`, `query_source` |
| `tool_result`   | Tool finishes executing   | `tool_name`, `duration_ms`, `success`, `decision_type`, `decision_source`, `tool_input_size_bytes`, `tool_result_size_bytes`                |
| `tool_decision` | Tool permission evaluated | `tool_name`, `decision`, `source`                                                                                                           |

---

## Note on `active_time` — Dropped

`claude_code_active_time_seconds_total` is emitted by the CLI session tracker only. Three of four Kilowott developers use the VS Code extension and emit no `active_time` data. All panels depending on this metric are dropped.

### Loki proxies used instead

| Signal                     | Source                                     | Proxy for            |
| -------------------------- | ------------------------------------------ | -------------------- |
| API request rate over time | Loki `api_request`                         | Engagement intensity |
| Requests per session       | Loki `api_request` grouped by `session_id` | Session depth        |
| Session count              | Loki `api_request` distinct `session_id`   | Working sessions     |
| Tool call volume           | Loki `tool_result`                         | Active usage signal  |

**Not recoverable without `active_time`:** developer keyboard/review time, AI-assisted hours in wall-clock terms, session duration in wall-clock terms. Dropped cleanly — no proxy substitutes for them.

---

## Dashboard Variables

| Variable     | Type  | Query                                                                                   | Datasource | Notes                                                             |
| ------------ | ----- | --------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------- |
| `user_email` | Query | `label_values(claude_code_token_usage_tokens_total, user_email)`                        | Prometheus | Per Developer only. Default: `${__user.email}`                    |
| `project`    | Query | `label_values(claude_code_token_usage_tokens_total{user_email="$user_email"}, project)` | Prometheus | Per Developer only. Default: `All`. Scoped to selected developer. |

**Chained variable behaviour:** `$project` query is scoped to `{user_email="$user_email"}`. When `$user_email` changes, Grafana re-evaluates `$project` and resets to `All`. Standard Grafana chained variable pattern — no custom JS required.

On all other dashboards, an optional `project` filter variable can be added but is not required.

---

## Dashboard 1 — Per Developer

**Audience:** Individual developer
**Filter:** All panels filtered to `user_email="$user_email"` and `project=~"$project"`. Defaults: logged-in user, All projects.
**Max panels:** 16
**Value proposition:** Feedback on personal usage patterns, prompt discipline, and workflow efficiency. Watch for changes that improve token efficiency, engagement depth, and tool use patterns.

---

### Panel 1 — Token Type Breakdown Over Time `[G]` ⭐ HERO

**Purpose:** Cache hit ratio trending upward = improving prompt discipline and reuse. The single most actionable self-improvement signal.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project", type="input"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project", type="output"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project", type="cacheRead"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project", type="cacheCreation"}[$__rate_interval]))
```

Four queries, legend labels: `input`, `output`, `cache read`, `cache write`. Stacked area time series.

---

### Panel 2 — Edit Acceptance Rate Over Time `[G]`

**Purpose:** Quality signal. Sustained low rate = poor prompting, wrong model, or ignoring suggestions.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_code_edit_tool_decision_total{user_email="$user_email", project=~"$project", decision="accept"}[$__rate_interval]))
/
sum(rate(claude_code_code_edit_tool_decision_total{user_email="$user_email", project=~"$project"}[$__rate_interval]))
* 100
```

Unit = percent. Threshold lines at 50% (warning) and 70% (target).

---

### Panel 3 — Edit Acceptance Rate by Language `[G]`

**Purpose:** Breaks acceptance rate down by file language. A low rate in a specific language indicates the developer doesn't trust Claude's suggestions there, or the model performs less well in that context. Actionable: switch model, adjust prompting style, or accept that Claude Code is less useful for that language on this project.

**Datasource:** Prometheus

```promql
sum by (language) (increase(claude_code_code_edit_tool_decision_total{user_email="$user_email", project=~"$project", decision="accept"}[$__range]))
/
sum by (language) (increase(claude_code_code_edit_tool_decision_total{user_email="$user_email", project=~"$project"}[$__range]))
* 100
```

Bar chart, one bar per language, sorted descending. Unit = percent. Threshold colouring: red < 50%, yellow 50–70%, green > 70%.

---

### Panel 4 — Tokens Per Line of Code Over Time `[G]`

**Purpose:** Efficiency proxy. Lower over time = more output per token. Directional trend only — noisy by nature.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project"}[$__rate_interval]))
/
(
  sum(rate(claude_code_lines_of_code_count_total{user_email="$user_email", project=~"$project", type="added"}[$__rate_interval]))
  + sum(rate(claude_code_lines_of_code_count_total{user_email="$user_email", project=~"$project", type="removed"}[$__rate_interval]))
)
```

Use `[1h]` rate interval if too noisy at default. Y axis label: "tokens / line".

---

### Panel 5 — Tool Call Mix Over Time `[G]`

**Purpose:** Shows what kind of work Claude Code is doing. Edit-heavy = code modification; Bash-heavy = execution and testing; Read-heavy = codebase exploration. Shifts in the mix indicate changing workflows or task types.

**Datasource:** Loki
**Visualisation:** Stacked bar chart, one series per `tool_name`

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | user_email="$user_email" [$__interval]
) by (tool_name)
```

---

### Panel 6 — Tool Latency by Tool Name `[G]`

**Purpose:** Baseline for each tool's typical execution time. Bash latency spikes usually indicate a slow test suite or blocking process. Edit and Write should be near-instant; a spike there is worth investigating. Shifts in Bash latency often correlate with changes in what scripts are being run.

**Datasource:** Loki
**Visualisation:** Multi-line time series, one line per `tool_name`

```logql
avg by (tool_name) (
  avg_over_time(
    {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | user_email="$user_email"
    | unwrap duration_ms [$__interval]
  )
)
```

Unit = milliseconds.

---

### Panel 7 — Tool Failure Rate by Tool Name `[G]`

**Purpose:** Bash failures are common and often expected (Claude runs commands speculatively). Edit and Write failures are not — they typically indicate permission misconfiguration or file access issues. Spikes in specific tools narrow down environment problems quickly.

**Datasource:** Loki
**Visualisation:** Multi-line time series, one line per `tool_name`

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | user_email="$user_email" | success="false" [$__interval]
) by (tool_name)
/
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | user_email="$user_email" [$__interval]
) by (tool_name)
* 100
```

Unit = percent. Y axis 0–100.

---

### Panel 8 — Tools Per API Request Over Time `[G]`

**Purpose:** Measures average tool use depth per prompt turn. Rising value = Claude is doing more autonomous work per exchange (more agentic). Falling = more conversational back-and-forth. Connects token type breakdown (more cache reads with higher tool depth is expected) to actual work pattern.

**Datasource:** Loki
**Visualisation:** Time series

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | user_email="$user_email" [$__interval]
)
/
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email" [$__interval]
)
```

Y axis label: "tools / request".

---

### Panel 9 — API Request Rate Over Time `[G]`

**Purpose:** Engagement intensity. Primary replacement for active time as a usage signal — works for all surfaces including VS Code.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email" [$__interval]
)
```

Unit = requests. Bar chart aligned to `$__interval`.

---

### Panel 10 — Requests Per Session Over Time `[G]`

**Purpose:** Session depth proxy replacing average session duration. More requests per session = longer, more complex working sessions.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email" [$__interval]
)
/
count(
  count_over_time(
    {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email" [$__interval]
  ) by (session_id)
)
```

Y axis label: "requests / session".

---

### Panel 11 — Model Usage `[G]`

**Purpose:** Confirms intended model use. Catches accidental use of expensive models.

**Datasource:** Prometheus

```promql
sum by (model) (increase(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project"}[$__range]))
```

Bar chart, one bar per model.

---

### Panel 12 — Cost by Query Source `[G]`

**Purpose:** Subagent fraction shows agentic usage depth — what proportion of spend is multi-step autonomous work vs direct prompting.

**Datasource:** Prometheus

```promql
sum by (query_source) (increase(claude_code_cost_usage_USD_total{user_email="$user_email", project=~"$project"}[$__range]))
```

Bar or pie chart. Values: `main`, `subagent`, `auxiliary`.

---

### Panel 13 — API Response Latency `[G]`

**Purpose:** Baseline for noticing model changes or degradation. A shift in typical latency affects workflow pacing.

**Datasource:** Loki

```logql
avg_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email"
  | unwrap duration_ms [$__interval]
)
```

Unit = milliseconds. Optional: overlay p95 using `quantile_over_time(0.95, ...)`.

---

### Panel 14 — Token Usage Over Time `[G]`

**Purpose:** Baseline volume. Contextualises the token type breakdown hero.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", project=~"$project"}[$__rate_interval]))
```

---

### Panel 15 — Lines of Code `[S]` pair

**Purpose:** Output volume in the selected period.

**Datasource:** Prometheus

```promql
# Added
sum(increase(claude_code_lines_of_code_count_total{user_email="$user_email", project=~"$project", type="added"}[$__range]))
# Removed
sum(increase(claude_code_lines_of_code_count_total{user_email="$user_email", project=~"$project", type="removed"}[$__range]))
```

Two stat cards: "Lines Added" and "Lines Removed".

---

### Panel 16 — Session Count `[S]`

**Purpose:** Volume of working sessions in the selected period.

**Datasource:** Loki

```logql
count(
  count_over_time(
    {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" | user_email="$user_email" [$__range]
  ) by (session_id)
)
```

Stat card with sparkline.

---

## Dashboard 2 — Team Lead

**Audience:** Engineering team lead
**Filter:** No per-user filter. All developers visible. Optional `project` filter.
**Max panels:** 12
**Value proposition:** Identify adoption outliers, coach on prompting, spot engagement pattern shifts. Focus is tokens and time — not cost.

---

### Panel 1 — Acceptance Rate Trend — All Developers `[G]` ⭐ HERO

**Purpose:** Best coaching signal. Spot team-wide drops after model updates or onboarding. Individual lines reveal who is improving and who needs a conversation.

**Datasource:** Prometheus

```promql
sum by (user_email) (rate(claude_code_code_edit_tool_decision_total{decision="accept", project=~"$project"}[$__rate_interval]))
/
sum by (user_email) (rate(claude_code_code_edit_tool_decision_total{project=~"$project"}[$__rate_interval]))
* 100
```

Multi-line time series. Unit = percent. Threshold bands at 50% and 70%.

---

### Panel 2 — Edit Acceptance Rate by Developer `[T]`

**Purpose:** Snapshot ranking. Sort ascending to surface lowest performers.

**Datasource:** Prometheus

```promql
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total{decision="accept", project=~"$project"}[$__range]))
/
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total{project=~"$project"}[$__range]))
* 100
```

Table. Threshold colouring: red < 50%, yellow 50–70%, green > 70%. Add accepted/total counts as additional columns.

---

### Panel 3 — Token Usage by Developer `[G]`

**Purpose:** Volume comparison. Reveals who is and is not using Claude Code.

**Datasource:** Prometheus

```promql
sum by (user_email) (increase(claude_code_token_usage_tokens_total{project=~"$project"}[$__range]))
```

Bar chart, one bar per developer.

---

### Panel 4 — API Request Rate by Developer `[G]`

**Purpose:** Engagement intensity per developer over time. Works for all surfaces.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" [$__interval]
) by (user_email)
```

Multi-line time series, one line per developer.

---

### Panel 5 — Requests Per Session by Developer `[G]`

**Purpose:** Session depth per developer. Pair with acceptance rate: low acceptance + low depth = prompting problems; low acceptance + high depth = model fit issue.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" [$__range]
) by (user_email)
/
count(
  count_over_time(
    {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" [$__range]
  ) by (user_email, session_id)
) by (user_email)
```

Bar chart, one bar per developer. Unit = "requests / session".

---

### Panel 6 — Bash vs Edit Ratio by Developer `[G]`

**Purpose:** Single ratio describing the nature of each developer's work pattern. High = execution-heavy (running scripts, tests, commands); low = code-modification-heavy. Useful context when investigating a developer's token volume or acceptance rate — different work types have different baselines.

**Datasource:** Loki
**Visualisation:** Bar chart, one bar per developer

```logql
# Bash calls
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | tool_name="Bash" [$__range]
) by (user_email)
/
# Edit calls
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | tool_name="Edit" [$__range]
) by (user_email)
```

Y axis label: "Bash / Edit ratio". A value of 1 = equal; > 1 = more execution; < 1 = more editing.

---

### Panel 7 — Tool Call Depth by Developer `[G]`

**Purpose:** Who is running deep agentic tasks vs shallow conversational sessions. Contextualises token volume — a high-volume dev with high tool depth is doing different work to a high-volume dev with low depth.

**Datasource:** Loki
**Visualisation:** Bar chart, one bar per developer

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" [$__range]
) by (user_email)
/
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" [$__range]
) by (user_email)
```

Y axis label: "tools / request".

---

### Panel 8 — Tool Call Failure Rate by Developer `[T]`

**Purpose:** High failure rate = environment issues or tasks Claude Code is not suited for. Surfaces friction points worth investigating.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" | success="false" [$__range]
) by (user_email)
/
count_over_time(
  {service_name="claude-code", project=~"$project"} | logfmt | event_name="tool_result" [$__range]
) by (user_email)
* 100
```

Table. Unit = percent.

---

### Panel 9 — Per Developer, Per Model Token Usage `[G]`

**Purpose:** Which models each developer uses. Flags unintended model choices across the team.

**Datasource:** Prometheus

```promql
sum by (user_email, model) (increase(claude_code_token_usage_tokens_total{project=~"$project"}[$__range]))
```

Stacked bar chart — one bar per developer, stacked by model.

---

### Panel 10 — Subagent Token Fraction by Developer `[G]`

**Purpose:** Who is running agentic multi-step tasks vs simple completions. Contextualises both token volume and tool depth.

**Datasource:** Prometheus

```promql
sum by (user_email) (increase(claude_code_token_usage_tokens_total{query_source="subagent", project=~"$project"}[$__range]))
/
sum by (user_email) (increase(claude_code_token_usage_tokens_total{project=~"$project"}[$__range]))
* 100
```

Bar chart, one bar per developer. Unit = percent.

---

### Panel 11 — Top Consumers Right Now `[T]`

**Purpose:** Live view of who is actively using Claude Code.

**Datasource:** Prometheus

```promql
topk(5, sum by (user_email) (rate(claude_code_token_usage_tokens_total[5m])))
```

Auto-refresh every 30s.

---

### Panel 12 — Session Count by Developer `[G]`

**Purpose:** Volume of working sessions per developer. Normalises token usage.

**Datasource:** Loki

```logql
count by (user_email) (
  count_over_time(
    {service_name="claude-code", project=~"$project"} | logfmt | event_name="api_request" [$__range]
  ) by (user_email, session_id)
)
```

Bar chart.

---

## Dashboard 3 — Senior Project Manager

**Audience:** Senior project manager
**Filter:** No per-user filter. Optional `project` filter.
**Max panels:** 10
**Value proposition:** Cost governance, adoption visibility, efficiency at a glance. Cost is the primary lens.

---

### Panel 1 — Cost Trend — Daily, 30-Day Window `[G]` ⭐ HERO

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[$__interval]))
```

Bar chart at daily resolution. Unit = USD.

---

### Panel 2 — Total Team Cost — MTD `[S]`

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[30d]))
```

---

### Panel 3 — Projected Monthly Cost `[S]`

**Datasource:** Prometheus

```promql
sum(rate(claude_code_cost_usage_USD_total[7d])) * 86400 * 30
```

---

### Panel 4 — Weekly Summary Table `[T]`

**Columns:** `user_email`, `cost_usd`, `tokens`, `sessions`, `acceptance_rate_%`, `commits`

**Datasource:** Prometheus + Loki

```promql
sum by (user_email) (increase(claude_code_cost_usage_USD_total[$__range]))
sum by (user_email) (increase(claude_code_token_usage_tokens_total[$__range]))
sum by (user_email) (increase(claude_code_commit_count_total[$__range]))
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total{decision="accept"}[$__range]))
  / sum by (user_email) (increase(claude_code_code_edit_tool_decision_total[$__range])) * 100
```

```logql
count by (user_email) (
  count_over_time(
    {service_name="claude-code"} | logfmt | event_name="api_request" [$__range]
  ) by (user_email, session_id)
)
```

Join all results in Grafana table transformation.

---

### Panel 5 — Cost by Project `[G]`

**Purpose:** Where spend is going across projects. Useful for client attribution or project prioritisation.

**Datasource:** Prometheus

```promql
sum by (project) (increase(claude_code_cost_usage_USD_total[$__range]))
```

Bar chart, one bar per project.

---

### Panel 6 — Cost by Query Source — Team `[G]`

**Purpose:** What fraction of spend is agentic (subagent) vs direct prompting. Rising subagent fraction = team is tackling more complex autonomous tasks.

**Datasource:** Prometheus

```promql
sum by (query_source) (increase(claude_code_cost_usage_USD_total[$__range]))
```

Stacked bar or pie.

---

### Panel 7 — Team-Wide Edit Acceptance Rate Trend `[G]`

**Purpose:** Quality signal anchored to the cost hero. Falling acceptance while cost rises is the key risk signal.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_code_edit_tool_decision_total{decision="accept"}[$__rate_interval]))
/ sum(rate(claude_code_code_edit_tool_decision_total[$__rate_interval])) * 100
```

---

### Panel 8 — Cost Per Line of Code — Team `[S]`

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[$__range]))
/
(
  sum(increase(claude_code_lines_of_code_count_total{type="added"}[$__range]))
  + sum(increase(claude_code_lines_of_code_count_total{type="removed"}[$__range]))
)
```

Unit = USD/line (4 decimal places).

---

### Panel 9 — Cost Per Commit — Team `[S]`

**Purpose:** Rough ROI proxy using natively emitted commit count. Direction matters more than absolute value.

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[$__range]))
/
sum(increase(claude_code_commit_count_total[$__range]))
```

Unit = USD/commit.

---

### Panel 10 — Overall Model Usage `[G]`

**Datasource:** Prometheus

```promql
sum by (model) (increase(claude_code_token_usage_tokens_total[$__range]))
```

Bar chart, one bar per model.

---

## Dashboard 4 — Senior Management

**Audience:** Senior management / leadership
**Filter:** None. All aggregates, no individual developer data.
**Max panels:** 6
**Value proposition:** Is the investment being used? Is the trend positive? What is it costing? One screen, no scrolling.

---

### Panel 1 — AI Tooling Spend — MTD vs Prior Month `[S]` pair ⭐ HERO

**Datasource:** Prometheus

```promql
# MTD
sum(increase(claude_code_cost_usage_USD_total[30d]))
# Prior month
sum(increase(claude_code_cost_usage_USD_total[30d] offset 30d))
```

Two stat cards with delta indicator (% change).

---

### Panel 2 — Edit Acceptance Rate — Trend `[G]`

**Purpose:** Primary ROI signal at this level. Sustained upward trend = the AI is increasingly useful.

**Datasource:** Prometheus

```promql
sum(rate(claude_code_code_edit_tool_decision_total{decision="accept"}[$__rate_interval]))
/ sum(rate(claude_code_code_edit_tool_decision_total[$__rate_interval])) * 100
```

Single line. Default time range: 90 days.

---

### Panel 3 — Monthly Cost Trend `[G]`

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[$__interval]))
```

Bar chart at monthly resolution. Default time range: 6 months.

---

### Panel 4 — Team Adoption — Token-Based `[S]` pair

**Purpose:** How many developers are actively using Claude Code. Token-based — works for all surfaces.

**Datasource:** Prometheus

```promql
# Active in last 7 days
count(sum by (user_email) (increase(claude_code_token_usage_tokens_total[7d])) > 0)
# Active in last 30 days (team size proxy)
count(sum by (user_email) (increase(claude_code_token_usage_tokens_total[30d])) > 0)
```

Two stat cards: "Active this week" and "Active this month".

---

### Panel 5 — Commits This Month `[S]`

**Purpose:** Tangible output signal alongside cost. Only output volume available without GitHub enrichment.

**Datasource:** Prometheus

```promql
sum(increase(claude_code_commit_count_total[30d]))
```

---

### Panel 6 — Cost Per Commit — Trend `[G]`

**Purpose:** Closest available ROI proxy without GitHub. Falling = cost dropping or output increasing.

**Datasource:** Prometheus

```promql
sum(increase(claude_code_cost_usage_USD_total[$__interval]))
/
sum(increase(claude_code_commit_count_total[$__interval]))
```

Time series. Unit = USD/commit.

---

## Appendix — Tool Panel Alternatives

The following panels were considered and not included in the primary spec. Add them if the included tool panels are not surfacing useful signal, or if a dedicated tool activity sub-dashboard is warranted.

---

### Alt-T1 — Tool Input/Output Size Over Time `[G]`

**Dashboard:** Per Developer
**Purpose:** `tool_input_size_bytes` on Bash reflects context passed to shell commands; `tool_result_size_bytes` on Read reflects how much file context is being pulled in. A rising Read result size often correlates with larger cache tokens on the next API call — connects to the token type breakdown hero. Too abstract for most developers without a specific investigation in mind.

**Datasource:** Loki

```logql
# Average input size by tool
avg by (tool_name) (
  avg_over_time(
    {service_name="claude-code"} | logfmt | event_name="tool_result" | user_email="$user_email"
    | unwrap tool_input_size_bytes [$__interval]
  )
)

# Average result size by tool
avg by (tool_name) (
  avg_over_time(
    {service_name="claude-code"} | logfmt | event_name="tool_result" | user_email="$user_email"
    | unwrap tool_result_size_bytes [$__interval]
  )
)
```

---

### Alt-T2 — Manually Rejected Tool Decisions Over Time `[G]`

**Dashboard:** Per Developer
**Purpose:** `tool_decision` events where `decision="reject"` are developer-initiated blocks — the dev manually declined a tool call before it ran. High Bash reject rate = developer is running in cautious review mode. Distinct from `success="false"` which is a tool execution failure. Only meaningful if a developer is actively managing tool permissions.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code"} | logfmt | event_name="tool_decision" | user_email="$user_email" | decision="reject" [$__interval]
) by (tool_name)
```

---

### Alt-T3 — `decision_source` Breakdown `[G]`

**Dashboard:** Per Developer
**Purpose:** Breaks tool decisions by what granted permission (`config`, manual approval, etc.). Currently only `config` appears as a value in the data — no differentiation today. Revisit if other `decision_source` values appear as the team adopts custom tool permission configurations.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code"} | logfmt | event_name="tool_decision" | user_email="$user_email" [$__interval]
) by (decision_source)
```

---

### Alt-T4 — Hook Execution Health `[G]`

**Dashboard:** Per Developer or Team Lead
**Purpose:** `hook_execution_complete` events carry `num_blocking`, `num_non_blocking_error`, `num_cancelled`. Useful for detecting broken hooks. Only relevant once the team is actively using Claude Code hooks; not worth the panel slot until then.

**Datasource:** Loki

```logql
# Non-blocking errors over time
sum_over_time(
  {service_name="claude-code"} | logfmt | event_name="hook_execution_complete" | user_email="$user_email"
  | unwrap num_non_blocking_error [$__interval]
)

# Blocking hook executions
sum_over_time(
  {service_name="claude-code"} | logfmt | event_name="hook_execution_complete" | user_email="$user_email"
  | unwrap num_blocking [$__interval]
)
```

---

### Alt-T5 — Tool Call Failure Rate — Team-Wide `[G]`

**Dashboard:** Team Lead (alternative to per-tool breakdown)
**Purpose:** Aggregate failure rate across all tools and all developers as a single time series. Less diagnostic than the per-developer table (Panel 8) but useful as a team health trendline. Add if the per-developer table is not being used regularly.

**Datasource:** Loki

```logql
count_over_time(
  {service_name="claude-code"} | logfmt | event_name="tool_result" | success="false" [$__interval]
)
/
count_over_time(
  {service_name="claude-code"} | logfmt | event_name="tool_result" [$__interval]
)
* 100
```

---

## Implementation Notes

### Chained Dashboard Variables

`$project` is scoped to `{user_email="$user_email"}` so Grafana re-evaluates the project list on developer change and resets to `All`. Standard Grafana chained variable pattern — no additional configuration required.

### Session Counting

Always use Loki for session counts — more accurate than `claude_code_session_count_total` (fires at session start regardless of API calls).

### Null and Zero Handling

Acceptance rate panels: zero edit decisions in the window = no data, not zero. Correct — do not use `or vector(0)`. For `cost_per_commit` and `cost_per_line`: zero denominator shows `+Inf` — use a Grafana transformation to display "—".

### Loki Query Pattern

`user_email` and `event_name` are **structured metadata** in Loki (not stream labels). Confirmed via `GET /loki/api/v1/labels` — stream labels are `service_name`, `project`, `os_type`, `service_version` only.

Filter pattern — no parser needed:
```logql
{service_name="claude-code", project=~"$project"} | user_email="$user_email" | event_name="api_request"
```

Grouping by structured metadata works in metric queries: `by (user_email)`, `by (tool_name)`, `by (session_id)` all valid.

`| logfmt` is **not required** and should not be used — these fields are not in the log body.

**Pending (after 2026-04-30 demo):** Promote `user_email` and `event_name` to stream labels via OTel Collector `transform/promote_log_resource_attrs` processor. Loki `limits_config.otlp_config` already declares them as `index_label`. Once promoted, move `user_email` into the stream selector `{..., user_email="$user_email"}` for faster indexed lookup.

### Rate Interval

`$__rate_interval` for all `rate()` queries. `$__range` for `increase()` over the full selected window. `$__interval` for bar charts and Loki `count_over_time` aligned to time range resolution.

**Minimum interval:** Set `"interval": "1m"` on Loki targets in high-frequency panels to prevent `$__interval` collapsing below Loki's minimum step at short time ranges. For daily bar charts, set `"interval": "1d"` explicitly on the target. Without a minimum, queries over ranges shorter than ~15 minutes may return empty results or single-point series.

### Provisioning

Dashboard JSON in `./grafana/dashboards/<slug>/`. Provisioned via `./grafana/provisioning/dashboards/dashboards.yml`. After each Grafana MCP push: export with `get_dashboard_by_uid`, strip `id` field, commit with `uid` intact.

### Personal Dashboard Default

`$user_email` defaults to `${__user.email}`. Grafana account email must match `user_email` label value — enforced at account creation.
