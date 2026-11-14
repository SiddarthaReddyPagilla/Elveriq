# Elveriq inbound ASN execution — staging milestone

**Scope:** Purchase-order-linked advance shipment notices (ASNs), dock arrival, SKU-verified intake, accepted/damaged dispositions, shortage close-out and immutable receipt history.

**This is not a production-quality supplier EDI integration or certified QC quarantine.** The supplier reference is manually entered; damaged quantities are **not** posted to saleable stock or the PO received total. Do not present these as quarantined physical stock: tracking physical damaged goods by storage bin and lot requires a future quality-inventory model.

## Migration and rollout order

1. Back up staging PostgreSQL and practice restoring the backup.
2. Verify transfer, warehouse execution, bin counting and `20261114_outbound_execution.sql` migrations are applied.
3. Apply `psql "$STAGING_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261115_inbound_notices.sql` once to staging. This migration is additive; do not run it twice without migration tooling.
4. Deploy new application code to staging, run tests with `ELVERIQ_TEST_POSTGRES_URL` and inspect constraint/index creation.
5. Validate browser and handheld workflow with a real scanner, supplier PO and a physical partial delivery. Verify `sum(stock_movements.on_hand_delta)` equals accepted receipt quantities and no damaged or short units were posted.
6. Only after passing staging checks, schedule production with tested backups and a reversal plan. DB tables may be retained on app rollback.

## API workflow

1. Create a purchase order with SKU lines through `/api/purchase-orders`.
2. `POST /api/inbound/notices` as owner or manager using `{purchase_order_id,reference,supplier_reference,dock,items:[{purchase_line_id,expected}]}`. Quantities must fit the PO's unreceived units minus other **open** ASNs.
3. `POST /api/inbound/notices/{id}/arrive` at the physical dock (safe to repeat).
4. `POST /api/inbound/notices/{id}/scan` as authenticated staff or manager with `Idempotency-Key` header (8–128 safe characters) and `{line_id,scan_sku,accepted,damaged,damage_note}`. A damaged scan requires a reason; accepted units post to the canonical **existing** PO receiving accounting path in the same transaction. A matching retry returns `replayed=true`, never a second stock movement.
5. `GET /api/inbound/notices` returns expected/accepted/damaged/short by line; `/receipts` and `/events` return operator evidence.
6. `POST /api/inbound/notices/{id}/close` as manager/owner with `{note}`. If units are missing, at least three characters of closure explanation are required. A short does not invent received stock.
7. Cancel only unreceived ASNs through `/cancel`; an ASN with any recorded disposition cannot be canceled and stock cannot be silently reversed.

**Multi-tenant enforcement:** All reads and mutations validate the authenticated tenant. CSRF is mandatory for writes. Manual PO receiving via existing APIs remains supported and shared PO quantity constraints prevent over-receipt.

## Known launch gaps

- Supplier EDI/ASN ingestion; blind receiving; supplier barcode mappings; serial/lot capture; batch expiration.
- Damaged stock quarantine and release with QC status; physical discrepancy photographs; returns-to-vendor.
- Dock appointment scheduling, gate check-in, carrier arrival integrations, label printing.
- PostgreSQL concurrency tests, bulk/load tests, alerting and full rollback verification are still release gates.
