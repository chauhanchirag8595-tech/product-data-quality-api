"""Create reproducible analysis, a one-page dashboard, memo and issue evidence."""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "products.sqlite"
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    columns = {r[1] for r in db.execute("PRAGMA table_info(products)")}
    barcode_col = next(c for c in ("code", "barcode", "_id") if c in columns)
    n = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    duplicate_barcodes = db.execute(f'SELECT COUNT(*) FROM (SELECT "{barcode_col}" FROM products GROUP BY "{barcode_col}" HAVING COUNT(*)>1)').fetchone()[0]
    invalid = db.execute("SELECT COUNT(*) FROM products WHERE barcode_valid=0").fetchone()[0]
    avg_score = db.execute("SELECT AVG(completeness_score) FROM products").fetchone()[0] or 0
    ge75 = db.execute("SELECT COUNT(*) FROM products WHERE completeness_score>=75").fetchone()[0]
    score_counts = {str(r[0]): r[1] for r in db.execute("SELECT completeness_score, COUNT(*) FROM products GROUP BY completeness_score ORDER BY completeness_score")}
    blank_counts = {}
    for field in ("product_name", "brands", "quantity", "categories_en", "ingredients_text", "nutrition_grade_fr", "allergens", "image_url"):
        blank_counts[field] = db.execute(f'SELECT COUNT(*) FROM products WHERE "{field}" IS NULL OR TRIM("{field}")=""').fetchone()[0]
    top_brands = [(r[0] or "(blank)", r[1]) for r in db.execute('SELECT brands,COUNT(*) n FROM products WHERE TRIM(brands)!="" GROUP BY brands ORDER BY n DESC LIMIT 5')]
    top_categories = [(r[0] or "(blank)", r[1]) for r in db.execute('SELECT categories_en,COUNT(*) n FROM products WHERE TRIM(categories_en)!="" GROUP BY categories_en ORDER BY n DESC LIMIT 5')]
    group_missing = {}
    for label, entries, column in (("brands", top_brands, "brands"), ("categories", top_categories, "categories_en")):
        group_missing[label] = {}
        for name, count in entries:
            if name == "(blank)":
                continue
            # Top missing field per group makes the data action-oriented.
            sums = {}
            for f in blank_counts:
                sums[f] = db.execute(f'SELECT COUNT(*) FROM products WHERE "{column}"=? AND ("{f}" IS NULL OR TRIM("{f}")="")', (name,)).fetchone()[0]
            group_missing[label][name] = {"rows": count, "most_missing_field": max(sums, key=sums.get), "missing_counts": sums}
    live_path = ROOT / "data" / "live_comparison.json"
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else {"sample_size": 0, "results": []}
    matched = [x for x in live["results"] if x.get("status") == "ok" and x.get("live_score") is not None]
    improved = sum(x["live_score"] > x["snapshot_score"] for x in matched)
    declined = sum(x["live_score"] < x["snapshot_score"] for x in matched)
    tied = sum(x["live_score"] == x["snapshot_score"] for x in matched)
    stats = {"n": n, "duplicate_barcode_groups": duplicate_barcodes, "invalid_barcodes": invalid, "average_score": round(avg_score, 2), "ge75_count": ge75, "ge75_pct": round(100*ge75/n, 2), "score_counts": score_counts, "blank_counts": blank_counts, "top_brands": top_brands, "top_categories": top_categories, "group_missing": group_missing, "live": {"requested": live.get("sample_size", 0), "matched": len(matched), "improved": improved, "declined": declined, "unchanged": tied, "results": live.get("results", [])}}
    (OUT / "analysis.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    create_dashboard(stats)
    create_memo(stats)
    create_issue(stats)
    db.close()
    print(json.dumps({k: stats[k] for k in ("n", "duplicate_barcode_groups", "invalid_barcodes", "average_score", "ge75_pct", "blank_counts")}))


def create_dashboard(s: dict) -> None:
    max_count = max(s["score_counts"].values()) or 1
    bars = "".join(f'<div class="barrow"><span>{score}%</span><div class="bar" style="width:{count/max_count*100:.1f}%"></div><b>{count}</b></div>' for score, count in sorted(s["score_counts"].items(), key=lambda x:int(x[0])))
    fields = "".join(f'<tr><td>{field}</td><td>{count:,}</td><td>{count/s["n"]*100:.1f}%</td></tr>' for field,count in sorted(s["blank_counts"].items(), key=lambda x:-x[1]))
    brands = "".join(f'<li>{name}: {v["most_missing_field"]} missing most ({max(v["missing_counts"].values()):,}/{v["rows"]:,})</li>' for name,v in s["group_missing"]["brands"].items())
    cats = "".join(f'<li>{name}: {v["most_missing_field"]} missing most ({max(v["missing_counts"].values()):,}/{v["rows"]:,})</li>' for name,v in s["group_missing"]["categories"].items())
    l=s["live"]
    live=f'{l["improved"]} improved · {l["declined"]} declined · {l["unchanged"]} unchanged from {l["matched"]} successful live matches (of {l["requested"]} attempted).'
    html=f'''<!doctype html><html><head><meta charset="utf-8"><title>Product data quality dashboard</title><style>body{{font:14px Arial;background:#f3f6fa;color:#1a2a3a;margin:24px}}h1{{font-size:26px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}section{{background:white;padding:18px;border-radius:12px;box-shadow:0 2px 10px #152c4410}}.wide{{grid-column:span 2}}.kpi{{font-size:28px;font-weight:bold;color:#146b55}}table{{width:100%;border-collapse:collapse}}td,th{{padding:7px;border-bottom:1px solid #e5eaf0;text-align:left}}.barrow{{display:flex;gap:8px;align-items:center;margin:6px 0}}.barrow span{{width:42px}}.bar{{height:14px;background:#278a70;border-radius:4px;min-width:2px}}.barrow b{{font-size:12px}}small{{color:#667}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}</style></head><body><h1>Open Food Facts · Product quality audit</h1><p>Seed 42 random sample · {s['n']:,} records · completeness = filled share of 8 fields</p><div class="grid"><section><small>Mean score</small><div class="kpi">{s['average_score']}%</div></section><section><small>Score ≥ 75</small><div class="kpi">{s['ge75_pct']}%</div><div>{s['ge75_count']:,} products</div></section><section><small>Invalid barcodes</small><div class="kpi">{s['invalid_barcodes']:,}</div></section><section class="wide"><h2>Completeness score spread</h2>{bars}</section><section><h2>Duplicate barcode groups</h2><div class="kpi">{s['duplicate_barcode_groups']:,}</div></section><section><h2>Missing values</h2><table><tr><th>Field</th><th>Blank</th><th>Share</th></tr>{fields}</table></section><section><h2>Top brands · most missing field</h2><ul>{brands}</ul></section><section><h2>Top categories · most missing field</h2><ul>{cats}</ul></section><section class="wide"><h2>Snapshot vs live API</h2><p>{live}</p><small>Small sample, survivor and network-response bias apply; see memo.</small></section></div></body></html>'''
    (OUT/"dashboard.html").write_text(html, encoding="utf-8")


def create_memo(s: dict) -> None:
    styles=getSampleStyleSheet(); story=[Paragraph("Product Data API · One-page findings memo",styles["Title"]),Paragraph("Open Food Facts snapshot · random sample of 5,000 records · seed 42",styles["Normal"]),Spacer(1,10)]
    most=max(s["blank_counts"],key=s["blank_counts"].get); pct=100*s["blank_counts"][most]/s["n"]
    l=s["live"]
    findings=[f"<b>1. Barcode integrity:</b> {s['invalid_barcodes']:,} of {s['n']:,} sampled records ({100*s['invalid_barcodes']/s['n']:.1f}%) fail the GS1 Mod-10 check-digit rule; {s['duplicate_barcode_groups']:,} barcode groups contain duplicates.",f"<b>2. Content completeness:</b> average score is {s['average_score']}%; {s['ge75_count']:,} products ({s['ge75_pct']}%) score at least 75. <i>{most}</i> is most often blank ({s['blank_counts'][most]:,}; {pct:.1f}%).",f"<b>3. Snapshot vs live:</b> {l['improved']} of {l['matched']} successful comparisons improved, {l['declined']} declined and {l['unchanged']} were unchanged (from {l['requested']} attempted). This small, valid-barcode sample is directional only; nonresponse and matching/selection bias limit inference."]
    for f in findings: story += [Paragraph(f,styles["BodyText"]),Spacer(1,7)]
    story += [Paragraph("Recommendation",styles["Heading2"]),Paragraph(f"Prioritize fixing {most} capture and reject invalid GTIN check digits at ingestion, with a correction queue for the {s['invalid_barcodes']:,} affected sample rows. Recheck completeness after remediation.",styles["BodyText"]),Paragraph("What would increase confidence",styles["Heading2"]),Paragraph("Repeat the comparison on a larger stratified sample across brands, categories and score bands; retry 404/429/timeouts on a controlled schedule, record timestamps, and compare multiple snapshots over time.",styles["BodyText"]),Spacer(1,6),Paragraph("Issue report · invalid GS1 check digits",styles["Heading2"]),Paragraph(f"Evidence: SELECT COUNT(*) FROM products WHERE barcode_valid=0; result = {s['invalid_barcodes']:,}/{s['n']:,}. Expected: invalid barcodes are flagged and excluded from reliable joins. Actual: these records can fail lookup or be incorrectly linked. Impact: {s['invalid_barcodes']:,} sample records. 90-day cost assumption: 2 minutes of manual triage per affected row once = {s['invalid_barcodes']*2/60:.1f} staff hours; errors may also mislead shoppers and catalog teams. Screenshot: issue-screenshot.svg in reports/.",styles["BodyText"]) ]
    doc=SimpleDocTemplate(str(OUT/"memo.pdf"),pagesize=letter,rightMargin=40,leftMargin=40,topMargin=35,bottomMargin=35)
    doc.build(story)


def create_issue(s: dict) -> None:
    text=f'''# Issue report: {s['invalid_barcodes']:,} sampled product barcodes fail GS1 Mod-10\n\n**Steps / evidence**\n\nRun `python scripts/analyze.py` after loading the database. Query: `SELECT COUNT(*) FROM products WHERE barcode_valid = 0;` Result: **{s['invalid_barcodes']:,} of {s['n']:,}** sampled records. The validator in `app/data.py` applies the GS1 Mod-10 check digit to 8, 12, 13 and 14 digit GTINs.\n\n**Expected vs actual**\n\nExpected: every barcode is validated and invalid values are clearly flagged before external lookup or record matching. Actual: this sample contains the above invalid values; live lookups cannot reliably match them and downstream joins may fail or misattribute product data.\n\n**Screenshot**\n\n![Invalid barcode query evidence](issue-screenshot.svg)\n\n**Impact**\n\n{ s['invalid_barcodes']:,} sample records. Cost assumption if left for 90 days: one manual review of 2 minutes per invalid record costs {s['invalid_barcodes']*2/60:.1f} staff hours; unresolved joins also risk bad product details for catalog teams and shoppers. This is an estimate, not measured operational loss.\n'''
    (OUT/"issue-report.md").write_text(text,encoding="utf-8")
    (OUT/"issue-screenshot.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="420"><rect width="960" height="420" fill="#f3f6fa"/><rect x="45" y="38" width="870" height="344" rx="18" fill="white" stroke="#dce4ec"/><text x="80" y="100" font-family="Arial" font-size="28" fill="#1a2a3a">SQL evidence · invalid GTIN check digits</text><rect x="80" y="135" width="800" height="95" rx="8" fill="#172331"/><text x="105" y="193" font-family="Consolas,monospace" font-size="20" fill="#bce7d9">SELECT COUNT(*) FROM products WHERE barcode_valid = 0;</text><text x="80" y="286" font-family="Arial" font-size="18" fill="#667789">Sample rows</text><text x="80" y="335" font-family="Arial" font-size="34" font-weight="bold" fill="#176b57">{s['n']:,}</text><text x="390" y="286" font-family="Arial" font-size="18" fill="#667789">Invalid GS1 check digits</text><text x="390" y="335" font-family="Arial" font-size="34" font-weight="bold" fill="#b24a3a">{s['invalid_barcodes']:,} ({100*s['invalid_barcodes']/s['n']:.1f}%)</text></svg>''',encoding="utf-8")


if __name__ == "__main__":
    main()
