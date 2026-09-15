#!/usr/bin/env python3
"""Build data/focus.json from the four focus-account Word lists.

Each .docx is a flat list of health system names with the focus label
concatenated onto the end of the name ("SSM Health CareReady"), so the
suffix is stripped before matching.

Names resolve to either a parent (health system) or a child account in
master.json — several focus entries are child accounts, e.g. "(TH) Central
Region" sits under Trinity Health, and "(GEHC) Corporate" under GE HealthCare.
"""
import json, re, sys, unicodedata, zipfile

FILES = {
    'strategic':     ('Document1.docx',   'Strategic',     '#036E78'),
    'ready':         ('Document1_3.docx', 'Ready',         '#6E8A36'),
    'transactional': ('Document1_2.docx', 'Transactional', '#8B7F78'),
    'netnew':        ('Document1_4.docx', 'Net new',       '#D46A1E'),
}
UPLOADS = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads'
MASTER  = 'app/data/master.json'
OUT     = 'app/data/focus.json'

SUFFIX = re.compile(r'(Net New|Ready|Transaction)\s*$')

# Names in the Word lists that don't match master.json verbatim. Left-hand side
# is the list spelling, right-hand side the account-master spelling.
ALIAS = {
    'Detroit Medical Center Health':  'Detroit Medical Center',
    'Henry Ford Health System':       'Henry Ford Health',
    'University of Michigan':         'University of Michigan Health',
    'Baptist Health - Arkansas':      'Baptist Health - AR',
    'Huntsville Health System':       'Huntsville Hospital Health System',
    'Jackson Health System FL':       'Jackson Health System (FL)',
    'Vanderbilt Health Network':      'Vanderbilt Health',
    'University of Miami Hospital':   'University of Miami Health System',
    'Broward Health System':          'Broward Health',
    'UNC Health Care System (UNC)':   'UNC Health',
    'Geisinger Health System':        'Geisinger Health - Part of Risant Health',
    # these resolve to child accounts, not parents
    '(GEHC) Corporate':                  '(GEHC) Corporate',
    '(GEHC) ROC':                        '(GEHC) ROC',
    '(TH) Central Region':               '(TH) Central Region',
    '(TH) Eastern Region':               '(TH) Eastern Region',
    'Atrium Health Navicent - GA':       'Atrium Health Navicent - GA',
    'SHBal Sinai Hospital of Baltimore': 'SHBal Sinai Hospital of Baltimore',
    'NEA Baptist Memorial Hospital':     'NEA Baptist Memorial Hospital',
    'Hackensack Meridian Health':        'Hackensack Meridian Health',
    'Mount Sinai Health System':         'Mount Sinai Health System',
}


def norm(s):
    s = unicodedata.normalize('NFKD', s).replace('\u2019', "'")
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s.lower())
    s = re.sub(r'\b(inc|llc|corp|corporation|the)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def lines(fn):
    xml = zipfile.ZipFile(f'{UPLOADS}/{fn}').read('word/document.xml').decode('utf8')
    out = []
    for p in re.findall(r'<w:p [^>]*>(.*?)</w:p>', xml, re.S):
        t = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S))
        t = t.replace('&amp;', '&').replace('&#8217;', '\u2019').strip()
        if t:
            out.append(t)
    return out


master = json.load(open(MASTER))
parent_by_norm, kid_parent, kid_by_norm = {}, {}, {}
for s in master['systems']:
    parent_by_norm.setdefault(norm(s['parent']), s['parent'])
    for k in s['kids']:
        name = k['name'].split(' | ')[0].strip()
        kid_parent.setdefault(name, s['parent'])
        kid_by_norm.setdefault(norm(name), name)

byParent, byAccount, unmatched, counts = {}, {}, [], {}

for key, (fn, label, color) in FILES.items():
    raw = lines(fn)[1:]                       # first line is the list heading
    seen, n = set(), 0
    for entry in raw:
        name = SUFFIX.sub('', entry).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        target = ALIAS.get(name, name)

        parent = parent_by_norm.get(norm(target))
        if parent:
            tags = byParent.setdefault(parent, [])
            if key not in tags:
                tags.append(key)
            n += 1
            continue

        kid = kid_by_norm.get(norm(target))
        if kid:
            byAccount.setdefault(kid, []).append(key)
            # so the parent row surfaces the badge too
            byParent.setdefault(kid_parent[kid], [])
            if key not in byParent[kid_parent[kid]]:
                byParent[kid_parent[kid]].append(key)
            n += 1
            continue

        unmatched.append({'list': key, 'name': name})
    counts[key] = n

out = {
    'generated': __import__('datetime').date.today().isoformat(),
    'lists': {k: {'label': v[1], 'color': v[2]} for k, v in FILES.items()},
    'order': ['strategic', 'ready', 'transactional', 'netnew'],
    'counts': counts,
    'byParent': byParent,
    'byAccount': byAccount,
    'unmatched': unmatched,
}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))

for k in out['order']:
    print(f'  {FILES[k][1]:14s} {counts[k]:3d} matched')
print(f'\nflagged health systems : {len(byParent)}')
print(f'flagged child accounts : {len(byAccount)}')
print(f'unmatched              : {len(unmatched)}')
for u in unmatched:
    print(f'   [{u["list"]}] {u["name"]}')
