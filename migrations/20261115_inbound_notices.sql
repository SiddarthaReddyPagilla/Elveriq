-- Additive inbound ASN migration; after 20261114 outbound migration.
-- Apply to backed-up staging before deploying code.
BEGIN;

CREATE TABLE inbound_notices (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	purchase_order_id INTEGER NOT NULL,
	warehouse_id INTEGER NOT NULL,
	reference VARCHAR(100) NOT NULL,
	supplier_reference VARCHAR(120) NOT NULL,
	dock VARCHAR(64) NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_by INTEGER NOT NULL,
	arrived_by INTEGER,
	closed_by INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	arrived_at TIMESTAMP WITH TIME ZONE,
	closed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_inbound_reference UNIQUE (business_id, reference),
	CONSTRAINT inbound_notice_status_valid CHECK (status IN ('planned', 'arrived', 'closed', 'canceled')),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	FOREIGN KEY(arrived_by) REFERENCES users (id),
	FOREIGN KEY(closed_by) REFERENCES users (id)
);

CREATE INDEX ix_inbound_notices_business_id ON inbound_notices (business_id);

CREATE INDEX ix_inbound_notices_purchase_order_id ON inbound_notices (purchase_order_id);

CREATE TABLE inbound_notice_events (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	notice_id INTEGER NOT NULL,
	action VARCHAR(32) NOT NULL,
	note VARCHAR(250) NOT NULL,
	actor_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(notice_id) REFERENCES inbound_notices (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_inbound_notice_events_business_id ON inbound_notice_events (business_id);

CREATE INDEX ix_inbound_notice_events_notice_id ON inbound_notice_events (notice_id);

CREATE TABLE inbound_notice_lines (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	notice_id INTEGER NOT NULL,
	purchase_line_id INTEGER NOT NULL,
	expected INTEGER NOT NULL,
	accepted INTEGER NOT NULL,
	damaged INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inbound_notice_po_line UNIQUE (notice_id, purchase_line_id),
	CONSTRAINT inbound_expected_positive CHECK (expected > 0),
	CONSTRAINT inbound_disposition_within_expected CHECK (accepted >= 0 AND damaged >= 0 AND accepted + damaged <= expected),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(notice_id) REFERENCES inbound_notices (id),
	FOREIGN KEY(purchase_line_id) REFERENCES purchase_order_lines (id)
);

CREATE INDEX ix_inbound_notice_lines_business_id ON inbound_notice_lines (business_id);

CREATE INDEX ix_inbound_notice_lines_notice_id ON inbound_notice_lines (notice_id);

CREATE TABLE inbound_receipts (
	id SERIAL NOT NULL,
	business_id INTEGER NOT NULL,
	notice_id INTEGER NOT NULL,
	notice_line_id INTEGER NOT NULL,
	accepted INTEGER NOT NULL,
	damaged INTEGER NOT NULL,
	scan_sku VARCHAR(80) NOT NULL,
	damage_note VARCHAR(250) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	request_fingerprint VARCHAR(64) NOT NULL,
	actor_id INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_inbound_receipt_key UNIQUE (business_id, idempotency_key),
	CONSTRAINT inbound_receipt_positive CHECK (accepted >= 0 AND damaged >= 0 AND accepted + damaged > 0),
	FOREIGN KEY(business_id) REFERENCES businesses (id),
	FOREIGN KEY(notice_id) REFERENCES inbound_notices (id),
	FOREIGN KEY(notice_line_id) REFERENCES inbound_notice_lines (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_inbound_receipts_business_id ON inbound_receipts (business_id);

CREATE INDEX ix_inbound_receipts_notice_id ON inbound_receipts (notice_id);

COMMIT;
