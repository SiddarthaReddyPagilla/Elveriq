-- Additive Phase 2 outbound schema. Requires the 20261113 bin cycle count migration.

-- Back up staging, check table sizes and locks, then apply BEFORE deploying code.

-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261114_outbound_execution.sql

BEGIN;

CREATE TABLE outbound_picks (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	order_id INTEGER NOT NULL,
	order_line_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	bin_id INTEGER NOT NULL,
	quantity INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	assigned_user_id INTEGER,
	picked_by INTEGER,
	idempotency_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	scan_fingerprint VARCHAR(64),
	created_by INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	picked_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_outbound_pick_key UNIQUE (business_id, idempotency_key),
	CONSTRAINT outbound_pick_qty_positive CHECK (quantity > 0),
	CONSTRAINT outbound_pick_status_valid CHECK (status IN ('queued', 'assigned', 'in_progress', 'picked', 'packed', 'shipped', 'canceled')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(order_id) REFERENCES customer_orders (id),
	FOREIGN KEY(order_line_id) REFERENCES order_lines (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(product_id) REFERENCES products (id),
	FOREIGN KEY(bin_id) REFERENCES warehouse_bins (id),
	FOREIGN KEY(assigned_user_id) REFERENCES users (id),
	FOREIGN KEY(picked_by) REFERENCES users (id),
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX ix_outbound_picks_business_id ON outbound_picks (business_id);

CREATE INDEX ix_outbound_picks_order_id ON outbound_picks (order_id);

CREATE TABLE outbound_pick_events (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	pick_id INTEGER NOT NULL,
	actor_id INTEGER NOT NULL,
	action VARCHAR(32) NOT NULL,
	detail VARCHAR(250) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(pick_id) REFERENCES outbound_picks (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_outbound_pick_events_business_id ON outbound_pick_events (business_id);

CREATE INDEX ix_outbound_pick_events_pick_id ON outbound_pick_events (pick_id);

CREATE TABLE outbound_cartons (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	order_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	code VARCHAR(64) NOT NULL,
	status VARCHAR(12) NOT NULL,
	created_by INTEGER NOT NULL,
	sealed_by INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	sealed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_outbound_carton_code UNIQUE (business_id, code),
	CONSTRAINT outbound_carton_status_valid CHECK (status IN ('open', 'sealed', 'shipped')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(order_id) REFERENCES customer_orders (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	FOREIGN KEY(sealed_by) REFERENCES users (id)
);

CREATE INDEX ix_outbound_cartons_business_id ON outbound_cartons (business_id);

CREATE INDEX ix_outbound_cartons_order_id ON outbound_cartons (order_id);

CREATE TABLE outbound_carton_items (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	carton_id INTEGER NOT NULL,
	pick_id INTEGER NOT NULL,
	quantity INTEGER NOT NULL,
	packed_by INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_carton_item_pick UNIQUE (pick_id),
	CONSTRAINT outbound_carton_item_qty_positive CHECK (quantity > 0),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(carton_id) REFERENCES outbound_cartons (id),
	FOREIGN KEY(pick_id) REFERENCES outbound_picks (id),
	FOREIGN KEY(packed_by) REFERENCES users (id)
);

CREATE INDEX ix_outbound_carton_items_business_id ON outbound_carton_items (business_id);

CREATE INDEX ix_outbound_carton_items_carton_id ON outbound_carton_items (carton_id);

CREATE TABLE outbound_shipments (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	order_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	carrier VARCHAR(80) NOT NULL,
	tracking_reference VARCHAR(120) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	shipped_by INTEGER NOT NULL,
	shipped_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_shipment_order UNIQUE (order_id),
	CONSTRAINT uq_shipment_key UNIQUE (business_id, idempotency_key),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(order_id) REFERENCES customer_orders (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(shipped_by) REFERENCES users (id)
);

CREATE INDEX ix_outbound_shipments_business_id ON outbound_shipments (business_id);

COMMIT;
