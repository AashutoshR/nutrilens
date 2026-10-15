"""Make small copies of the food and recipe databases for hosting (e.g. Render's free plan).

  foods:   every generic USDA food (Foundation, SR Legacy, FNDDS dishes), without the 1.8M branded products
  recipes: the most-reviewed recipes with photos, at least PER_CUISINE per cuisine, about 50,000 in total

Run from backend/:  python scripts/build_lite_data.py
Writes data-lite/foods.db.gz and data-lite/recipes.db.gz (the Docker build unpacks them into data/).
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SRC = BACKEND / "data"
OUT = BACKEND / "data-lite"
PER_CUISINE = 2500
TOTAL_RECIPES = 50_000


def log(msg: str) -> None:
    print(msg, flush=True)


def copy_schema(src: sqlite3.Connection, dst: sqlite3.Connection, tables: list[str]) -> None:
    for name in tables:
        sql = src.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]
        dst.execute(sql)


def build_foods(path: Path) -> None:
    log("Foods: copying generic foods…")
    path.unlink(missing_ok=True)
    dst = sqlite3.connect(path)
    dst.execute("ATTACH DATABASE ? AS src", (str(SRC / 'foods.db'),))
    src = sqlite3.connect(f"file:{SRC / 'foods.db'}?mode=ro", uri=True)
    copy_schema(src, dst, ["foods", "portions", "meta"])
    dst.executescript("""
        INSERT INTO foods SELECT * FROM src.foods WHERE data_type != 'branded_food';
        INSERT INTO portions SELECT p.* FROM src.portions p JOIN foods f ON f.fdc_id = p.fdc_id;
        INSERT INTO meta SELECT * FROM src.meta;
        INSERT OR REPLACE INTO meta VALUES ('edition', 'lite: generic foods only');
        CREATE INDEX portions_fdc ON portions(fdc_id);
        CREATE INDEX foods_gtin ON foods(gtin);
        CREATE VIRTUAL TABLE foods_fts USING fts5(
            description, category, brand, content='foods', content_rowid='fdc_id', tokenize='porter unicode61'
        );
        INSERT INTO foods_fts(foods_fts) VALUES ('rebuild');
        CREATE VIRTUAL TABLE generic_fts USING fts5(description, category, tokenize='porter unicode61');
        INSERT INTO generic_fts(rowid, description, category) SELECT fdc_id, description, category FROM foods;
        INSERT INTO generic_fts(generic_fts) VALUES ('optimize');
    """)
    dst.commit()
    dst.execute("DETACH DATABASE src")
    log(f"  {dst.execute('SELECT COUNT(*) FROM foods').fetchone()[0]:,} foods")
    dst.execute("VACUUM")
    dst.close()


def build_recipes(path: Path) -> None:
    log("Recipes: choosing the best-reviewed recipes…")
    src = sqlite3.connect(f"file:{SRC / 'recipes.db'}?mode=ro", uri=True)
    best = "ORDER BY (image IS NOT NULL AND image != '') DESC, COALESCE(reviews, 0) DESC, COALESCE(rating, 0) DESC"
    ids: set[int] = set()
    for (cuisine,) in src.execute("SELECT DISTINCT cuisine FROM recipes WHERE cuisine IS NOT NULL").fetchall():
        ids.update(r[0] for r in src.execute(f"SELECT id FROM recipes WHERE cuisine = ? {best} LIMIT ?", (cuisine, PER_CUISINE)))
    for (rid,) in src.execute(f"SELECT id FROM recipes {best} LIMIT ?", (TOTAL_RECIPES * 2,)):
        if len(ids) >= TOTAL_RECIPES:
            break
        ids.add(rid)
    src.close()

    path.unlink(missing_ok=True)
    dst = sqlite3.connect(path)
    dst.execute("ATTACH DATABASE ? AS src", (str(SRC / 'recipes.db'),))
    src = sqlite3.connect(f"file:{SRC / 'recipes.db'}?mode=ro", uri=True)
    copy_schema(src, dst, ["recipes", "meta"])
    dst.execute("CREATE TEMP TABLE keep (id INTEGER PRIMARY KEY)")
    dst.executemany("INSERT INTO keep VALUES (?)", ((i,) for i in ids))
    dst.executescript("""
        INSERT INTO recipes SELECT r.* FROM src.recipes r JOIN keep k ON k.id = r.id;
        INSERT INTO meta SELECT * FROM src.meta;
        INSERT OR REPLACE INTO meta VALUES ('edition', 'lite: best-reviewed recipes');
        CREATE INDEX recipes_animal ON recipes(animal);
        CREATE VIRTUAL TABLE recipes_fts USING fts5(
            name, keywords, category, ingredients, content='recipes', content_rowid='id', tokenize='porter unicode61'
        );
        INSERT INTO recipes_fts(recipes_fts) VALUES ('rebuild');
        INSERT INTO recipes_fts(recipes_fts) VALUES ('optimize');
    """)
    dst.commit()
    dst.execute("DETACH DATABASE src")
    log(f"  {dst.execute('SELECT COUNT(*) FROM recipes').fetchone()[0]:,} recipes")
    dst.execute("VACUUM")
    dst.close()


def gz(path: Path) -> Path:
    out = path.with_suffix(path.suffix + ".gz")
    with open(path, "rb") as f, gzip.open(out, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)
    path.unlink()
    log(f"  {out.name}: {out.stat().st_size / 1e6:.1f} MB")
    return out


def main() -> None:
    if not (SRC / "foods.db").exists() or not (SRC / "recipes.db").exists():
        sys.exit("Build data/foods.db and data/recipes.db first (see README).")
    OUT.mkdir(exist_ok=True)
    build_foods(OUT / "foods.db")
    gz(OUT / "foods.db")
    build_recipes(OUT / "recipes.db")
    gz(OUT / "recipes.db")


if __name__ == "__main__":
    main()
