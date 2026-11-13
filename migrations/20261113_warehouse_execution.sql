-- Elveriq Phase 1 warehouse execution: additive PostgreSQL schema.

-- Back up database and run BEFORE deploying matching API code.

-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_warehouse_execution.sql

BEGIN;


CREATE TABLE IF NOT EXISTS warehouse_bins (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	code VARCHAR(64) NOT NULL,
	zone VARCHAR(60) NOT NULL,
	aisle VARCHAR(40) NOT NULL,
	rack VARCHAR(40) NOT NULL,
	shelf VARCHAR(40) NOT NULL,
	capacity_units INTEGER,
	active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_warehouse_bin_code UNIQUE (warehouse_id, code),
	CONSTRAINT bin_capacity_positive CHECK (capacity_units IS NULL OR capacity_units > 0),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX IF NOT EXISTS ix_warehouse_bins_business_id ON warehouse_bins (business_id);


CREATE TABLE IF NOT EXISTS bin_stocks (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	bin_id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	on_hand INTEGER NOT NULL,
	allocated INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_bin_product UNIQUE (bin_id, product_id),
	CONSTRAINT bin_stock_on_hand_nonnegative CHECK (on_hand >= 0),
	CONSTRAINT bin_stock_allocated_within_hand CHECK (allocated >= 0 AND allocated <= on_hand),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(bin_id) REFERENCES warehouse_bins (id),
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX IF NOT EXISTS ix_bin_stocks_business_id ON bin_stocks (business_id);


CREATE TABLE IF NOT EXISTS warehouse_tasks (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	kind VARCHAR(16) NOT NULL,
	from_bin_id INTEGER,
	to_bin_id INTEGER,
	quantity INTEGER NOT NULL,
	priority INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	note VARCHAR(250) NOT NULL,
	created_by INTEGER NOT NULL,
	assigned_user_id INTEGER,
	completed_by INTEGER,
	scan_fingerprint VARCHAR(64),
	idempotency_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_warehouse_task_key UNIQUE (business_id, idempotency_key),
	CONSTRAINT warehouse_task_qty_positive CHECK (quantity > 0),
	CONSTRAINT warehouse_task_priority_range CHECK (priority BETWEEN 1 AND 5),
	CONSTRAINT warehouse_task_kind_valid CHECK (kind IN ('putaway', 'move', 'unlocate')),
	CONSTRAINT warehouse_task_locations_valid CHECK ((kind = 'putaway' AND from_bin_id IS NULL AND to_bin_id IS NOT NULL) OR (kind = 'move' AND from_bin_id IS NOT NULL AND to_bin_id IS NOT NULL AND from_bin_id <> to_bin_id) OR (kind = 'unlocate' AND from_bin_id IS NOT NULL AND to_bin_id IS NULL)),
	CONSTRAINT warehouse_task_status_valid CHECK (status IN ('queued', 'assigned', 'in_progress', 'completed', 'canceled')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(product_id) REFERENCES products (id),
	FOREIGN KEY(from_bin_id) REFERENCES warehouse_bins (id),
	FOREIGN KEY(to_bin_id) REFERENCES warehouse_bins (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	FOREIGN KEY(assigned_user_id) REFERENCES users (id),
	FOREIGN KEY(completed_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_warehouse_tasks_business_id ON warehouse_tasks (business_id);


CREATE TABLE IF NOT EXISTS warehouse_task_events (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	task_id INTEGER NOT NULL,
	actor_id INTEGER NOT NULL,
	action VARCHAR(32) NOT NULL,
	detail VARCHAR(250) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(task_id) REFERENCES warehouse_tasks (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_warehouse_task_events_business_id ON warehouse_task_events (business_id);

CREATE INDEX IF NOT EXISTS ix_warehouse_task_events_task_id ON warehouse_task_events (task_id);

COMMIT;
