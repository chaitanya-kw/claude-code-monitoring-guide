# Telemetry Reference — Prometheus & Loki

Source: live VM stack (`prometheus:9090`, `loki:3100`)
Generated: 2026-04-29, updated 13:50 IST
Prometheus series: 352 | Loki services: `claude-code`, `gemini-cli`

---

## How to read this document

**Prometheus** stores named numeric time series. Counters are queried as `<base>_total`. Use `rate(<metric>_total[5m])` for per-second rates, `increase(<metric>_total[1h])` for totals over a window. Labels filter series.

**Loki** stores structured log events. The `line` field is the human-readable summary. All rich context is in `structuredMetadata`. Query with `{service_name="claude-code"} | logfmt` or filter by metadata field: `{service_name="claude-code"} | logfmt | event_name="api_request"`.

**Loki stream labels** (indexed, use in `{}` selector): `service_name`, `service_version`, `project`, `os_type`

**Loki structured metadata** (not indexed, use after `| logfmt`): all other fields — `user_email`, `session_id`, `model`, `cost_usd`, etc.

---

# Part 1 — Prometheus Metrics

## claude_code — Primary project metrics

All `claude_code_*` metrics share a common set of labels. Differences per metric are noted under each entry.

### Common labels on all claude_code_* metrics

| Label | Example values | Notes |
|---|---|---|
| `user_email` | `chaitanya.chowgule@kilowott.com`, `ajaj.rajguru@kilowott.com`, `tushar.ghatwal@kilowott.com` | Primary identity label for per-dev filtering |
| `user_id` | `8c17bc2a10944aad…` | SHA-256 hash of user identity |
| `user_account_id` | `user_01Pmf3Km2vhwrs9Fzj82WinH` | Anthropic account ID |
| `user_account_uuid` | `b865382b-db28-44e1-96fc-0cc722b14afe` | Anthropic account UUID |
| `organization_id` | `d706bcff-05bb-483c-a49a-84f9aad43ed8` | Kilowott org — constant across all devs |
| `project` | `claude-code-monitoring-guide`, `unknown` | Set via `OTEL_RESOURCE_ATTRIBUTES`; `unknown` if run outside a tagged repo |
| `session_id` | `393726da-284f-423b-abb6-49fa9cf99efa` | One per CLI session; high cardinality |
| `terminal_type` | `kitty`, `windows-terminal`, `non-interactive` | Terminal environment |
| `otel_scope_name` | `com.anthropic.claude_code` | Instrumentation scope — constant |
| `otel_scope_version` | `2.1.121`, `2.1.123` | Claude Code version |

---

### `claude_code_token_usage_tokens_total`

**Type:** counter | **Unit:** tokens

Tokens consumed per API call, broken down by token category. This is the primary metric for cost attribution and cache efficiency.

**Additional labels:**

| Label | Values | Notes |
|---|---|---|
| `type` | `input`, `output`, `cacheCreation`, `cacheRead` | Split token spend by category |
| `model` | `claude-opus-4-7[1m]`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | Model used for the request |
| `effort` | `xhigh`, `medium` | Extended thinking effort level; absent when thinking disabled |
| `query_source` | `main`, `subagent`, `auxiliary` | What initiated the request: main thread, a subagent, or background work |

**Example queries:**

```promql
# Total tokens per developer (all time)
sum by (user_email) (claude_code_token_usage_tokens_total)

# Cache hit rate (fraction of tokens served from cache)
sum by (user_email) (claude_code_token_usage_tokens_total{type="cacheRead"})
/
sum by (user_email) (claude_code_token_usage_tokens_total{type=~"input|cacheRead|cacheCreation"})

# Token rate by model over last hour
sum by (model) (increase(claude_code_token_usage_tokens_total[1h]))

# Input + output tokens only (excludes cache)
sum by (user_email) (claude_code_token_usage_tokens_total{type=~"input|output"})
```

---

### `claude_code_cost_usage_USD_total`

**Type:** counter | **Unit:** USD

Cumulative API cost in USD. One series per (user, session, model, effort, query_source) combination.

**Additional labels:**

| Label | Values | Notes |
|---|---|---|
| `model` | `claude-opus-4-7[1m]`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | |
| `effort` | `xhigh`, `medium` | |
| `query_source` | `main`, `subagent`, `auxiliary` | |

**Example values:** `0.038`, `0.545`, `3.407` (cumulative USD per session)

**Example queries:**

```promql
# Total spend per developer
sum by (user_email) (claude_code_cost_usage_USD_total)

# Daily spend rate
sum by (user_email) (increase(claude_code_cost_usage_USD_total[24h]))

# Cost breakdown by model
sum by (model) (claude_code_cost_usage_USD_total)

# Cost by project
sum by (project) (claude_code_cost_usage_USD_total)
```

---

### `claude_code_active_time_seconds_total`

**Type:** counter | **Unit:** seconds

Time Claude Code was active, split by activity type.

**Additional labels:**

| Label | Values | Notes |
|---|---|---|
| `type` | `user`, `cli` | `user` = time user was interacting; `cli` = total CLI wall-clock time |

**Example values:** `61.8s` (user active), `518.3s` (cli running)

**Example queries:**

```promql
# Active time per developer (user interaction only)
sum by (user_email) (claude_code_active_time_seconds_total{type="user"})

# Sessions running right now (CLI active in last 5 min)
count by (user_email) (rate(claude_code_active_time_seconds_total{type="cli"}[5m]) > 0)
```

---

### `claude_code_lines_of_code_count_total`

**Type:** counter | **Unit:** lines

Lines of code modified by Claude Code edits.

**Additional labels:**

| Label | Values | Notes |
|---|---|---|
| `type` | `added`, `removed` | Direction of change |

**Example values:** `694` added, `126` removed (for one session)

**Example queries:**

```promql
# Net lines changed per developer
sum by (user_email) (claude_code_lines_of_code_count_total{type="added"})
- sum by (user_email) (claude_code_lines_of_code_count_total{type="removed"})

# Total edits (churn) per project
sum by (project) (claude_code_lines_of_code_count_total)
```

---

### `claude_code_code_edit_tool_decision_total`

**Type:** counter

Permission decisions made for code editing tools (Edit, Write, NotebookEdit).

**Additional labels:**

| Label | Values | Notes |
|---|---|---|
| `decision` | `accept`, `reject` | Whether the edit was allowed |
| `source` | `config` | How the decision was made |
| `tool_name` | `Edit`, `Write`, `NotebookEdit` | Which tool was gated |
| `language` | `python`, `typescript`, … | File language of the edit target |

**Example queries:**

```promql
# Acceptance rate per developer
sum by (user_email) (claude_code_code_edit_tool_decision_total{decision="accept"})
/ sum by (user_email) (claude_code_code_edit_tool_decision_total)
```

---

### `claude_code_session_count_total`

**Type:** counter

One increment per CLI session started.

**Labels:** common set only (no extra labels). Each series represents one user/session/terminal combination.

**Example queries:**

```promql
# Sessions per developer (count distinct session_id series)
count by (user_email) (claude_code_session_count_total)

# Sessions per project
count by (project) (claude_code_session_count_total)
```

---

### `claude_code_commit_count_total`

**Type:** counter

Git commits created during Claude Code sessions.

**Labels:** common set only.

**Example queries:**

```promql
# Commits per developer this week
sum by (user_email) (increase(claude_code_commit_count_total[7d]))
```

---

### `claude_code_pull_request_count_total`

**Type:** counter

Pull requests created during Claude Code sessions.

**Labels:** common set only.

---

## gemini_cli — Gemini CLI metrics

Emitted by the Gemini CLI. Uses `gemini-2.5-flash-lite` model. Appears when any team member runs the Gemini CLI with OTel enabled.

### Common labels on all gemini_cli_* metrics

| Label | Example values | Notes |
|---|---|---|
| `user_email` | `chaitanya.chowgule@kilowott.com` | |
| `model` | `gemini-2.5-flash-lite` | |
| `project` | `claude-code-monitoring-guide` | |
| `session_id` | `9f075be3-eff1-4d42-9641-9721e7ace092` | |
| `installation_id` | `61743add-e516-4827-a521-55b4ad98f377` | Stable per machine |
| `interactive` | `true` | Whether session was interactive |
| `auth_type` | `oauth-personal` | |
| `experiments_ids` | `[106018683, …]` | Long list of A/B experiment IDs — **high cardinality label, avoid grouping by this** |

---

### `gemini_cli_token_usage_total`

**Type:** counter | **Unit:** tokens

**`type` label values:**

| Value | Meaning |
|---|---|
| `input` | Prompt tokens |
| `output` | Completion tokens |
| `thought` | Internal thinking/reasoning tokens |
| `cache` | Cached context tokens |
| `tool` | Tokens used in tool calls |

**Example values:** `input=8638`, `output=581`, `thought=905`, `cache=0`, `tool=0`

**Example queries:**

```promql
# Total Gemini tokens
sum by (user_email, type) (gemini_cli_token_usage_total)

# Thinking token fraction
sum(gemini_cli_token_usage_total{type="thought"})
/ sum(gemini_cli_token_usage_total{type=~"input|output|thought"})
```

---

### `gemini_cli_session_count_total`

**Type:** counter — Sessions started.

### `gemini_cli_api_request_count_total`

**Type:** counter — API requests, tagged by `model` and `status`.

### `gemini_cli_file_operation_count_total`

**Type:** counter — File operations (`create`, `read`, `update`).

### `gemini_cli_tool_call_count_total`

**Type:** counter — Tool calls, tagged by function name and success.

### `gemini_cli_keychain_availability_count_total`

**Type:** counter — Keychain availability checks.

### `gemini_cli_token_storage_type_count_total`

**Type:** counter — Token storage type initializations.

### `gemini_cli_api_request_latency_milliseconds`

**Type:** histogram — API request latency in milliseconds.

### `gemini_cli_model_routing_latency_milliseconds`

**Type:** histogram — Model routing decision latency.

### `gemini_cli_startup_duration_milliseconds`

**Type:** histogram — CLI startup time broken down by initialization phase.

### `gemini_cli_tool_call_latency_milliseconds`

**Type:** histogram — Tool call latency in milliseconds.

---

## gen_ai_client — OpenTelemetry GenAI semantic conventions

Provider-agnostic GenAI metrics following the OTel semantic conventions. Emitted by the Gemini CLI via the OTel GenAI instrumentation layer.

### `gen_ai_client_operation_duration_seconds`

**Type:** histogram — End-to-end GenAI operation duration.

**Labels:** `gen_ai_system` (e.g. `vertex_ai`), `gen_ai_operation_name`, `gen_ai_request_model`, `server_address`

### `gen_ai_client_token_usage`

**Type:** histogram — Input and output tokens, tagged by `gen_ai_token_type` (`input`, `output`).

---

## Infrastructure metrics (Prometheus self-monitoring)

These are emitted by Prometheus, the OTel collector Go runtime, and the OS. Not useful for productivity dashboards. Listed here for completeness.

| Namespace | What it covers |
|---|---|
| `go_*` | Go runtime: GC, goroutines, memory, scheduler |
| `process_*` | OS process: CPU, memory, file descriptors |
| `net_conntrack_*` | Network connection tracking |
| `prometheus_*` | Prometheus internals: scrape pools, TSDB, WAL, query engine |
| `promhttp_*` | HTTP handler for `/metrics` scrape endpoint |
| `scrape_*` / `up` | Scrape health per target |

See the original listing in git history for full descriptions.

---

# Part 2 — Loki Logs

## Stream labels (use in `{}` selector)

| Label | Values seen | Notes |
|---|---|---|
| `service_name` | `claude-code`, `gemini-cli` | Primary selector |
| `service_version` | `2.1.121`, `2.1.123` (Claude), `v24.14.1` (Gemini) | CLI version |
| `project` | `claude-code-monitoring-guide`, `unknown` | Repo context |
| `os_type` | `windows`, `linux` | Developer OS |

---

## claude-code events

Each log line is a Claude Code event. The `line` field is a short human-readable summary. Filter by event type with `| logfmt | event_name="<name>"`.

### Event types

| `event_name` | Line example | When emitted |
|---|---|---|
| `api_request` | `claude_code.api_request` | Each call to the Anthropic API |
| `api_response` | `claude_code.api_response` | When API response is received |
| `tool_decision` | `claude_code.tool_decision` | When a tool use permission is evaluated |
| `tool_result` | `claude_code.tool_result` | When a tool finishes executing |
| `hook_execution_complete` | `claude_code.hook_execution_complete` | When a Claude Code hook runs |

---

### Structured metadata — `api_request`

| Field | Example | Notes |
|---|---|---|
| `event_name` | `api_request` | |
| `event_timestamp` | `2026-04-29T11:07:36.448Z` | When event occurred |
| `session_id` | `7ef38ec7-9605-4df0-8463-474fd90f0e2b` | Session that made the call |
| `prompt_id` | `49f4a1b2-dd9c-490e-94d3-62d3360d2a6f` | Prompt turn ID |
| `request_id` | `req_011CaXxQj5FQPEj24g8Xtv6A` | Anthropic request ID |
| `model` | `claude-opus-4-7[1m]` | Model called |
| `effort` | `xhigh` | Extended thinking effort |
| `query_source` | `repl_main_thread`, `sdk` | What triggered the call |
| `speed` | `normal` | |
| `duration_ms` | `4561` | API call wall-clock time |
| `input_tokens` | `1` | Non-cache input tokens |
| `output_tokens` | `256` | Output tokens |
| `cache_creation_tokens` | `380` | Tokens written to cache this call |
| `cache_read_tokens` | `115866` | Tokens read from cache this call |
| `cost_usd` | `0.066713` | Per-request USD cost |
| `user_email` | `ajaj.rajguru@kilowott.com` | |
| `user_id` | `593a40fe…` | |
| `organization_id` | `d706bcff-05bb-483c-a49a-84f9aad43ed8` | |
| `terminal_type` | `windows-terminal` | |
| `host_arch` | `amd64` | |
| `os_version` | `10.0.22621` | |

**Key use:** per-request cost, cache efficiency, latency distribution — data that Prometheus only has as aggregated counters.

**Example LogQL:**

```logql
# All API requests for a developer
{service_name="claude-code"} | logfmt | event_name="api_request" | user_email="ajaj.rajguru@kilowott.com"

# Requests using extended thinking
{service_name="claude-code"} | logfmt | event_name="api_request" | effort="xhigh"

# Average API latency (metric query)
avg_over_time(
  {service_name="claude-code"} | logfmt | event_name="api_request" | unwrap duration_ms [$__range]
)

# Cache read tokens per request over time
sum_over_time(
  {service_name="claude-code"} | logfmt | event_name="api_request" | unwrap cache_read_tokens [1h]
)
```

---

### Structured metadata — `tool_result`

| Field | Example | Notes |
|---|---|---|
| `event_name` | `tool_result` | |
| `tool_name` | `Edit`, `Bash`, `Write`, `Read` | Which tool ran |
| `tool_use_id` | `toolu_01HZ5mzXicUXveKKoa1MDAu2` | Links to the tool_decision event |
| `tool_input_size_bytes` | `351` | Size of input sent to tool |
| `tool_result_size_bytes` | `129` | Size of tool output |
| `duration_ms` | `11` | Tool execution time |
| `success` | `true` | Whether tool succeeded |
| `decision_type` | `accept` | Permission decision that allowed this |
| `decision_source` | `config` | What granted permission |
| `session_id`, `prompt_id`, `user_email` | — | As above |

**Example LogQL:**

```logql
# Bash tool executions with duration
{service_name="claude-code"} | logfmt | event_name="tool_result" | tool_name="Bash"

# Failed tool calls
{service_name="claude-code"} | logfmt | event_name="tool_result" | success="false"

# Average tool latency by tool name
avg by (tool_name) (
  avg_over_time(
    {service_name="claude-code"} | logfmt | event_name="tool_result" | unwrap duration_ms [$__range]
  )
)
```

---

### Structured metadata — `tool_decision`

| Field | Example | Notes |
|---|---|---|
| `event_name` | `tool_decision` | |
| `tool_name` | `Edit`, `Bash` | Tool being gated |
| `tool_use_id` | `toolu_01HZ5mzXicUXveKKoa1MDAu2` | Links to tool_result |
| `decision` | `accept`, `reject` | Permission outcome |
| `source` | `config` | Decision source |
| `session_id`, `prompt_id`, `user_email` | — | As above |

---

### Structured metadata — `hook_execution_complete`

| Field | Example | Notes |
|---|---|---|
| `event_name` | `hook_execution_complete` | |
| `hook_name` | `Stop` | Hook type |
| `hook_event` | `Stop` | |
| `hook_source` | `merged` | |
| `num_hooks` | `1` | |
| `num_success` | `1` | |
| `num_blocking` | `0` | |
| `num_non_blocking_error` | `0` | |
| `num_cancelled` | `0` | |
| `total_duration_ms` | `4` | |

---

## gemini-cli events

### Event types

| `event_name` | Line example | When emitted |
|---|---|---|
| `gemini_cli.api_request` | `API request to gemini-2.5-flash-lite.` | Each API call sent |
| `gemini_cli.api_response` | `API response from gemini-2.5-flash-lite. Status: 200. Duration: 5799ms.` | API response received |
| `gen_ai.client.inference.operation.details` | `GenAI operation details from gemini-2.5-flash-lite. Status: 200.` | OTel GenAI span details |
| `gemini_cli.plan.approval_mode_duration` | `Approval mode default was active for 38926ms.` | When plan approval phase ends |
| `gemini_cli.slash_command` | `Slash command: quit.` | When user runs a `/` command |

---

### Structured metadata — `gemini_cli.api_response`

| Field | Example | Notes |
|---|---|---|
| `event_name` | `gemini_cli.api_response` | |
| `model` | `gemini-2.5-flash-lite` | |
| `duration_ms` | `5799` | API latency |
| `http_status_code` | `200` | |
| `input_token_count` | `8638` | |
| `output_token_count` | `581` | |
| `thoughts_token_count` | `905` | Thinking tokens |
| `tool_token_count` | `0` | |
| `cached_content_token_count` | `0` | |
| `total_token_count` | `10124` | |
| `finish_reasons` | `STOP` | |
| `prompt_id` | `…` | |
| `session_id` | `9f075be3-…` | |
| `user_email` | `chaitanya.chowgule@kilowott.com` | |
| `span_id`, `trace_id` | `…` | OTel trace correlation |
| `response_text` | _(truncated)_ | Full response text — large field |
| `role` | `model` | |
| `host_name` | `pop-os` | Machine hostname |
| `process_owner` | `chaits` | OS user |
| `installation_id` | `61743add-…` | Stable device ID |

---

### Structured metadata — `gemini_cli.api_request`

| Field | Example | Notes |
|---|---|---|
| `model` | `gemini-2.5-flash-lite` | |
| `prompt_id` | `…` | |
| `request_text` | _(truncated)_ | Full prompt text — large field |
| `role` | `user` | |
| `span_id`, `trace_id` | `…` | OTel trace IDs |
| `flags` | `…` | Feature flags active |
| `session_id`, `user_email` | — | As above |

---

### Structured metadata — `gen_ai.client.inference.operation.details`

| Field | Example | Notes |
|---|---|---|
| `gen_ai_operation_name` | `chat` | |
| `gen_ai_provider_name` | `google_ai_studio` | |
| `gen_ai_request_model` | `gemini-2.5-flash-lite` | |
| `gen_ai_response_model` | `gemini-2.5-flash-lite-preview-06-17` | Resolved model name |
| `gen_ai_request_temperature` | `1` | |
| `gen_ai_request_top_k` | `40` | |
| `gen_ai_request_top_p` | `0.95` | |
| `gen_ai_response_finish_reasons` | `STOP` | |
| `gen_ai_response_id` | `…` | |
| `gen_ai_usage_input_tokens` | `8638` | |
| `gen_ai_usage_output_tokens` | `581` | |
| `server_address` | `generativelanguage.googleapis.com` | |
| `server_port` | `443` | |
| `span_id`, `trace_id` | `…` | Full OTel trace correlation |

---

### Common Gemini structured metadata (all events)

| Field | Example | Notes |
|---|---|---|
| `auth_type` | `oauth-personal` | |
| `installation_id` | `61743add-e516-4827-a521-55b4ad98f377` | Stable per machine |
| `interactive` | `true` | |
| `host_name` | `pop-os` | |
| `host_arch` | `amd64` | |
| `process_owner` | `chaits` | |
| `process_pid` | `…` | |
| `process_runtime_name` | `nodejs` | |
| `process_runtime_version` | `24.14.1` | |
| `process_command` | `/home/chaits/.nvm/…/gemini` | |
| `experiments_ids` | `[106018683, …]` | Long list of A/B experiment IDs — omit from dashboards |

---

## Session counting with Loki

Because `session_id` is structured metadata (not a stream label), count sessions with:

```logql
# Sessions per developer today
count by (user_email) (
  count_over_time(
    {service_name="claude-code"} | logfmt | event_name="api_request" [$__range]
  ) by (user_email, session_id)
)
```

This is more accurate than using `claude_code_session_count_total` in Prometheus because it counts sessions that actually made API calls.
