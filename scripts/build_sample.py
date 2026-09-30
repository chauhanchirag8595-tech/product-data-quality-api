"""Stream the source archive and create a reproducible 5,000-row sample."""
from __future__ import annotations

import csv
import json
import gzip
import random
import sys
import zipfile
from pathlib import Path

SOURCE = Path.home() / "Downloads" / "archive.zip"
OUT = Path(__file__).resolve().parents[1] / "data" / "sample.jsonl.gz"
SAMPLE_SIZE = 5_000
SEED = 42


def main() -> None:
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    rng = random.Random(SEED)
    reservoir: list[dict[str, str]] = []
    seen = 0
    with zipfile.ZipFile(SOURCE) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith((".tsv", ".txt"))]
        if not members:
            raise RuntimeError("No TSV/TXT dataset found in archive")
        with archive.open(members[0]) as raw:
            import io
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""), delimiter="\t")
            for row in reader:
                seen += 1
                clean = {str(k): (v or "").strip() for k, v in row.items() if k is not None}
                if len(reservoir) < SAMPLE_SIZE:
                    reservoir.append(clean)
                else:
                    pos = rng.randrange(seen)
                    if pos < SAMPLE_SIZE:
                        reservoir[pos] = clean
    if seen < SAMPLE_SIZE:
        raise RuntimeError(f"Source has only {seen} rows")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8", newline="") as f:
        for row in reservoir:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"rows_seen": seen, "sample_rows": len(reservoir), "seed": SEED, "source_member": members[0], "output": str(OUT)}))


if __name__ == "__main__":
    main()
