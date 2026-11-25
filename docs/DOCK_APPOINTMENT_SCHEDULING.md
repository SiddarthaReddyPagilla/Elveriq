# Dock appointment scheduling — operational release

This release adds physical dock doors and manual carrier appointment scheduling.
It does **not** book carriers, receive goods, schedule labor automatically, or change the inventory ledger.

## Deployment gate
1. Back up staging PostgreSQL and restore it to a disposable environment.
2. Apply `migrations/20261124_dock_appointments.sql` **after** the 20261116 migration.
3. Validate tenant roles, concurrent overlapping bookings, and booking replay on PostgreSQL.
4. Deploy application only after the migration succeeds; validate from a logged-in test workspace.
5. Rollback code via previous deployment; preserve tables and records for audit. Do not drop tables in production.

## Invariants
- Every dock code is unique within a warehouse and business.
- A door is either inbound, outbound, or both.
- Windows are timezone-aware ISO-8601; all persisted intervals are UTC.
- Schedule overlap uses `[start, end)` semantics; adjacent bookings are valid.
- PostgreSQL warehouse-row locking serializes booking checks and writes.
- Only `scheduled` and `checked_in` reserve a slot.
- A unique idempotency key identifies each booking; conflicting retries are rejected.
- Staff can check in and release; only owner/manager can create doors, book, cancel or no-show.
- Every successful state transition adds an append-only operator event.
- No dock operation posts, reserves, or adjusts inventory.

## API
- GET/POST `/api/dock/doors`
- GET/POST `/api/dock/appointments`
- GET `/api/dock/doors/{id}/availability?start_at=...&end_at=...`
- POST `/api/dock/appointments/{id}/check-in|complete|cancel|no-show`
- GET `/api/dock/appointments/{id}/events`
- GET `/api/dock/metrics`

## Known limits
No rescheduling, carrier/ASN foreign-key links, physical gate integration, SMS, EDI, device check-ins, or resource optimization yet. These belong in subsequent phases.
