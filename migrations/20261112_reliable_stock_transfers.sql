-- Elveriq Warehouse Cloud: additive PostgreSQL migration for safe transfers.
-- Execute against the EXISTING warehouse database before deploying the new code.
-- This does not modify existing stock counts or historical transfer rows.
-- Run with: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261112_reliable_stock_transfers.sql
BEGIN;

ALTER TABLE inventory_transfers
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE inventory_transfers
    ADD COLUMN IF NOT EXISTS request_fingerprint VARCHAR(64);

-- Historical transfers have NULL keys and remain valid. New API transfers
-- require a key. PostgreSQL UNIQUE permits multiple historical NULLs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transfers_tenant_key
    ON inventory_transfers (business_id, idempotency_key);

ALTER TABLE stock_movements
    ADD COLUMN IF NOT EXISTS transfer_id INTEGER REFERENCES inventory_transfers(id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_transfer_id
    ON stock_movements (transfer_id);

COMMIT;
