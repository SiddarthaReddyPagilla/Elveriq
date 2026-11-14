# Phase 2 outbound execution — order-bound pick / pack / dispatch

**November 14, 2026 development batch. Status: testable prototype; pilot pending.**

## What this release actually does

1. Create a reserved customer order using existing `/api/orders`.
2. Put received stock into a named active physical bin using the Phase 1.1 task scanner.
3. A manager plans one or more `OutboundPick` rows against **specific order line IDs and bins**. A conditional SQL update commits the bin stock (`BinStock.allocated`); order-line totals cannot be over-planned.
4. A staff member claims and starts each queued pick; scans the **SKU and source bin**. Only that worker can verify the in-progress pick. Verification removes units from `BinStock` into an **order-bound staged pool** but keeps `StockLevel.on_hand` and `StockLevel.reserved` unchanged.
5. Workers create scannable cartons; pack verified whole picks into an open carton with SKU and carton barcode checks, then seal cartons. One pick cannot be packed into multiple cartons.
6. A manager dispatches only when **all reserved order lines are completely packed and all cartons are sealed**. In the same database transaction, picked rows become shipped, `StockLevel.on_hand` and `.reserved` each decrease, `StockMovement(kind='ship')` audit entries are written, and the customer order becomes fulfilled. A stable `Idempotency-Key` lets clients safely replay that request.

Cartons are software records of physical packages. Carrier and tracking fields are **manual references**: no shipping labels, carrier booking, tracking polling, manifests, shipping rates, or external carrier integration is provided.

## Inventory invariants and compatibility

- Warehouse stock is still the accounting authority. A bin is a physical subset; *staged outbound units* are outside bins but remain included in warehouse on-hand until dispatch.
- `protected_units_expr()` now protects **placed + pending putaway + staged outbound** from legacy stock reducers; putaway creation also excludes staged outbound units.
- Legacy `/api/orders/{id}/fulfill` and `/cancel` reject orders that still have noncanceled outbound picks. **Do not attempt to bypass this by manually editing the database.** If a pick has already been scanned, the current supported resolution is to finish packing and dispatch; reverse-pick and short-pick workflows are future work.
- A planned pick is not a shipment. A pick scan is not a warehouse-level stock debit. Dispatch is the only outbound operation that deducts on-hand after physical picking.
- The work queue uses optimistic, SQL-conditional state changes under the warehouse/product stock row lock. Only active workers with valid CSRF/session credentials can execute work.
- All order, line, bin, task, carton and shipment lookups enforce authenticated business tenancy. Cartons cannot contain picks from another order or warehouse.

## Routes (`/api` prefix)

| Endpoint | Action | Permission |
|---|---|---|
| `GET /outbound/orders/{id}/lines` | Lines with planned/packed quantities | Signed in |
| `GET /outbound/picks` | Pick queue, optional `order_id` | Signed in |
| `GET /outbound/picks/{id}/events` | Worker/event history | Signed in |
| `POST /outbound/orders/{id}/picks` | `{order_line_id, bin_id, quantity}` + `Idempotency-Key` | Owner/manager |
| `POST /outbound/picks/{id}/claim` | Claim unassigned work | Staff/manager/owner |
| `POST /outbound/picks/{id}/start` | Start own assigned work | Assigned worker |
| `POST /outbound/picks/{id}/scan` | `{scan_sku, scan_bin}` | Assigned worker |
| `POST /outbound/picks/{id}/cancel` | Release still-unpicked bin commitments | Owner/manager |
| `GET /outbound/cartons` | Carton list with contents | Signed in |
| `POST /outbound/orders/{id}/cartons` | `{code}` | Staff/manager/owner |
| `POST /outbound/cartons/{id}/pack` | `{pick_id, scan_sku, scan_carton}` | Staff/manager/owner |
| `POST /outbound/cartons/{id}/seal` | Seal a nonempty carton | Staff/manager/owner |
| `GET /outbound/shipments` | Shipped orders and manual tracking reference | Signed in |
| `POST /outbound/orders/{id}/dispatch` | `{carrier, tracking_reference}` + `Idempotency-Key` | Owner/manager |

All POST endpoints require a signed-in non-disabled user and existing `X-CSRF-Token`. Stable idempotency keys are mandatory for pick planning and dispatch. Workers should always use the UI's retry-safe request behavior on network failures, not submit changed details with the same key.

## Migration and staging gate

Required order **before application deployment**:

1. Existing transfer schema migration, if not yet applied: `20261112_reliable_stock_transfers.sql`.
2. Phase 1.1 warehouse task/bin schema: `20261113_warehouse_execution.sql`.
3. Phase 1.1 counts: `20261113_bin_cycle_counts.sql`.
4. **This release:** `20261114_outbound_execution.sql`.

Execute against a *staging backup restoration first*. Review relational constraints and PostgreSQL lock behavior. Example:

```bash
psql "$STAGING_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261114_outbound_execution.sql
ELVERIQ_TEST_POSTGRES_URL='postgresql+psycopg://.../disposable_db' python -m pytest -q
node --check dispatchforge_app/static/app.js
```

The migration is additive and retains old accounting balances. Backups and tested restoration are mandatory for any production rollout. Do not drop the tables to roll back after transactions have been recorded; revert application code under a controlled freeze and reconcile open picks/cartons before reuse.

## Known public-launch blockers

- Real PostgreSQL concurrency acceptance and failure injection on a deployed staging stack; SQLite cannot prove row-lock behavior.
- A canonical per-stock-unit posting ledger replacing both aggregate and physical-subset accounting as the master plan specifies.
- Short pick, returns-to-stock for already scanned picks, order amendment, split-quantity packing, damage/quality holds, and multiwarehouse order fulfillment.
- Carrier API, label/barcode printing, packing material dimensions/weight, tracking, manifests and dock loading.
- Comprehensive mobile scanner testing, per-warehouse staff access, accessibility, audit retention, backups, monitoring and a pilot warehouse.

**Not a production-ready shipping product yet.** This release makes an end-to-end *internal* verified outbound workflow testable and auditable; use it with disposable staging inventory until the release gates pass.
