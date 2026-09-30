"""SQLite loading, completeness scoring and GS1 Mod-10 validation."""
from __future__ import annotations

import json
import gzip
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("DATABASE_PATH", Path(__file__).resolve().parents[1] / "data" / "products.sqlite"))
SAMPLE_PATH = Path(os.getenv("SAMPLE_PATH", Path(__file__).resolve().parents[1] / "data" / "sample.jsonl.gz"))
SCORE_FIELDS = ("product_name", "brands", "quantity", "categories_en", "ingredients_text", "nutrition_grade_fr", "allergens", "image_url")


def gs1_mod10_valid(value: Any) -> bool:
    """Validate 8, 12, 13 or 14 digit GS1 GTINs using their check digit."""
    digits = str(value or "").strip()
    if not re.fullmatch(r"[0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14}", digits):
        return False
    payload, check = digits[:-1], int(digits[-1])
    weighted_sum = sum(int(d) * (3 if (len(payload) - i) % 2 else 1) for i, d in enumerate(payload))
    return (10 - weighted_sum % 10) % 10 == check


def score_product(row: dict[str, Any]) -> int:
    filled = sum(bool(str(row.get(field, "") or "").strip()) for field in SCORE_FIELDS)
    return round(100 * filled / len(SCORE_FIELDS))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def load_sample(path: Path = SAMPLE_PATH) -> int:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        rows = [json.loads(line) for line in source if line.strip()]
    if not rows:
        raise RuntimeError(f"No records found in {path}")
    columns = list(rows[0])
    barcode_col = "code" if "code" in columns else "barcode" if "barcode" in columns else "_id" if "_id" in columns else None
    if barcode_col is None:
        raise RuntimeError("Source has no code/barcode/_id field")
    with connect() as db:
        db.execute("DROP TABLE IF EXISTS products")
        definitions = ", ".join(f"{quote(c)} TEXT" for c in columns)
        db.execute(f"CREATE TABLE products ({definitions}, barcode_valid INTEGER NOT NULL, completeness_score INTEGER NOT NULL)")
        names = columns + ["barcode_valid", "completeness_score"]
        insert_sql = f"INSERT INTO products ({', '.join(quote(c) for c in names)}) VALUES ({', '.join('?' for _ in names)})"
        payload = []
        for row in rows:
            barcode = row.get(barcode_col, "")
            payload.append([row.get(c, "") for c in columns] + [int(gs1_mod10_valid(barcode)), score_product(row)])
        db.executemany(insert_sql, payload)
        db.execute("CREATE INDEX idx_products_score ON products(completeness_score)")
        db.execute(f"CREATE INDEX idx_products_barcode ON products({quote(barcode_col)})")
    return len(rows)


def main() -> None:
    count = load_sample()
    print(f"Loaded {count} rows into {DB_PATH}")


if __name__ == "__main__":
    main()
