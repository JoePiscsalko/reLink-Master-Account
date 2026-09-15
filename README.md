# reLink360 Account Master

Internal audit view of the reLink360 book: every 360 and transactional account under a
health-system parent, with escrow by GL line, coverage roles, 2026 budget, open third-party
stock and contract status.

**Confidential — internal use only.**

## What's here

| File | Purpose |
|---|---|
| `index.html` | Interactive dashboard (health systems, coverage & roles, open TPS, contract gap, method) |
| `report.html` | Printable report — same data, paginated, exports to PDF from the browser |
| `data/*.json` | Pre-joined datasets the pages fetch at load |
| `support.js`, `doc-page.js` | Runtime and paged-document component |

Static site. No build step, no server, no dependencies.

## Run locally

Must be served over HTTP — the pages `fetch()` the JSON, so opening `index.html`
straight from the filesystem will fail:

```bash
python3 -m http.server 8080
# open http://localhost:8080
```

## Deploy to Netlify

**Drag and drop** — unzip, then drop the folder's *contents* on the Netlify dashboard.

**From GitHub** — push this folder to a repo, then in Netlify: Add new site →
Import an existing project → pick the repo. Settings come from `netlify.toml`:

- Build command: *(none)*
- Publish directory: `.`

If this folder sits inside a larger repo, set **Base directory** to that subfolder.

## Data refresh

The pages read only `data/*.json`. To update the numbers, replace those four files and
redeploy — no code changes. They are generated from six Salesforce exports:

| Source export | Feeds |
|---|---|
| Parent Child Escrow Report V2 | GL budget by line, parent–child hierarchy |
| Accounts with Parent Account | Account status, acquisition & sell-to coordinators, consignment % |
| All Contacts with Roles Assigned | Authorized redeemer, 360 disposition champion |
| Master Tracker with Budgets 2026 | 2026 annual budget by health system |
| Daily OPEN TPS YTD | Open third-party stock pipeline |
| No Active Contract | Contract-gap flag |

## Known data gaps

- **Open TPS** is account-linked for the 360 Current slice only (39 of 87 open records).
  The other exports carry `Queue TPS Seller Account Status` but not `Seller Account`,
  so those records can't be attributed to a child account yet.
- **Budgets** are tracker figures, not a Salesforce field; 14 net-new prospects have no
  Salesforce account and don't roll up.
- **Escrow** is filtered to `reLink 360 Partner = True`, so transactional accounts appear
  in the hierarchy with no escrow line.

See the **Method & gaps** tab in the dashboard for the full reconciliation.

---
reLink Medical®, reLink360®, and reLink Ready® are registered trademarks of reLink Medical LLC.

## Open REQ tab

Added from the Salesforce Requisition export. `data/reqs.json` is built by
`build_reqs.py`:

    python3 build_reqs.py /path/to/req-export.csv

Notes on the source export:
- It is **cp1252**, not UTF-8. A plain `read_csv` fails on a degree symbol.
- Grain is Requisition Item; the script rolls it to Requisition.
- `Account Name` and `Parent Account: Account Name` both describe the
  **purchaser**. Nothing in this export links a Req to the 360 partner that
  supplied the equipment, so Reqs do not roll up to the seller-side account book.
- `rL Sales Team Estimated Margin` is populated on ~5% of line items.
- There is no Status or date column, so "open" cannot be computed — the tab
  shows whatever the saved Salesforce report returns.
