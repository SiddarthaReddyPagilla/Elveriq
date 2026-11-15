-- Requires 20261115_inbound_notices.sql. Additive staging migration.
BEGIN;

CREATE TABLE warehouse_exceptions (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	source_type VARCHAR(32) NOT NULL,
	source_id INTEGER,
	category VARCHAR(40) NOT NULL,
	severity VARCHAR(12) NOT NULL,
	title VARCHAR(160) NOT NULL,
	detail VARCHAR(500) NOT NULL,
	status VARCHAR(20) NOT NULL,
	dedupe_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	created_by INTEGER NOT NULL,
	assigned_user_id INTEGER,
	resolved_by INTEGER,
	due_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	acknowledged_at TIMESTAMP WITH TIME ZONE,
	resolved_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_warehouse_exception_key UNIQUE (business_id, dedupe_key),
	CONSTRAINT warehouse_exception_status_valid CHECK (status IN ('open','acknowledged','resolved')),
	CONSTRAINT warehouse_exception_severity_valid CHECK (severity IN ('low','medium','high','critical')),
	CONSTRAINT warehouse_exception_category_valid CHECK (category IN ('manual','inbound_damage','inbound_shortage','outbound_short_pick','shipment_issue','stock_discrepancy')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	FOREIGN KEY(assigned_user_id) REFERENCES users (id),
	FOREIGN KEY(resolved_by) REFERENCES users (id)
);

CREATE INDEX ix_warehouse_exceptions_business_id ON warehouse_exceptions (business_id);

CREATE TABLE warehouse_exception_events (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	exception_id INTEGER NOT NULL,
	action VARCHAR(32) NOT NULL,
	note VARCHAR(500) NOT NULL,
	actor_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(exception_id) REFERENCES warehouse_exceptions (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_warehouse_exception_events_business_id ON warehouse_exception_events (business_id);

CREATE INDEX ix_warehouse_exception_events_exception_id ON warehouse_exception_events (exception_id);

CREATE TABLE shipment_tracking_updates (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	shipment_id INTEGER NOT NULL,
	milestone VARCHAR(24) NOT NULL,
	location VARCHAR(120) NOT NULL,
	note VARCHAR(250) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	recorded_by INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_tracking_retry_key UNIQUE (business_id, idempotency_key),
	CONSTRAINT tracking_milestone_valid CHECK (milestone IN ('in_transit','out_for_delivery','delayed','exception','delivered')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(shipment_id) REFERENCES outbound_shipments (id),
	FOREIGN KEY(recorded_by) REFERENCES users (id)
);

CREATE INDEX ix_shipment_tracking_updates_business_id ON shipment_tracking_updates (business_id);

CREATE INDEX ix_shipment_tracking_updates_shipment_id ON shipment_tracking_updates (shipment_id);

COMMIT;
