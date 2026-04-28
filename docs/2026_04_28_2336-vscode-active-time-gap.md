# VS Code Extension — active_time Gap

## Problem

Developers using Claude Code via the VS Code extension emit token and cost metrics normally, but **do not emit `claude_code_active_time_seconds_total`**. This means all dashboard panels that derive from active_time show no data for those users:

- Session count (proxy: `count_over_time(active_time{type="user"})`)
- Active time totals
- Average session duration / session length
- Team Adoption Rate (uses 7d active / 30d seen ratio on active_time)
- Total AI-Assisted Development Hours

Token usage, cost, edit acceptance rate, and lines of code panels are unaffected.

## Root Cause

`active_time_seconds_total` is emitted by the Claude Code CLI's session lifecycle tracker, which monitors keypress/interaction activity inside an interactive terminal session. The VS Code extension runs Claude Code as an IDE panel process — it does not expose the same terminal session hooks, so the active_time signal is never triggered.

## Evidence (as of 2026-04-28)

Four `user_email` values are in the Prometheus label index. Only one (CLI user) has `active_time_seconds_total`. All four have `token_usage_tokens_total`:

| Developer | Tokens (200h) | active_time |
|---|---|---|
| madiha.shaikh@kilowott.com | ~59M | ✗ |
| chaitanya.chowgule@kilowott.com | ~11M | ✓ (CLI) |
| tushar.ghatwal@kilowott.com | ~4.8M | ✗ |
| ajaj.rajguru@kilowott.com | ~269K | ✗ |

## Impact on Dashboards

| Panel | CLI users | VS Code users |
|---|---|---|
| Token usage | ✓ | ✓ |
| Cost | ✓ | ✓ |
| Edit acceptance rate | ✓ | ✓ |
| Session count (proxy) | ✓ | ✗ |
| Active time | ✓ | ✗ |
| Avg session duration | ✓ | ✗ |
| Team Adoption Rate | ✓ | ✗ (undercounts) |

## Options for Resolution

1. **Token-based engagement proxy** — replace session count and active time panels with daily token volume as the usage/engagement signal for team-level views. Works for all surfaces.

2. **Ask VS Code users to use the CLI** — even occasionally, to populate active_time data. Not sustainable at scale.

3. **Wait for Anthropic to fix** — the VS Code extension may be updated to emit active_time in a future release.

4. **Hybrid panels** — show token-based metrics alongside active_time where available, using `or` in PromQL to fall back gracefully.

Option 1 is the recommended path for team/management dashboards. Per-developer dashboard can note that session data is CLI-only.
