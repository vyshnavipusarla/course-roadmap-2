"""Part 6: save roadmaps and learner progress in SQLite (roadmaps.db)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from schemas import Roadmap, Stage


def _path() -> str:
    return os.getenv("ROADMAP_DB", "roadmaps.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_path(), timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS roadmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL,
            level TEXT,
            hours_per_week INTEGER,
            created_at TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS progress (
            roadmap_id INTEGER NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
            item_key TEXT NOT NULL,
            PRIMARY KEY (roadmap_id, item_key)
        );
        """
    )
    return conn


# ---- the key scheme for trackable items lives here, so UI and export always agree ----
def item_keys(i: int, stage: Stage) -> list[str]:
    keys = [f"s{i}:v{j}" for j in range(len(stage.videos))]
    keys += [f"s{i}:e{j}" for j in range(len(stage.exercises))]
    if stage.project:
        keys += [f"s{i}:d{j}" for j in range(len(stage.project.deliverables))]
    return keys


# ---- roadmaps ----
def save_roadmap(roadmap: Roadmap, level: str = "", hours_per_week: int = 0) -> int:
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO roadmaps (course, level, hours_per_week, created_at, data) VALUES (?,?,?,?,?)",
            (roadmap.course, level, hours_per_week,
             datetime.now(timezone.utc).isoformat(timespec="seconds"), roadmap.model_dump_json()),
        )
        return cur.lastrowid


def list_roadmaps() -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, course, level, hours_per_week, created_at FROM roadmaps ORDER BY id DESC"
        ).fetchall()
    return [dict(zip(("id", "course", "level", "hours_per_week", "created_at"), r)) for r in rows]


def load_roadmap(roadmap_id: int) -> Roadmap | None:
    with closing(_conn()) as conn:
        row = conn.execute("SELECT data FROM roadmaps WHERE id = ?", (roadmap_id,)).fetchone()
    return Roadmap.model_validate_json(row[0]) if row else None


def delete_roadmap(roadmap_id: int) -> None:
    with closing(_conn()) as conn, conn:
        conn.execute("DELETE FROM roadmaps WHERE id = ?", (roadmap_id,))   # progress rows cascade


# ---- progress ----
def get_progress(roadmap_id: int) -> set[str]:
    with closing(_conn()) as conn:
        rows = conn.execute("SELECT item_key FROM progress WHERE roadmap_id = ?", (roadmap_id,)).fetchall()
    return {r[0] for r in rows}


def set_progress(roadmap_id: int, key: str, done: bool) -> None:
    with closing(_conn()) as conn, conn:
        if done:
            conn.execute("INSERT OR IGNORE INTO progress VALUES (?, ?)", (roadmap_id, key))
        else:
            conn.execute("DELETE FROM progress WHERE roadmap_id = ? AND item_key = ?", (roadmap_id, key))
