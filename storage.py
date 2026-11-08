"""Local SQLite or PostgreSQL demo storage."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_URL = os.getenv("DATABASE_URL", "")

DB_FILE = os.path.join(
    os.path.dirname(__file__),
    "gridhive_v4.sqlite3"
)


@contextmanager
def db():
    if DB_URL:
        import psycopg
        from psycopg.rows import dict_row

        con = psycopg.connect(
            DB_URL,
            row_factory=dict_row
        )
    else:
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def query(sql):
    return (
        sql.replace("?", "%s")
        if DB_URL else sql
    )


def init():
    id_type = (
        "BIGSERIAL PRIMARY KEY"
        if DB_URL
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    blob = "BYTEA" if DB_URL else "BLOB"

    with db() as con:
        con.execute(
            f"CREATE TABLE IF NOT EXISTS inspections ("
            f"id {id_type}, "
            "asset_id TEXT NOT NULL, "
            "severity INTEGER NOT NULL, "
            "source TEXT NOT NULL, "
            "notes TEXT NOT NULL, "
            f"image {blob}, "
            "ai_note TEXT NOT NULL DEFAULT '', "
            "verified INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL)"
        )

        con.execute(
            f"CREATE TABLE IF NOT EXISTS events ("
            f"id {id_type}, "
            "category TEXT NOT NULL, "
            "message TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )


def stamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def log(category, message):
    with db() as con:
        con.execute(
            query(
                "INSERT INTO events "
                "(category,message,created_at) "
                "VALUES (?,?,?)"
            ),
            (category, message[:300], stamp())
        )


def add_inspection(
    asset_id, severity, source,
    notes, image=None, ai_note=""
):
    with db() as con:
        con.execute(
            query(
                "INSERT INTO inspections "
                "(asset_id,severity,source,notes,image,"
                "ai_note,verified,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)"
            ),
            (
                asset_id,
                int(severity),
                source,
                notes[:1200],
                image,
                ai_note[:1500],
                0,
                stamp()
            )
        )

    log(
        "INSPECTION",
        f"Pending human review: {asset_id} ({source})"
    )


def list_inspections():
    with db() as con:
        rows = con.execute(
            "SELECT id,asset_id,severity,source,notes,"
            "image,ai_note,verified,created_at "
            "FROM inspections "
            "ORDER BY id DESC LIMIT 100"
        ).fetchall()

        return [dict(row) for row in rows]


def approve(inspection_id):
    with db() as con:
        con.execute(
            query(
                "UPDATE inspections SET verified=1 "
                "WHERE id=?"
            ),
            (inspection_id,)
        )

    log(
        "APPROVED",
        f"Inspection #{inspection_id} verified"
    )


def events():
    with db() as con:
        rows = con.execute(
            "SELECT category,message,created_at "
            "FROM events ORDER BY id DESC LIMIT 80"
        ).fetchall()

        return [dict(row) for row in rows]


def reset():
    with db() as con:
        con.execute("DELETE FROM inspections")
        con.execute("DELETE FROM events")

    log("RESET", "Demo scenario reset")