"""Upgrade an EXISTING local demo SQLite database without deleting its data.

PostgreSQL production uses migrations/20261112_reliable_stock_transfers.sql.
This is only for existing SQLite demo databases; create_all handles new ones.
"""
import argparse
import sqlite3
from pathlib import Path


def upgrade(path: Path):
    if not path.is_file():
        raise SystemExit(f"SQLite database does not exist: {path}")
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            for table in ("inventory_transfers", "stock_movements"):
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    raise SystemExit(f"Expected table missing: {table}")
            transfer_cols = {row[1] for row in db.execute("PRAGMA table_info(inventory_transfers)")}
            movement_cols = {row[1] for row in db.execute("PRAGMA table_info(stock_movements)")}
            if "idempotency_key" not in transfer_cols:
                db.execute("ALTER TABLE inventory_transfers ADD COLUMN idempotency_key VARCHAR(128)")
            if "request_fingerprint" not in transfer_cols:
                db.execute("ALTER TABLE inventory_transfers ADD COLUMN request_fingerprint VARCHAR(64)")
            if "transfer_id" not in movement_cols:
                db.execute("ALTER TABLE stock_movements ADD COLUMN transfer_id INTEGER REFERENCES inventory_transfers(id)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transfers_tenant_key "
                       "ON inventory_transfers (business_id, idempotency_key)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_stock_movements_transfer_id "
                       "ON stock_movements (transfer_id)")
            db.commit()
        except BaseException:
            db.rollback()
            raise
    print(f"Transfer schema upgraded: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to existing local SQLite .sqlite3 database")
    upgrade(parser.parse_args().path)
