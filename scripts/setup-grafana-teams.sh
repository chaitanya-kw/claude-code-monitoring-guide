#!/usr/bin/env bash
# Idempotent: creates 5 teams and sets folder permissions in Grafana.
# Safe to run multiple times — skips teams that already exist.
# Run once after first `docker-compose up -d` on a fresh host.
#
# Usage:
#   ./scripts/setup-grafana-teams.sh
#   GRAFANA_URL=http://localhost:3000 GRAFANA_USER=admin GRAFANA_PASSWORD=secret ./scripts/setup-grafana-teams.sh

set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-${GF_SECURITY_ADMIN_PASSWORD:-}}"

if [[ -z "$GRAFANA_PASSWORD" ]]; then
  # Try reading from .env in the repo root
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ENV_FILE="$SCRIPT_DIR/../.env"
  if [[ -f "$ENV_FILE" ]]; then
    GRAFANA_PASSWORD="$(grep -E '^GF_SECURITY_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
  fi
fi

if [[ -z "$GRAFANA_PASSWORD" ]]; then
  echo "ERROR: GRAFANA_PASSWORD not set. Export it or ensure .env contains GF_SECURITY_ADMIN_PASSWORD." >&2
  exit 1
fi

BASE="${GRAFANA_URL}/api"
AUTH="${GRAFANA_USER}:${GRAFANA_PASSWORD}"

# ── helpers ──────────────────────────────────────────────────────────────────

gf_get()  { curl -sf -u "$AUTH" "$BASE$1"; }
gf_post() { curl -sf -u "$AUTH" -X POST -H "Content-Type: application/json" "$BASE$1" -d "$2"; }

wait_for_grafana() {
  echo "Waiting for Grafana at $GRAFANA_URL ..."
  for i in $(seq 1 30); do
    if curl -sf -o /dev/null "$GRAFANA_URL/api/health"; then
      echo "Grafana is up."
      return 0
    fi
    sleep 2
  done
  echo "ERROR: Grafana did not become healthy within 60 seconds." >&2
  exit 1
}

# Returns the numeric team ID for a given name; creates the team if missing.
ensure_team() {
  local name="$1"
  local existing
  existing="$(gf_get "/teams/search?name=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$name'))")" | python3 -c "
import sys, json
teams = json.load(sys.stdin).get('teams', [])
match = [t for t in teams if t['name'] == '$name']
print(match[0]['id'] if match else '')
")"
  if [[ -n "$existing" ]]; then
    echo "$existing"
    return
  fi
  gf_post "/teams" "{\"name\":\"$name\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['teamId'])"
}

# Sets permissions on a folder, replacing any existing team entries.
# Args: folder_uid [team_id permission]...
# Permission values: 1=Viewer, 2=Editor, 4=Admin
set_folder_permissions() {
  local folder_uid="$1"; shift
  local items="["
  local first=1
  while [[ $# -gt 0 ]]; do
    local tid=$1 perm=$2; shift 2
    [[ $first -eq 0 ]] && items+=","
    items+="{\"teamId\":$tid,\"permission\":$perm}"
    first=0
  done
  items+="]"
  gf_post "/folders/$folder_uid/permissions" "{\"items\":$items}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','ok'))"
}

# ── main ─────────────────────────────────────────────────────────────────────

wait_for_grafana

echo ""
echo "── Creating teams ───────────────────────────────────────────────────────"
DEV_ID=$(ensure_team  "Dev");   echo "  Dev   → id=$DEV_ID"
PM_ID=$(ensure_team   "PM");    echo "  PM    → id=$PM_ID"
SPM_ID=$(ensure_team  "SPM");   echo "  SPM   → id=$SPM_ID"
MGMT_ID=$(ensure_team "MGMT");  echo "  MGMT  → id=$MGMT_ID"
ADM_ID=$(ensure_team  "Admin"); echo "  Admin → id=$ADM_ID"

echo ""
echo "── Setting folder permissions ───────────────────────────────────────────"

# Per Developer — all teams can view; Admin has admin
echo -n "  Per Developer:        "
set_folder_permissions f-per-developer \
  "$DEV_ID"  1 \
  "$PM_ID"   1 \
  "$SPM_ID"  1 \
  "$MGMT_ID" 1 \
  "$ADM_ID"  4

# Team Lead — PM and above
echo -n "  Team Lead:            "
set_folder_permissions f-team-lead \
  "$PM_ID"   1 \
  "$SPM_ID"  1 \
  "$MGMT_ID" 1 \
  "$ADM_ID"  4

# Senior Project Manager — SPM and above
echo -n "  Senior Project Mgr:   "
set_folder_permissions f-spm \
  "$SPM_ID"  1 \
  "$MGMT_ID" 1 \
  "$ADM_ID"  4

# Senior Management — MGMT and above
echo -n "  Senior Management:    "
set_folder_permissions f-senior-mgmt \
  "$MGMT_ID" 1 \
  "$ADM_ID"  4

echo ""
echo "Done. Verify at ${GRAFANA_URL}/org/teams"
