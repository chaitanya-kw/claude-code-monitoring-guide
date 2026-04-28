# Claude Code Productivity Dashboard Specification

## Context

This spec defines Grafana dashboards for a team of 3–8 developers tracking Claude Code usage. Metrics are sourced from the OTel Collector → Prometheus pipeline. GitHub enrichment is not in scope for this build.

All developers are on seat-based plans. Cost is therefore a meaningful signal for individual developers — it reflects workflow intensity, not billing. The focus at individual and team lead level is **tokens and time**, not cost. Cost becomes the primary lens at manager level and above.

There are four dashboards, one per audience. Each dashboard is self-contained. Shared infrastructure: one Prometheus datasource, one `user_email` variable populated from `label_values(claude_code_token_usage_tokens_total, user_email)`.

---

## Design Principles

**Hero panel**: Each dashboard has exactly one hero panel — the single most important indicator for that audience. The hero panel occupies the top row and is larger than the others. All other panels on the dashboard are supporting context anchored to the hero panel's signal.

---

## Metric Reference

These are the Claude Code OTel metrics available in Prometheus. All are emitted natively when `OTEL_EXPORTER_OTLP_ENDPOINT` is set on a dev machine.

| Metric                                      | Type    | Notes                                                                                                                        |
| ------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `claude_code_token_usage_tokens_total`      | Counter | Labels: `type` (`input`, `output`, `cacheRead`, `cacheCreation`), `user_email`, `model`, `project`, `query_source`, `effort` |
| `claude_code_cost_usage_USD_total`          | Counter | Labels: `user_email`, `model`, `project`, `query_source`, `effort`                                                           |
| `claude_code_session_count_total`           | Counter | Labels: `user_email`, `project`, `start_type`                                                                                |
| `claude_code_active_time_seconds_total`     | Counter | Labels: `user_email`, `project`, `type` (`cli`, `user`) — always sum over `type` in queries                                  |
| `claude_code_lines_of_code_count_total`     | Counter | Labels: `user_email`, `project`, `type` (`added`, `removed`) — replaces spec's separate added/removed metrics                |
| `claude_code_code_edit_tool_decision_total` | Counter | Labels: `user_email`, `project`, `decision` (`accept`, `reject`), `tool_name`, `language`, `source`                          |

> `cache_read` and `cache_write` in earlier design notes correspond to `cacheRead` and `cacheCreation` in the actual `type` label values.
> `claude_code_session_count_total` schema is registered; live samples appear at session start.

---

## Dashboard 1 — Per Developer

**Audience**: Individual developer  
**Filter**: All panels filtered to `{user_email="$user_email"}` where `$user_email` defaults to the logged-in user  
**Max panels**: 12  
**Value proposition**: Feedback on personal usage patterns, prompt discipline, and workflow efficiency. Devs should watch for changes that improve token and time utilisation.

### Variables

| Variable     | Type     | Query                                                                                                |
| ------------ | -------- | ---------------------------------------------------------------------------------------------------- |
| `user_email` | Query    | `label_values(claude_code_token_usage_tokens_total, user_email)` — default to logged-in user's email |
| `time_range` | Built-in | Grafana time picker                                                                                  |

### Panels

Panels are listed in priority order. Size: `[S]` = stat card, `[G]` = time series graph, `[D]` = dual-axis or combined panel.

---

#### 1. Token Type Breakdown Over Time `[G]` ⭐ HERO

**Purpose**: Primary efficiency signal. Shows whether cache hit ratio is improving — a direct indicator of prompt discipline and prompt reuse.

**Visualisation**: Stacked area time series  
**Legend**: `input`, `output`, `cacheRead`, `cacheCreation`

```promql
# One query per token type
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", type="cacheRead"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", type="cacheCreation"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", type="input"}[$__rate_interval]))
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email", type="output"}[$__rate_interval]))
```

**Display options**: Use distinct colours per type. Add a derived field or annotation for "cache ratio" (cacheRead / total tokens) if Grafana transformations support it.

---

#### 2. Edit Acceptance Rate Over Time `[G]`

**Purpose**: Quality signal. Sustained low rate indicates poor prompting, wrong model for the task, or ignoring suggestions.

**Visualisation**: Time series, 0–100% Y axis

```promql
sum(rate(claude_code_code_edit_tool_decision_total{decision="accept",user_email="$user_email"}[$__rate_interval]))
/
sum(rate(claude_code_code_edit_tool_decision_total{user_email="$user_email"}[$__rate_interval]))
* 100
```

**Display options**: Unit = percent (0–100). Threshold lines at 50% (warning) and 70% (target) — configure to taste.

---

#### 3. Tokens Per Line of Code Over Time `[G]`

**Purpose**: Efficiency proxy scoped to this dashboard only. Spots workflow changes that affect how much token spend translates to output. Noisy by nature — treat as a directional trend, not a precise KPI.

**Visualisation**: Time series

```promql
sum(increase(claude_code_token_usage_tokens_total{user_email="$user_email"}[$__rate_interval]))
/
(
  sum(increase(claude_code_lines_of_code_count_total{type="added",user_email="$user_email"}[$__rate_interval]))
  + sum(increase(claude_code_lines_of_code_count_total{type="removed",user_email="$user_email"}[$__rate_interval]))
)
```

**Display options**: No unit. Label axis "tokens / line". Smooth the line (use longer rate interval if too noisy, e.g. `[1h]`).

---

#### 4. Active Time vs Sessions `[D]`

**Purpose**: Reveals engagement depth. Many short sessions = exploratory or interruptive use. Fewer long sessions = integrated into focused workflow. The ratio shifts when working patterns change.

**Visualisation**: Dual-axis time series — active time (seconds, left axis) and session count (right axis), both as bars or lines over time

```promql
# Active time (sum over type=cli and type=user)
sum(increase(claude_code_active_time_seconds_total{user_email="$user_email"}[$__interval]))

# Sessions
sum(increase(claude_code_session_count_total{user_email="$user_email"}[$__interval]))
```

**Display options**: Use `$__interval` so bars align to the time range resolution. Label axes clearly.

---

#### 5. Token Usage Over Time `[G]`

**Purpose**: Baseline volume trend. Contextualises the type breakdown panel.

**Visualisation**: Time series (total tokens, all types combined)

```promql
sum(rate(claude_code_token_usage_tokens_total{user_email="$user_email"}[$__rate_interval]))
```

---

#### 6. Model Usage `[G]`

**Purpose**: Confirms the developer is using the intended model. Catches accidental use of expensive models, or reveals deliberate model choices.

**Visualisation**: Bar chart or pie chart — token volume by model over the selected time range

```promql
sum by (model) (increase(claude_code_token_usage_tokens_total{user_email="$user_email"}[$__range]))
```

**Display options**: Use bar chart for time-range totals. Label each bar with model name.

---

#### 7. Average Session Duration `[G]`

**Purpose**: Trend in typical session length over time — rising average indicates deeper workflow integration.

```promql
sum(increase(claude_code_active_time_seconds_total{user_email="$user_email"}[$__range]))
/
sum(increase(claude_code_session_count_total{user_email="$user_email"}[$__range]))
```

**Display options**: Unit = seconds (auto-format to minutes). Time series line.

---

#### 8. Lines of Code (Net) `[G]`

**Purpose**: Output volume trend over the selected time range.

```promql
sum(increase(claude_code_lines_of_code_count_total{type="added",user_email="$user_email"}[$__range]))
- sum(increase(claude_code_lines_of_code_count_total{type="removed",user_email="$user_email"}[$__range]))
```

**Display options**: Time series showing net lines over time. Optionally overlay added and removed as a stacked area.

---

#### 9. AI Response Time vs Developer Input Time `[G]`

**Purpose**: Shows how session time is split between waiting for the AI (`type=cli`) and the developer actively typing or reviewing (`type=user`). A rising CLI proportion suggests longer, more complex requests; a high user proportion suggests frequent short exchanges or heavy review time.

**Visualisation**: Stacked area time series, two series

```promql
# AI response time
sum(rate(claude_code_active_time_seconds_total{type="cli", user_email="$user_email"}[$__rate_interval]))

# Developer input/review time
sum(rate(claude_code_active_time_seconds_total{type="user", user_email="$user_email"}[$__rate_interval]))
```

**Display options**: Unit = seconds/s (rate). Legend: `cli` = AI, `user` = Developer. Stacked so the total line is visible.

---

## Dashboard 2 — Team Lead

**Audience**: Engineering team lead  
**Filter**: No per-user filter applied. All developers visible.  
**Max panels**: 10  
**Value proposition**: Identify adoption outliers, coach on prompting, spot engagement pattern shifts. Focus is tokens and time — not cost.

### Variables

| Variable     | Type     | Query               |
| ------------ | -------- | ------------------- |
| `time_range` | Built-in | Grafana time picker |

### Panels

---

#### 1. Acceptance Rate Trend — All Developers `[G]` ⭐ HERO

**Purpose**: Best coaching signal. Spot team-wide drops after model updates, configuration changes, or onboarding. Individual lines per developer reveal who is improving and who needs a conversation.

**Visualisation**: Multi-line time series, one line per `user_email`

```promql
sum by (user_email) (rate(claude_code_code_edit_tool_decision_total{decision="accept"}[$__rate_interval]))
/
sum by (user_email) (rate(claude_code_code_edit_tool_decision_total[$__rate_interval]))
* 100
```

**Display options**: Unit = percent (0–100). Threshold bands at 50% (warning) and 70% (target).

---

#### 2. Edit Acceptance Rate by Developer `[T]`

**Purpose**: Snapshot view ranking developers by acceptance rate. Pair with the hero trend to distinguish a temporary dip from a sustained problem.

**Visualisation**: Table, one row per developer, sortable ascending

```promql
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total{decision="accept"}[$__range]))
/
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total[$__range]))
* 100
```

**Display options**: Unit = percent. Threshold colouring (red < 50%, yellow 50–70%, green > 70%). Include absolute accepted/total counts as additional columns via separate queries.

---

#### 3. Active Time vs Sessions by Developer `[G]`

**Purpose**: Engagement pattern per developer. Pair with acceptance rate to diagnose low performers (low acceptance + short sessions = prompting problems; low acceptance + long sessions = model fit issue).

**Visualisation**: Grouped bar chart — one group per developer, two bars per group (active time and sessions). Prefer this over a table; use a table only if more than ~6 developers make the chart unreadable.

```promql
# Active time
sum by (user_email) (increase(claude_code_active_time_seconds_total[$__range]))

# Sessions
sum by (user_email) (increase(claude_code_session_count_total[$__range]))
```

**Display options**: Dual Y axes or normalised if scales differ significantly.

---

#### 4. Average Session Length by Developer `[G]`

**Purpose**: Trends in session depth over time. A rising average typically indicates deeper integration into workflow.

**Visualisation**: Multi-line time series, one line per developer

```promql
sum by (user_email) (increase(claude_code_active_time_seconds_total[$__rate_interval]))
/
sum by (user_email) (increase(claude_code_session_count_total[$__rate_interval]))
```

**Display options**: Unit = seconds (auto-format to minutes).

---

#### 5. Token Usage by Developer `[G]`

**Purpose**: Volume comparison. Reveals who is and is not using Claude Code.

**Visualisation**: Bar chart, one bar per developer, for the selected time range

```promql
sum by (user_email) (increase(claude_code_token_usage_tokens_total[$__range]))
```

---

#### 6. Per Developer, Per Model Token Usage `[G]`

**Purpose**: Shows which models each developer is using. Flags unintended model use across the team.

**Visualisation**: Stacked bar chart — one bar per developer, stacked by model. Use a table as fallback if more than ~6 developers or ~4 models make the chart unreadable.

```promql
sum by (user_email, model) (increase(claude_code_token_usage_tokens_total[$__range]))
```

---

#### 7. Top Consumers Right Now `[G]`

**Purpose**: Live view of who is actively using Claude Code at this moment.

**Visualisation**: Horizontal bar chart, top 5 by current token rate. Use a table as fallback.

```promql
topk(5, sum by (user_email) (rate(claude_code_token_usage_tokens_total[5m])))
```

**Display options**: Auto-refresh every 30s. Short time window (5m) for "right now" feel.

---

## Dashboard 3 — Engineering Manager

**Audience**: Engineering manager  
**Filter**: No per-user filter. Team aggregates and per-user breakdowns both visible.  
**Max panels**: 10  
**Value proposition**: Cost governance, adoption visibility, efficiency at a glance. Cost is the primary lens here.

### Panels

---

#### 1. Weekly Summary Table `[T]`

**Purpose**: Single panel to scan the whole team. Replaces several individual panels.

**Columns**: `user_email`, `cost_usd`, `tokens`, `sessions`, `active_time_hours`, `acceptance_rate_%`

```promql
# One query per column, joined in Grafana via table transformation
sum by (user_email) (increase(claude_code_cost_usage_USD_total[$__range]))
sum by (user_email) (increase(claude_code_token_usage_tokens_total[$__range]))
sum by (user_email) (increase(claude_code_session_count_total[$__range]))
sum by (user_email) (increase(claude_code_active_time_seconds_total[$__range]))
sum by (user_email) (increase(claude_code_code_edit_tool_decision_total{decision="accept"}[$__range]))
  / sum by (user_email) (increase(claude_code_code_edit_tool_decision_total[$__range])) * 100
```

---

#### 2. Total Team Cost — MTD `[T]`

```promql
sum(increase(claude_code_cost_usage_USD_total[30d]))
```

**Display options**: Unit = USD. Stat card is acceptable here — this is a single point-in-time total, not a trend. Pair with the projected cost panel.

---

#### 3. Projected Monthly Cost `[T]`

**Purpose**: Forward-looking spend signal.

```promql
# Daily rate × 30
sum(rate(claude_code_cost_usage_USD_total[7d])) * 86400 * 30
```

**Display options**: Unit = USD. Stat card is acceptable — single forward projection. Pair with MTD card.

---

#### 4. Cost Trend — Daily, 30-Day Window `[G]` ⭐ HERO

```promql
sum(increase(claude_code_cost_usage_USD_total[$__interval]))
```

**Display options**: Bar chart aligned to day intervals. X axis = date. All other panels on this dashboard provide context for understanding this trend.

---

#### 5. Overall Model Usage `[G]`

**Purpose**: Team-level model distribution. Informs whether the team is using the right models for the right tasks.

**Visualisation**: Pie chart or bar chart — token volume by model, all developers combined

```promql
sum by (model) (increase(claude_code_token_usage_tokens_total[$__range]))
```

---

#### 6. Cost Per Line of Code — Team `[S]`

**Purpose**: Rough efficiency proxy. Direction matters more than the absolute number.

```promql
sum(increase(claude_code_cost_usage_USD_total[$__range]))
/
(
  sum(increase(claude_code_lines_of_code_count_total{type="added"}[$__range]))
  + sum(increase(claude_code_lines_of_code_count_total{type="removed"}[$__range]))
)
```

**Display options**: Unit = USD / line (format as currency with 4 decimal places or scientific notation).

---

#### 7. Team-Wide Edit Acceptance Rate Trend `[G]`

**Purpose**: Aggregate quality signal anchored to the cost trend. A falling acceptance rate while cost rises is the key risk signal for this audience.

```promql
sum(rate(claude_code_code_edit_tool_decision_total{decision="accept"}[$__rate_interval]))
/ sum(rate(claude_code_code_edit_tool_decision_total[$__rate_interval])) * 100
```

---

#### 8. Active Time vs Sessions — Team Total `[D]`

**Purpose**: Team-level engagement pattern. Useful when onboarding new developers or after tooling changes.

```promql
# Active time
sum(increase(claude_code_active_time_seconds_total[$__interval]))

# Sessions
sum(increase(claude_code_session_count_total[$__interval]))
```

---

#### 9. Usage Distribution — Sessions by Developer `[G]`

**Purpose**: Are 1–2 devs doing 80% of the usage? Shows adoption spread.

**Visualisation**: Bar chart, one bar per developer, session count

```promql
sum by (user_email) (increase(claude_code_session_count_total[$__range]))
```

---

#### 10. Total AI-Assisted Hours — Team `[S]`

```promql
sum(increase(claude_code_active_time_seconds_total[$__range])) / 3600
```

**Display options**: Unit = hours.

---

## Dashboard 4 — Senior Management

**Audience**: Senior management / leadership  
**Filter**: None. All aggregates, no dev-level breakdown.  
**Max panels**: 6  
**Value proposition**: Is the AI tooling investment being used? Is the trend positive? What is it costing? One screen, no scrolling.

> No model breakdown at this level. No individual developer data.

### Panels

---

#### 1. AI Tooling Spend — MTD vs Prior Month `[T]` pair

```promql
# MTD
sum(increase(claude_code_cost_usage_USD_total[30d]))

# Prior month (offset)
sum(increase(claude_code_cost_usage_USD_total[30d] offset 30d))
```

**Display options**: Two side-by-side stat cards with delta indicator (% change).

---

#### 2. Edit Acceptance Rate — Trend `[G]` ⭐ HERO

**Purpose**: "Is the AI actually useful?" Directional signal for leadership. The single most important quality indicator at this level — a sustained upward trend justifies the investment.

```promql
sum(rate(claude_code_code_edit_tool_decision_total{decision="accept"}[$__rate_interval]))
/ sum(rate(claude_code_code_edit_tool_decision_total[$__rate_interval])) * 100
```

**Display options**: Single line, 30–90 day window typical.

---

#### 3. Total AI-Assisted Development Hours `[T]`

```promql
sum(increase(claude_code_active_time_seconds_total[$__range])) / 3600
```

---

#### 4. Team Adoption Rate `[T]`

**Purpose**: % of developers active in the last 7 days, out of all developers seen in the last 30 days. No hardcoded headcount — team size is derived from the data itself.

```promql
count(sum by (user_email) (increase(claude_code_session_count_total[7d])) > 0)
/
count(sum by (user_email) (increase(claude_code_session_count_total[30d])) > 0)
* 100
```

**Display options**: Unit = percent. This naturally tracks onboarding — new developers appear in the denominator once they have their first session.

---

#### 5. Monthly Cost Trend — Rolling `[G]`

```promql
sum(increase(claude_code_cost_usage_USD_total[$__interval]))
```

**Display options**: Bar chart at monthly resolution. Set time range default to 6 months.

---

#### 6. Average Cost Per Developer Per Month `[T]`

Team size derived from distinct active users in the last 30 days — no hardcoded headcount.

```promql
sum(increase(claude_code_cost_usage_USD_total[30d]))
/
count(sum by (user_email) (increase(claude_code_cost_usage_USD_total[30d])) > 0)
```

**Display options**: Unit = USD.

---

## Implementation Notes

### Provisioning

Provision all four dashboards via Grafana's file-based provisioning. Place JSON exports in `./grafana/dashboards/` and configure `./grafana/provisioning/dashboards/dashboards.yml` to load from that path. Check dashboard JSON into version control.

### Rate Interval

Use `$__rate_interval` (not a hardcoded window) for all `rate()` queries. Grafana sets this automatically based on the selected time range and scrape interval. Use `$__range` for `increase()` queries where you want the total over the entire selected window.

### Null Handling

Panels that use `claude_code_session_count_total` will show no data for time windows before the metric was first emitted (it fires only at session start, not retroactively). This gap is accepted — do not attempt to backfill it. Add a panel description note: "Sessions recorded from [stack start date] only."

For acceptance rate panels: if a developer has zero edit decisions in the selected window, the panel shows no data rather than zero. This is intentional — a zero denominator is not the same as a low acceptance rate. Leave as-is; Grafana's default "No data" state is correct.

For other absent metrics (developer not active in the window), prefer Grafana's "No data" display over `or vector(0)` to avoid misleading zero values.

### Scrape Interval

Assumes Prometheus scrape interval of 15s (default). If changed, recording rules are recommended for expensive queries used across multiple dashboards (e.g. acceptance rate).

### Personal Dashboard Default

Configure the per-developer dashboard so that `$user_email` defaults to `${__user.email}` (Grafana's built-in current user email variable). Each developer's Grafana login username must be set to their email address — this is enforced at account creation time. Claude Code emits the same email as the `user_email` label, so the two will match automatically.
