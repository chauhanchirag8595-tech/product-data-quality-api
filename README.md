# Product Data API & Quality Audit

An intern-assignment implementation using a reproducible 5,000-row Open Food Facts sample (reservoir sampling, seed 42), SQLite, FastAPI and a small HTML UI. The checked-in compressed sample makes local startup and free-host deployment reproducible. Open Food Facts database contents are available under ODbL; attribution and share-alike obligations apply to derived databases. See [Open Food Facts API license guidance](https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/) and [terms of use](https://world.openfoodfacts.org/terms-of-use). The code license in `LICENSE` does not replace the data license.

## Run locally

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.data
python scripts/analyze.py
python scripts/compare_live.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the UI and `/docs` for interactive Swagger/OpenAPI. The API serves `GET /products/{barcode}`, `GET /products?brand=&min_score=&page=&page_size=`, and `GET /stats`. The database path can be changed with `DATABASE_PATH`; the source sample path with `SAMPLE_PATH`.

To rebuild the exact sample from the source archive, place `archive.zip` in your Downloads folder and run:

```powershell
python scripts/build_sample.py
python -m app.data
```

The builder streams the TSV inside the ZIP and keeps a uniform reservoir of exactly 5,000 rows using seed 42. The included snapshot was generated from 356,027 source rows. Original source column names are retained in SQLite; two calculated columns, `barcode_valid` and `completeness_score`, are appended.

## Analysis and deliverables

- `reports/dashboard.html` — one-page analysis dashboard
- `reports/memo.pdf` — one-page findings memo and issue summary
- `reports/issue-report.md` — reproducible issue report
- `reports/issue-screenshot.svg` — query evidence image
- `reports/analysis.json` — machine-readable analysis numbers
- `data/live_comparison.json` — 20-record snapshot/live results after running the comparison script

The live comparison chooses a seeded set of valid sample barcodes and sends a custom User-Agent. 404, 429, timeout and other request errors are saved as statuses instead of terminating the run. A successful product response is scored with the same eight fields and scoring rule as the snapshot. Network access is required for this step.

## AI disclosure

OpenAI Codex was used to draft the API, data cleaning/analysis scripts, UI and report. I reviewed the GS1 Mod-10 logic and the assignment's field/score definitions, generated the sample locally, and inspected computed outputs. One AI-generated first version assumed every TSV cell fit Python's default CSV field-size limit. The real source hit that limit; I reproduced the exception while building the sample and fixed it by raising `csv.field_size_limit` before reading the archive.

## Known limitations

- The current data is one random snapshot; Open Food Facts changes continuously.
- Category/brand text is not normalized, so spelling variants count separately.
- The duplicate metric counts repeated barcode groups, not excess duplicate rows.
- The live check is only 20 valid sample codes; timeouts/rate limits/non-matches reduce the usable comparison set.
- Render's free service can sleep and its filesystem may be ephemeral; SQLite data should be reloaded from the bundled sample after restart.
- The User-Agent uses a generic assignment contact by default. Replace it with your preferred contact before sending live requests if required by your course policy.

## Deploy (free Render web service)

1. Push this folder as the root of a public GitHub repository.
2. In Render, create a free **Web Service** from that repository. Build command: `pip install -r requirements.txt`; start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Or use the included `render.yaml` Blueprint. Render gives a URL with the UI at `/` and API docs at `/docs`.
4. Run the live comparison locally and commit `data/live_comparison.json` and refreshed report outputs if your course requires the comparison results in the submitted repo.

No deployment has been performed from this workspace; add the assigned GitHub remote and deploy through your own account.
