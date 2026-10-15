"""Build NutriLens's food database (data/foods.db) from the USDA FoodData Central full CSV download.

    python scripts/build_food_db.py data/raw/usda/FoodData_Central_csv_2026-04-30.zip

The zip is read in place (nothing is extracted). The result is a SQLite database with:
  foods      one row per food: description, type, category, brand, ingredients, 16 nutrients per 100 g
  portions   USDA household portions ("1 slice" = 28 g) for generic foods
  foods_fts  a full-text index used for retrieval (the "R" in RAG)
"""

from __future__ import annotations

import csv
import io
import math
import sqlite3
import sys
import time
import zipfile
from array import array
from pathlib import Path

csv.field_size_limit(10_000_000)

KEEP_TYPES = {"foundation_food", "sr_legacy_food", "survey_fndds_food", "branded_food"}

# App nutrient key -> USDA nutrient ids in order of preference.
NUTRIENTS = {
    "calories": [1008, 2047, 2048],
    "protein_g": [1003],
    "carbs_g": [1005, 1050],
    "fat_g": [1004, 1085],
    "fiber_g": [1079],
    "sugar_g": [2000, 1063],
    "sodium_mg": [1093],
    "iron_mg": [1089],
    "calcium_mg": [1087],
    "vitamin_c_mg": [1162],
    "vitamin_d_mcg": [1114],
    "vitamin_b12_mcg": [1178],
    "potassium_mg": [1092],
    "magnesium_mg": [1090],
    "zinc_mg": [1095],
    "folate_mcg": [1177, 1190],
}
KEYS = list(NUTRIENTS)
# USDA nutrient id -> (column index, preference rank)
ID_TO_SLOT = {nid: (i, rank) for i, ids in enumerate(NUTRIENTS.values()) for rank, nid in enumerate(ids)}
VITAMIN_D_IU = 1110  # converted to mcg (1 mcg = 40 IU) when the mcg value is missing

SCHEMA = f"""
CREATE TABLE foods (
    fdc_id INTEGER PRIMARY KEY,
    data_type TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    brand TEXT,
    gtin TEXT,
    ingredients TEXT,
    {", ".join(f"{k} REAL" for k in KEYS)}
);
CREATE TABLE portions (
    fdc_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    grams REAL NOT NULL
);
CREATE INDEX portions_fdc ON portions(fdc_id);
CREATE INDEX foods_gtin ON foods(gtin);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def open_csv(z: zipfile.ZipFile, name: str):
    member = next((n for n in z.namelist() if n.endswith("/" + name) or n == name), None)
    if member is None:
        return None
    return csv.DictReader(io.TextIOWrapper(z.open(member), encoding="utf-8", newline=""))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def add_generic_index(db: sqlite3.Connection) -> None:
    """A small, fast index over generic foods and dishes only (what appears on plates), searched first."""
    log("Building the generic-foods search index…")
    db.executescript("""
        DROP TABLE IF EXISTS generic_fts;
        CREATE VIRTUAL TABLE generic_fts USING fts5(description, category, tokenize='porter unicode61');
        INSERT INTO generic_fts(rowid, description, category)
            SELECT fdc_id, description, category FROM foods WHERE data_type != 'branded_food';
        INSERT INTO generic_fts(generic_fts) VALUES ('optimize');
    """)


def main(zip_path: str, out_path: str) -> None:
    z = zipfile.ZipFile(zip_path)

    log("Reading categories…")
    categories = {}
    for name, id_col, text_col in (("food_category.csv", "id", "description"),
                                   ("wweia_food_category.csv", "wweia_food_category", "wweia_food_category_description")):
        rows = open_csv(z, name)
        if rows:
            for r in rows:
                categories[r[id_col]] = r[text_col]

    log("Reading foods…")
    foods: dict[int, list] = {}
    for r in open_csv(z, "food.csv"):
        if r["data_type"] in KEEP_TYPES:
            foods[int(r["fdc_id"])] = [r["data_type"], r["description"].strip(), categories.get(r["food_category_id"])]
    log(f"  {len(foods):,} foods kept")

    log("Reading branded product details…")
    branded = {}
    rows = open_csv(z, "branded_food.csv")
    for r in rows or []:
        fid = int(r["fdc_id"])
        if fid in foods:
            brand = (r.get("brand_name") or r.get("brand_owner") or "").strip()
            branded[fid] = (brand, (r.get("gtin_upc") or "").strip(), (r.get("ingredients") or "").strip(),
                            (r.get("branded_food_category") or "").strip())
    log(f"  {len(branded):,} branded products")

    log("Reading nutrients (the big file, a few minutes)…")
    nan = float("nan")
    values: dict[int, array] = {}
    ranks: dict[int, array] = {}
    vit_d_iu: dict[int, float] = {}
    n = 0
    for r in open_csv(z, "food_nutrient.csv"):
        n += 1
        if n % 5_000_000 == 0:
            log(f"  {n:,} rows")
        if not (r.get("nutrient_id") or "").isdigit() or not (r.get("fdc_id") or "").isdigit():
            continue
        nid = int(r["nutrient_id"])
        if nid not in ID_TO_SLOT and nid != VITAMIN_D_IU:
            continue
        fid = int(r["fdc_id"])
        if fid not in foods or not r["amount"]:
            continue
        amount = float(r["amount"])
        if nid == VITAMIN_D_IU:
            vit_d_iu[fid] = amount
            continue
        slot, rank = ID_TO_SLOT[nid]
        if fid not in values:
            values[fid] = array("f", [nan] * len(KEYS))
            ranks[fid] = array("b", [99] * len(KEYS))
        if rank < ranks[fid][slot]:
            values[fid][slot] = amount
            ranks[fid][slot] = rank
    log(f"  {n:,} rows read, {len(values):,} foods with nutrients")

    out = Path(out_path)
    tmp = out.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)

    log("Writing foods…")
    vd = KEYS.index("vitamin_d_mcg")
    batch = []
    written = 0
    for fid, vals in values.items():
        if math.isnan(vals[0]):  # no energy value: not useful for meal totals
            continue
        if math.isnan(vals[vd]) and fid in vit_d_iu:
            vals[vd] = vit_d_iu[fid] / 40
        data_type, description, category = foods[fid]
        brand, gtin, ingredients, bcat = branded.get(fid, (None, None, None, None))
        nutrients = [None if math.isnan(v) else round(v, 3) for v in vals]
        batch.append((fid, data_type, description, category or bcat or None, brand or None, gtin or None,
                      ingredients or None, *nutrients))
        if len(batch) >= 20_000:
            db.executemany(f"INSERT INTO foods VALUES ({','.join('?' * (7 + len(KEYS)))})", batch)
            written += len(batch)
            batch.clear()
    db.executemany(f"INSERT INTO foods VALUES ({','.join('?' * (7 + len(KEYS)))})", batch)
    written += len(batch)
    log(f"  {written:,} foods written")

    log("Writing portions…")
    units = {}
    rows = open_csv(z, "measure_unit.csv")
    for r in rows or []:
        units[r["id"]] = r["name"]
    portions = []
    rows = open_csv(z, "food_portion.csv")
    for r in rows or []:
        if not (r.get("fdc_id") or "").strip().isdigit() or not r.get("gram_weight"):
            continue  # USDA's export has a few blank rows
        fid = int(r["fdc_id"])
        if fid not in values:
            continue
        unit = units.get(r.get("measure_unit_id"), "")
        unit = "" if unit in ("undetermined", "") else unit
        parts = [r.get("amount") or "", unit, r.get("modifier") or "", r.get("portion_description") or ""]
        text = " ".join(p.strip() for p in parts if p and p.strip() and p.strip() != "Quantity not specified")
        if text:
            portions.append((fid, text, float(r["gram_weight"])))
    db.executemany("INSERT INTO portions VALUES (?,?,?)", portions)
    log(f"  {len(portions):,} portions")

    log("Building the search index…")
    db.executescript("""
        CREATE VIRTUAL TABLE foods_fts USING fts5(
            description, category, brand, content='foods', content_rowid='fdc_id', tokenize='porter unicode61'
        );
        INSERT INTO foods_fts(rowid, description, category, brand) SELECT fdc_id, description, category, brand FROM foods;
        INSERT INTO foods_fts(foods_fts) VALUES ('optimize');
    """)
    add_generic_index(db)
    db.execute("INSERT INTO meta VALUES ('source', ?)", (Path(zip_path).name,))
    db.execute("INSERT INTO meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M"),))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    log(f"Done: {out} ({out.stat().st_size / 1e6:,.0f} MB)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/build_food_db.py <FoodData_Central_csv_*.zip> [out.db]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).resolve().parent.parent / "data" / "foods.db"))
