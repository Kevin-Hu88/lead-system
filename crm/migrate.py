# -*- coding: utf-8 -*-
"""Database migration - add new columns to existing leads table"""
import sqlite3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import settings

DB_PATH = settings.DB_PATH

COLUMNS_TO_ADD = [
    ("lead_level", "TEXT DEFAULT 'C'"),
    ("total_score", "INTEGER DEFAULT 0"),
    ("source_score", "INTEGER DEFAULT 0"),
    ("keyword_score", "INTEGER DEFAULT 0"),
    ("area_score", "INTEGER DEFAULT 0"),
    ("corp_score", "INTEGER DEFAULT 0"),
    ("is_opt_out", "INTEGER DEFAULT 0"),
    ("opt_out_at", "TEXT"),
    ("sleep_status", "INTEGER DEFAULT 0"),
]

def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cur.fetchall()}
    added = 0
    for col_name, col_def in COLUMNS_TO_ADD:
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def}")
                added += 1
                print(f"  Added: {col_name}")
            except Exception as e:
                print(f"  Skip {col_name}: {e}")
    conn.commit()
    conn.close()
    print(f"Migration done. {added} columns added.")

if __name__ == "__main__":
    migrate()
