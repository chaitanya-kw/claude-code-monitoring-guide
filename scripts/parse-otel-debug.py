#!/usr/bin/env python3
"""
Parse OTel collector debug exporter output and summarise what attributes
are arriving at resource level vs datapoint level.

Usage:
  docker-compose logs --tail=2000 otel-collector 2>&1 | python3 scripts/parse-otel-debug.py
  docker-compose logs --tail=2000 otel-collector 2>&1 | python3 scripts/parse-otel-debug.py --raw

Flags:
  --raw   dump every parsed ResourceMetrics block as JSON instead of the summary
"""

import sys
import re
import json
from collections import defaultdict

# ── parser state ────────────────────────────────────────────────────────────

ATTR_RE   = re.compile(r'->\s+(.+?):\s+\w+\((.+)\)$')
NAME_RE   = re.compile(r'->\s+Name:\s+(.+)$')
TYPE_RE   = re.compile(r'->\s+DataType:\s+(.+)$')
SCOPE_RE  = re.compile(r'InstrumentationScope\s+(.+)$')

def parse_logs(lines):
    blocks = []
    cur = None
    in_resource_attrs = False
    in_dp_attrs = False
    cur_metric = None

    for raw in lines:
        # strip docker-compose / timestamp prefix
        line = re.sub(r'^[^\|]+\|\s*', '', raw).rstrip()
        line = re.sub(r'^\S+\s+\S+\s+(info|warn|error)\s+', '', line)

        if 'ResourceMetrics #' in line:
            if cur:
                blocks.append(cur)
            cur = {'resource_attrs': {}, 'scope': '', 'metrics': []}
            in_resource_attrs = False
            in_dp_attrs = False
            cur_metric = None
            continue

        if cur is None:
            continue

        if line.strip() == 'Resource attributes:':
            in_resource_attrs = True
            in_dp_attrs = False
            continue

        if 'ScopeMetrics #' in line:
            in_resource_attrs = False
            continue

        m = SCOPE_RE.search(line)
        if m:
            cur['scope'] = m.group(1).strip()
            continue

        if 'Metric #' in line:
            cur_metric = {'name': '', 'type': '', 'dp_attrs': defaultdict(set)}
            cur['metrics'].append(cur_metric)
            in_dp_attrs = False
            continue

        if cur_metric:
            m = NAME_RE.search(line)
            if m:
                cur_metric['name'] = m.group(1).strip()
                continue
            m = TYPE_RE.search(line)
            if m:
                cur_metric['type'] = m.group(1).strip()
                continue

        if 'Data point attributes:' in line:
            in_resource_attrs = False
            in_dp_attrs = True
            continue

        if line.strip().startswith('->'):
            m = ATTR_RE.search(line)
            if not m:
                continue
            key, val = m.group(1).strip(), m.group(2).strip()
            if in_resource_attrs and cur:
                cur['resource_attrs'][key] = val
            elif in_dp_attrs and cur_metric:
                cur_metric['dp_attrs'][key].add(val)

    if cur:
        blocks.append(cur)
    return blocks


# ── aggregation ──────────────────────────────────────────────────────────────

def summarise(blocks):
    resource_keys   = defaultdict(set)   # key -> example values
    metric_dp_keys  = defaultdict(set)   # metric_name -> set of dp attr keys
    metric_types    = {}                  # metric_name -> DataType
    scopes          = set()

    for b in blocks:
        for k, v in b['resource_attrs'].items():
            resource_keys[k].add(v)
        if b['scope']:
            scopes.add(b['scope'])
        for m in b['metrics']:
            if not m['name']:
                continue
            metric_types[m['name']] = m['type']
            for k, vals in m['dp_attrs'].items():
                metric_dp_keys[m['name']].add(k)

    return resource_keys, metric_dp_keys, metric_types, scopes


# ── output ───────────────────────────────────────────────────────────────────

def print_summary(blocks):
    resource_keys, metric_dp_keys, metric_types, scopes = summarise(blocks)

    print(f"\n{'='*70}")
    print(f"  OTel collector debug summary  ({len(blocks)} ResourceMetrics blocks)")
    print(f"{'='*70}\n")

    print("INSTRUMENTATION SCOPES")
    for s in sorted(scopes):
        print(f"  {s}")
    print()

    print("RESOURCE ATTRIBUTES  (arrive at collector, not automatically Prometheus labels)")
    print(f"  {'Key':<40} Example value(s)")
    print(f"  {'-'*40} {'-'*28}")
    for k in sorted(resource_keys):
        examples = ', '.join(sorted(resource_keys[k])[:3])
        if len(resource_keys[k]) > 3:
            examples += f' … (+{len(resource_keys[k])-3})'
        print(f"  {k:<40} {examples}")
    print()

    print("METRICS  (datapoint-level attributes become Prometheus labels)")
    for name in sorted(metric_dp_keys):
        dtype = metric_types.get(name, '?')
        dp_keys = sorted(metric_dp_keys[name])
        print(f"\n  {name}  [{dtype}]")
        if dp_keys:
            for k in dp_keys:
                promoted = k in resource_keys
                tag = " ← also a resource attr" if promoted else ""
                print(f"    · {k}{tag}")
        else:
            print("    (no datapoint attributes)")

    # highlight resource attrs not promoted to any metric
    all_dp_keys = set()
    for keys in metric_dp_keys.values():
        all_dp_keys |= keys
    dropped = sorted(set(resource_keys) - all_dp_keys)
    if dropped:
        print(f"\n{'='*70}")
        print("RESOURCE ATTRS NOT PROMOTED TO ANY METRIC DATAPOINT")
        print("(these are invisible to Prometheus — add transform rules to expose them)")
        for k in dropped:
            examples = ', '.join(sorted(resource_keys[k])[:2])
            print(f"  {k:<40} e.g. {examples}")
    print()


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    raw_mode = '--raw' in sys.argv
    lines = sys.stdin.readlines()
    blocks = parse_logs(lines)

    if not blocks:
        print("No ResourceMetrics blocks found in input.")
        print("Make sure the debug exporter is running with verbosity: detailed")
        print("and try increasing --tail (e.g. --tail=5000).")
        sys.exit(1)

    if raw_mode:
        # serialise defaultdict sets for JSON
        def fix(b):
            return {
                'resource_attrs': b['resource_attrs'],
                'scope': b['scope'],
                'metrics': [
                    {'name': m['name'], 'type': m['type'],
                     'dp_attrs': {k: sorted(v) for k, v in m['dp_attrs'].items()}}
                    for m in b['metrics']
                ]
            }
        print(json.dumps([fix(b) for b in blocks], indent=2))
    else:
        print_summary(blocks)


if __name__ == '__main__':
    main()
