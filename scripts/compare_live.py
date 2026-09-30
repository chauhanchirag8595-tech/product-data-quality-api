"""Compare 20 random sample records to the current Open Food Facts API."""
from __future__ import annotations

import json
import gzip
import random
import sys
import time
from pathlib import Path
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data import SCORE_FIELDS, gs1_mod10_valid, score_product

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample.jsonl.gz"
OUT = ROOT / "data" / "live_comparison.json"


def main() -> None:
    with gzip.open(SAMPLE, "rt", encoding="utf-8") as f:
        rows = [json.loads(x) for x in f if x.strip()]
    key = "code" if "code" in rows[0] else "barcode"
    candidates = [r for r in rows if gs1_mod10_valid(r.get(key))]
    sample = random.Random(42).sample(candidates, min(20, len(candidates)))
    results = []
    for row in sample:
        barcode = row.get(key, "")
        try:
            req = urllib.request.Request(f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json", headers={"User-Agent": "ProductDataQualityInternAssignment/1.0 (educational contact: student@example.com)"})
            with urllib.request.urlopen(req, timeout=12) as response:
                body = json.loads(response.read().decode("utf-8"))
                product = body.get("product") or {}
                live = {f: product.get(f, "") for f in SCORE_FIELDS}
                results.append({"barcode": barcode, "status": "ok" if product else "not_found", "snapshot_score": score_product(row), "live_score": score_product(live) if product else None})
        except urllib.error.HTTPError as exc:
            status = "rate_limited" if exc.code == 429 else "not_found" if exc.code == 404 else "error"
            results.append({"barcode": barcode, "status": status, "http_status": exc.code, "snapshot_score": score_product(row), "live_score": None})
        except TimeoutError:
            results.append({"barcode": barcode, "status": "timeout", "snapshot_score": score_product(row), "live_score": None})
        except urllib.error.URLError as exc:
            status = "timeout" if isinstance(exc.reason, TimeoutError) else "error"
            results.append({"barcode": barcode, "status": status, "error": str(exc)[:180], "snapshot_score": score_product(row), "live_score": None})
        time.sleep(1.1)
    OUT.write_text(json.dumps({"sample_size": len(results), "results": results}, indent=2), encoding="utf-8")
    print(f"Saved {len(results)} comparisons to {OUT}")


if __name__ == "__main__":
    main()
