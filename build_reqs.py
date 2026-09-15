#!/usr/bin/env python3
"""Build data/reqs.json for the Account Master dashboard from the Salesforce Req export.

Grain in: Requisition Item (one row per RI-#######).
Grain out: Requisition (one row per Req-#######), items aggregated.

Source: report1789478971623.csv  (cp1252, NOT utf-8)
"""
import json, sys, re
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/report1789478971623.csv'
MASTER = 'app/data/master.json'
OUT = 'app/data/reqs.json'

# Parent-account values that are sales channels rather than a supplying health system.
MARKETPLACE = re.compile(r'^(shopify|ebay)\b', re.I)

df = pd.read_csv(SRC, encoding='cp1252')
df.columns = [c.strip() for c in df.columns]

PARENT = 'Parent Account: Account Name'
BUYER  = 'Account Name'
REQ    = 'Requisition Number'
ITEM   = 'Requisition Item #'
MAT    = 'Material: Material Name'
SELL   = 'Parent Account: Sell To Account Coordinator: Full Name'
SELL2  = 'Sell To Account Coordinator: Full Name'
ACQ    = 'Acquisition Coordinator: Full Name'
CONS   = 'Consignment Percent'
PCONS  = 'Parent Account: Consignment Percent'
SUB    = 'Subtotal'
MARGIN = 'rL Sales Team Estimated Margin'

# --- master.json parents, for rollup matching -------------------------------
master = json.load(open(MASTER))
parents = {s['parent'] for s in master['systems']}


def bucket(p):
    if not isinstance(p, str) or not p.strip():
        return 'none'
    return 'market' if MARKETPLACE.match(p.strip()) else 'health'


df['_bucket'] = df[PARENT].map(bucket)

rows = []
for req, g in df.groupby(REQ, sort=False):
    p = g[PARENT].dropna()
    p = p.iloc[0] if len(p) else None
    b = bucket(p)

    # coordinator: prefer the parent-level sell-to, fall back to account-level
    def first(col):
        s = g[col].dropna()
        return s.iloc[0] if len(s) else None

    sell = first(SELL) or first(SELL2)
    acq = first(ACQ)

    cons = g[CONS].dropna()
    if not len(cons):
        cons = g[PCONS].dropna()
    cons = float(cons.iloc[0]) if len(cons) else None

    mats = [m for m in g[MAT].dropna().unique()]
    margin = g[MARGIN].dropna()

    rows.append({
        'id': req,
        'items': int(len(g)),
        'bucket': b,
        # account is only populated when it resolves to a supplying health system
        'account': p if b == 'health' else None,
        'matched': bool(b == 'health' and p in parents),
        'channel': p if b == 'market' else None,
        'buyer': (g[BUYER].dropna().iloc[0] if g[BUYER].notna().any() else None),
        'material': (mats[0] if mats else None),
        'moreMats': max(0, len(mats) - 1),
        'sell': sell,
        'acq': acq,
        'cons': cons,
        'sub': round(float(g[SUB].sum()), 2),
        'margin': (round(float(margin.sum()), 2) if len(margin) else None),
        'marginItems': int(len(margin)),
    })

rows.sort(key=lambda r: -abs(r['sub']))


byBucket = {'health': 0, 'market': 0, 'none': 0}
for r in rows:
    byBucket[r['bucket']] += 1

# per-health-system rollup
byParent = {}
for r in rows:
    if r['bucket'] != 'health':
        continue
    k = r['account']
    e = byParent.setdefault(k, {'reqs': 0, 'items': 0, 'sub': 0.0,
                                'margin': 0.0, 'matched': r['matched']})
    e['reqs'] += 1
    e['items'] += r['items']
    e['sub'] += r['sub']
    e['margin'] += (r['margin'] or 0.0)
for e in byParent.values():
    e['sub'] = round(e['sub'], 2)
    e['margin'] = round(e['margin'], 2)

# drop empty keys — the renderer already treats missing as absent, and this
# roughly halves the payload across 8k rows
KEEP = {'id', 'items', 'bucket', 'sub'}
rows = [{k: v for k, v in r.items()
         if k in KEEP or (v is not None and v != 0 and v is not False)}
        for r in rows]

out = {
    'generated': pd.Timestamp.today().strftime('%Y-%m-%d'),
    'source': SRC.split('/')[-1],
    'itemRows': int(len(df)),
    'reqs': int(len(rows)),
    'byBucket': byBucket,
    'subtotal': round(float(df[SUB].sum()), 2),
    'marginItems': int(df[MARGIN].notna().sum()),
    'marginTotal': round(float(df[MARGIN].sum()), 2),
    'negativeItems': int((df[SUB] < 0).sum()),
    'zeroItems': int((df[SUB] == 0).sum()),
    'buyers': int(df[BUYER].nunique()),
    'byParent': byParent,
    'rows': rows,
}

json.dump(out, open(OUT, 'w'), separators=(',', ':'))

print('item rows      :', out['itemRows'])
print('requisitions   :', out['reqs'])
print('buckets        :', byBucket)
print('subtotal       : $%s' % f"{out['subtotal']:,.0f}")
print('margin on      : %d of %d items' % (out['marginItems'], out['itemRows']))
print('health systems : %d (%d matched to master)' %
      (len(byParent), sum(1 for e in byParent.values() if e['matched'])))
import os
print('file size      : %.0f KB' % (os.path.getsize(OUT) / 1024))
