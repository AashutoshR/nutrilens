"""One-off fix for recipe databases built before cuisine_of(): relabel cuisines in place (no full rebuild).

    python scripts/fix_recipe_cuisines.py [data/recipes.db]
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_recipe_db import cuisine_of  # noqa: E402

db_path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "data" / "recipes.db")
db = sqlite3.connect(db_path, timeout=60)
changed = []
for rid, name, category, keywords, cuisine, ingredients in db.execute(
        "SELECT id, name, category, keywords, cuisine, ingredients FROM recipes"):
    new = cuisine_of(category or "", [k.strip() for k in (keywords or "").split(",") if k.strip()], name)
    if new != cuisine:
        changed.append((rid, name, category, keywords, cuisine, ingredients, new))
print(f"{len(changed):,} recipes to relabel")

with db:
    for rid, name, category, keywords, old, ingredients, new in changed:
        # External-content FTS rows are replaced by deleting with the old indexed values, then inserting the new ones.
        db.execute("INSERT INTO recipes_fts(recipes_fts, rowid, name, keywords, category, ingredients) VALUES('delete', ?, ?, ?, ?, ?)",
                   (rid, name, f"{keywords} {old or ''}", category, ingredients))
        db.execute("INSERT INTO recipes_fts(rowid, name, keywords, category, ingredients) VALUES (?, ?, ?, ?, ?)",
                   (rid, name, f"{keywords} {new or ''}", category, ingredients))
        db.execute("UPDATE recipes SET cuisine = ? WHERE id = ?", (new, rid))
print("done")
