-- Elveriq Phase 1.1 additive migration: physical bin-level inventory counts.
-- Requires migrations/20261113_warehouse_execution.sql already applied.
-- Back up, validate on staging, then run:
-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_bin_cycle_counts.sql
BEGIN;

CREATE TABLE IF NOT EXISTS bin_cycle_counts (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
    bin_id INTEGER NOT NULL REFERENCES warehouse_bins(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    expected_on_hand INTEGER NOT NULL,
    expected_allocated INTEGER NOT NULL,
    expected_warehouse_on_hand INTEGER NOT NULL,
    expected_movement_id INTEGER NOT NULL DEFAULT 0,
    expected_task_event_id INTEGER NOT NULL DEFAULT 0,
    counted_on_hand INTEGER,
    status VARCHAR(20) NOT NULL,
    note VARCHAR(250) NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    posted_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL,
    posted_at TIMESTAMPTZ,
    CONSTRAINT bin_count_expected_nonnegative CHECK (expected_on_hand >= 0),
    CONSTRAINT bin_count_allocated_nonnegative CHECK (expected_allocated >= 0),
    CONSTRAINT bin_count_warehouse_nonnegative CHECK (expected_warehouse_on_hand >= 0),
    CONSTRAINT bin_count_observed_nonnegative CHECK (counted_on_hand IS NULL OR counted_on_hand >= 0),
    CONSTRAINT bin_count_status_valid CHECK (status IN ('open', 'posted', 'canceled'))
);
CREATE INDEX IF NOT EXISTS ix_bin_cycle_counts_business_id ON bin_cycle_counts(business_id);
CREATE INDEX IF NOT EXISTS ix_bin_cycle_counts_bin_status ON bin_cycle_counts(bin_id, status);
COMMIT;
