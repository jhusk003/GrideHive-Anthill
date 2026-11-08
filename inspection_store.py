"""SQLite-backed demo inspection notes and optional image thumbnails.

Local disk is durable on a laptop. Public hosting with an ephemeral filesystem is not.
Do not put sensitive or operational utility information in this public demo.
"""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / 'data' / 'gridhive_demo.sqlite3'


def _db_path():
    return Path(os.environ.get('GRIDHIVE_DB_PATH', str(DEFAULT_DB)))


def connect():
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def setup():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            status TEXT NOT NULL,
            severity INTEGER NOT NULL,
            confidence TEXT NOT NULL,
            notes TEXT NOT NULL,
            image_name TEXT,
            image_data BLOB
        )''')
        con.execute('CREATE INDEX IF NOT EXISTS idx_inspections_asset ON inspections(asset_id, id DESC)')


def add(asset_id, status, severity, confidence, notes, image_name=None, image_data=None):
    setup()
    created = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with connect() as con:
        cur = con.execute('''INSERT INTO inspections
            (created_at,asset_id,status,severity,confidence,notes,image_name,image_data)
            VALUES (?,?,?,?,?,?,?,?)''',
            (created, asset_id, status, severity, confidence, notes, image_name, image_data))
        return cur.lastrowid


def list_inspections(limit=200, with_images=False):
    setup()
    select_images = 'image_data' if with_images else 'NULL AS image_data'
    with connect() as con:
        rows = con.execute(f'''SELECT id, created_at, asset_id, status, severity,
            confidence, notes, image_name, {select_images}
            FROM inspections ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()
    return [dict(r) for r in rows]


def find_image(inspection_id):
    with connect() as con:
        row = con.execute('SELECT image_data FROM inspections WHERE id=?', (inspection_id,)).fetchone()
    return row['image_data'] if row else None


def reset_demo_inspections():
    setup()
    with connect() as con:
        con.execute('DELETE FROM inspections')
