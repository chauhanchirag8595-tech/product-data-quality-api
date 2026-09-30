from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .data import connect, load_sample, quote

app = FastAPI(title="Product Data Quality API", version="1.0.0", description="A 5,000-product Open Food Facts sample with barcode validation and completeness scores.")


@app.on_event("startup")
def initialize() -> None:
    db = connect()
    try:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'").fetchone()
    finally:
        db.close()
    if not exists:
        load_sample()


def product_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


@app.get("/products/{barcode}")
def get_product(barcode: str) -> dict[str, Any]:
    with connect() as db:
        cols = {row[1] for row in db.execute("PRAGMA table_info(products)")}
        key = next((name for name in ("code", "barcode", "_id") if name in cols), None)
        if key is None:
            raise HTTPException(status_code=500, detail="No barcode field is available in the dataset")
        row = db.execute(f"SELECT * FROM products WHERE {quote(key)}=? LIMIT 1", (barcode,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found in the 5,000-row sample")
    return product_dict(row)


@app.get("/products")
def list_products(brand: str | None = None, min_score: int = Query(0, ge=0, le=100), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    clauses, args = ["completeness_score >= ?"], [min_score]
    if brand:
        clauses.append('"brands" LIKE ?')
        args.append(f"%{brand}%")
    where = " AND ".join(clauses)
    with connect() as db:
        total = db.execute(f"SELECT COUNT(*) FROM products WHERE {where}", args).fetchone()[0]
        rows = db.execute(f"SELECT * FROM products WHERE {where} ORDER BY completeness_score DESC LIMIT ? OFFSET ?", args + [page_size, (page - 1) * page_size]).fetchall()
    return {"page": page, "page_size": page_size, "total": total, "items": [product_dict(row) for row in rows]}


@app.get("/stats")
def stats() -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT COUNT(*) AS total_products, ROUND(AVG(completeness_score), 2) AS average_score, SUM(CASE WHEN barcode_valid=0 THEN 1 ELSE 0 END) AS invalid_barcode_count FROM products").fetchone()
    return dict(row)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    return Path(__file__).with_name("index.html").read_text(encoding="utf-8")
