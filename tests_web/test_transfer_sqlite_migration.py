"""Existing local SQLite demo databases can be upgraded without losing rows."""
import sqlite3

from scripts.upgrade_transfers_sqlite import upgrade


def test_sqlite_upgrade_keeps_legacy_rows_and_is_repeatable(tmp_path):
    db_path = tmp_path / 'old-demo.sqlite3'
    with sqlite3.connect(db_path) as conn:
        conn.executescript('''
            CREATE TABLE inventory_transfers (
                id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, note TEXT
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL, note TEXT
            );
            INSERT INTO inventory_transfers (id, business_id, note)
                VALUES (7, 42, 'legacy transfer');
            INSERT INTO stock_movements (id, business_id, note)
                VALUES (9, 42, 'legacy audit');
        ''')
    upgrade(db_path)
    upgrade(db_path)  # Repeat is safe.
    with sqlite3.connect(db_path) as conn:
        fields = {row[1] for row in conn.execute('PRAGMA table_info(inventory_transfers)')}
        assert {'idempotency_key', 'request_fingerprint'} <= fields
        fields = {row[1] for row in conn.execute('PRAGMA table_info(stock_movements)')}
        assert 'transfer_id' in fields
        assert conn.execute('SELECT note FROM inventory_transfers WHERE id=7').fetchone() == ('legacy transfer',)
        assert conn.execute('SELECT note FROM stock_movements WHERE id=9').fetchone() == ('legacy audit',)
        conn.execute('UPDATE inventory_transfers SET idempotency_key=? WHERE id=7', ('key',))
        conn.execute('INSERT INTO inventory_transfers (id, business_id, idempotency_key) VALUES (8, 42, ?)', ('other',))
        try:
            conn.execute('INSERT INTO inventory_transfers (id, business_id, idempotency_key) VALUES (10, 42, ?)', ('key',))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError('Tenant/key unique index missing')
