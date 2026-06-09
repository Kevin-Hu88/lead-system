# -*- coding: utf-8 -*-
import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import settings
DB_PATH = settings.DB_PATH
COLUMNS = [
    ("bid_budget", "REAL DEFAULT 0"),
    ("bid_budget_text", "TEXT"),
    ("bid_deadline", "TEXT"),
    ("bid_open_time", "TEXT"),
    ("bid_purchaser", "TEXT"),
    ("bid_agency", "TEXT"),
]
def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in cur.fetchall()}
    added = 0
    for col, dtype in COLUMNS:
        if col not in existing:
            try:
                cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {dtype}")
                added += 1
                print(f"  Added: {col}")
            except Exception as e:
                print(f"  Skip {col}: {e}")
    conn.commit()
    conn.close()
    print(f"Migration done. {added} columns added.")
if __name__ == "__main__":
    migrate()
