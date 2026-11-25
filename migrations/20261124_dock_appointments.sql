-- Apply AFTER 20261116_operations_readiness.sql. Additive only.
-- Requires a verified staging backup and rollback plan before production.
BEGIN;
CREATE TABLE dock_doors (
 id SERIAL PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES businesses(id),
 warehouse_id INTEGER NOT NULL REFERENCES warehouses(id), code VARCHAR(64) NOT NULL,
 purpose VARCHAR(16) NOT NULL DEFAULT 'both', active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_dock_door_code UNIQUE(business_id, warehouse_id, code),
 CONSTRAINT ck_dock_door_purpose CHECK(purpose IN ('inbound','outbound','both'))
);
CREATE INDEX ix_dock_doors_business_id ON dock_doors(business_id);
CREATE INDEX ix_dock_doors_warehouse_id ON dock_doors(warehouse_id);
CREATE TABLE dock_appointments (
 id SERIAL PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES businesses(id),
 warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
 door_id INTEGER NOT NULL REFERENCES dock_doors(id), direction VARCHAR(12) NOT NULL,
 reference VARCHAR(100) NOT NULL, carrier VARCHAR(120) NOT NULL DEFAULT '',
 vehicle_plate VARCHAR(64) NOT NULL DEFAULT '', note VARCHAR(300) NOT NULL DEFAULT '',
 start_at TIMESTAMPTZ NOT NULL, end_at TIMESTAMPTZ NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'scheduled', request_key VARCHAR(128) NOT NULL,
 fingerprint VARCHAR(64) NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id),
 checked_in_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, canceled_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_dock_appointment_retry UNIQUE(business_id, request_key),
 CONSTRAINT dock_appointment_positive_window CHECK(end_at > start_at),
 CONSTRAINT ck_dock_appointment_direction CHECK(direction IN ('inbound','outbound')),
 CONSTRAINT ck_dock_appointment_status CHECK(status IN ('scheduled','checked_in','completed','canceled','no_show'))
);
CREATE INDEX ix_dock_appointments_business_id ON dock_appointments(business_id);
CREATE INDEX ix_dock_appointments_warehouse_id ON dock_appointments(warehouse_id);
CREATE INDEX ix_dock_appointments_door_id ON dock_appointments(door_id);
CREATE INDEX ix_dock_appointments_door_window ON dock_appointments(door_id,start_at,end_at,status);
CREATE TABLE dock_appointment_events (
 id SERIAL PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES businesses(id),
 appointment_id INTEGER NOT NULL REFERENCES dock_appointments(id),
 action VARCHAR(32) NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
 note VARCHAR(300) NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_dock_appointment_events_business_id ON dock_appointment_events(business_id);
CREATE INDEX ix_dock_appointment_events_appointment_id ON dock_appointment_events(appointment_id);
COMMIT;
