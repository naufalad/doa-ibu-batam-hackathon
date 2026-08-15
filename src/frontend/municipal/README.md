# Municipal frontend — TPA capacity dashboard

A single self-contained page (`index.html`, no build step, no dependencies)
for city/`authorized`-level staff monitoring landfill intake across Batam's
12 kecamatan. Open it directly in a browser, or serve the folder statically:

```bash
cd src/frontend/municipal
python3 -m http.server 8901
# open http://localhost:8901/index.html
```

By default it talks to the backend at `http://localhost:8000/api/v1`
(override in the ⚙️ settings modal, or edit `DEFAULT_CONFIG.apiBase` in
`index.html`). Log in with an `authorized` or `waste_bank` account (e.g. a
seeded account from `scripts/seed_db.py`) — `waste_bank` accounts only see
their assigned region(s), the rest render as "di luar cakupan akun ini".
No backend running / not logged in still renders the page against
generated demo data, clearly banner'd as such, so the layout can be
reviewed standalone.

## What's live vs. manual

- **Live**, aggregated in-browser from `GET /waste/history` +
  `GET /regions`: the per-kecamatan load/status grid, "Sampah Masuk Hari
  Ini", and the peak-arrival-hour readout. `/waste/history` returns
  `num_objects` per submission, not weight, so tonnage figures use a
  configurable kg-per-object estimate (⚙️ settings) — the per-kecamatan
  *load %* itself doesn't depend on that estimate, only the displayed
  kg/Ton rate does.
- **Manual (ops-configured)**: "Total Kapasitas TPA" and "Estimasi Sisa
  Umur TPA". Nothing in `app/db.py` models actual landfill capacity/fill
  yet, so these stay editable inputs in ⚙️ settings until a real capacity
  data source exists on the backend.

## Design

Follows the `dataviz` skill: status meters (Aman/Waspada/Kritis) always
pair color with a text label, chrome tokens support light/dark, and mass
figures use adaptive units (kg vs. Ton) rather than a fixed unit that
reads as "0.0" for small/demo datasets.
