"""Tiny SQLite store for profiles and meal logs.

On a personal computer there is one user ("local"). When hosted (NUTRILENS_PUBLIC), every visitor gets an
anonymous id in a cookie, and all profile and meal queries are scoped to it.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime

from .config import settings
from .schemas import LogMealRequest, Profile

# Whose data the current request reads and writes (set per request by main.py).
visitor: ContextVar[str] = ContextVar("visitor", default="local")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    visitor TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eaten_at TEXT NOT NULL,
    day TEXT NOT NULL,
    dish_name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    items TEXT NOT NULL,
    calories REAL NOT NULL,
    thumbnail TEXT
);
CREATE INDEX IF NOT EXISTS meals_day ON meals(day);
CREATE TABLE IF NOT EXISTS recipe_measurements (
    recipe_id INTEGER PRIMARY KEY,
    lines TEXT NOT NULL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Older databases: give meals an owner and move the single profile over to the "local" user.
        if "visitor" not in {r["name"] for r in conn.execute("PRAGMA table_info(meals)")}:
            conn.execute("ALTER TABLE meals ADD COLUMN visitor TEXT NOT NULL DEFAULT 'local'")
        conn.execute("CREATE INDEX IF NOT EXISTS meals_visitor_day ON meals(visitor, day)")
        conn.execute("INSERT OR IGNORE INTO profiles (visitor, data) SELECT 'local', data FROM profile WHERE id = 1")


def get_profile() -> Profile:
    with connect() as conn:
        row = conn.execute("SELECT data FROM profiles WHERE visitor = ?", (visitor.get(),)).fetchone()
    return Profile.model_validate_json(row["data"]) if row else Profile()


def save_profile(p: Profile) -> Profile:
    with connect() as conn:
        conn.execute(
            "INSERT INTO profiles (visitor, data) VALUES (?, ?) "
            "ON CONFLICT(visitor) DO UPDATE SET data = excluded.data, updated_at = CURRENT_TIMESTAMP",
            (visitor.get(), p.model_dump_json()),
        )
    return p


def add_meal(m: LogMealRequest, calories: float) -> int:
    now = datetime.now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO meals (visitor, eaten_at, day, dish_name, cuisine, meal_type, items, calories, thumbnail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (visitor.get(), now.isoformat(timespec="seconds"), now.date().isoformat(), m.dish_name, m.cuisine,
             m.meal_type, json.dumps([i.model_dump() for i in m.items]), calories, m.thumbnail),
        )
        return cur.lastrowid


def meals_on(day: date) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE visitor = ? AND day = ? ORDER BY eaten_at", (visitor.get(), day.isoformat())
        ).fetchall()
    return [{**dict(r), "items": json.loads(r["items"])} for r in rows]


def delete_meal(meal_id: int) -> bool:
    with connect() as conn:
        return conn.execute("DELETE FROM meals WHERE id = ? AND visitor = ?", (meal_id, visitor.get())).rowcount > 0


def history(days: int = 7) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT day, ROUND(SUM(calories)) AS calories, COUNT(*) AS meals FROM meals WHERE visitor = ? "
            "GROUP BY day ORDER BY day DESC LIMIT ?", (visitor.get(), days)
        ).fetchall()
    return [dict(r) for r in rows]


def get_measurements(recipe_id: int) -> list[str] | None:
    with connect() as conn:
        row = conn.execute("SELECT lines FROM recipe_measurements WHERE recipe_id = ?", (recipe_id,)).fetchone()
    return json.loads(row["lines"]) if row else None


def save_measurements(recipe_id: int, lines: list[str]) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO recipe_measurements (recipe_id, lines) VALUES (?, ?)", (recipe_id, json.dumps(lines)))
