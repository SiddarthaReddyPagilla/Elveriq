# Phase 1 — Warehouse Execution API and Operator Guide

## Scope

This release adds a physical location registry, bin-placement balances, work task states, scanner-confirmed location changes and audit events. These are incremental features on the original warehouse-level accounting engine. **This document describes the original Phase 1 foundation.** The newer, separately-scoped order-bound outbound flow is documented in `docs/OUTBOUND_EXECUTION.md`; lot/serial, quality holds, carrier shipping and advanced labor management remain unimplemented.

## Data semantics

`stock_levels.on_hand` and `.reserved` remain authoritative. `bin_stocks.on_hand` is the subset of that stock physically placed into named bins. `unlocated = warehouse on_hand - Σ placed` is the received/staged/not-yet-placed pool. Pending putaway reserves unlocated units **without** adjusting warehouse on-hand. A `move` reserves source-bin units and, after correct scanning, changes only the source and destination bin quantities. An `unlocate` reserves and then removes units from a bin back into the unlocated staging pool; it does not fulfill an order. The old `/orders/{id}/fulfill` endpoint may debit *free* unlocated stock only, respecting reservations and excluding any staged outbound units. It refuses orders with active outbound picks. See `docs/OUTBOUND_EXECUTION.md`.

An `unlocate` task has `to_bin_id = null`, uses destination scan literal `UNLOCATED`, and requires a source bin scan. It is currently a staging bridge, not an order-linked pick task. Managers must not consider it proof that an order was picked correctly. The final ledger redesign must move from these transitional semantics to atomic physical state posting and order-specific allocation.

Stock reductions from direct adjustments, warehouse transfers, order fulfillment and cycle count posting are guarded by the correlated `protected_units_expr()` so they cannot consume placed stock, open putaway reservations, or scanned outbound units staged for a specific customer order. Existing receipts and return receipts remain additive and continue to add unlocated units. The safeguards are implemented only through the application's known inventory APIs; unauthorized external SQL that writes the stock tables bypasses them and is unsupported.

## Roles

- Owner/manager: register bins, create and assign tasks, cancel open work, and perform their own warehouse tasks.
- Staff: view bins and work; claim unassigned tasks; start and verify work assigned to them. Cannot create bins/tasks, cancel or reassign.
- Demo visitors: read-only lists and samples. No demo mutations.

## Task states

`queued → assigned → in_progress → completed` or `queued/assigned/in_progress → canceled`. Supervisors may assign/reassign queued/assigned tasks; staff may claim only queued work. Cancellation of a pending move/unlocate releases its source-bin allocation; cancellation of putaway releases pending unlocated stock. Completed work is final; repeating a completion request with the same verified scans and worker returns `replayed: true`, not another move.

## API reference (all routes under `/api`)

| Method | Route | Role | Request / description |
|---|---|---|---|
| GET | `/locations` | Signed-in / demo read-only | Optional `warehouse_id`; bin metadata and placed totals |
| POST | `/locations` | Owner / manager | `{warehouse_id,code,zone,aisle,rack,shelf,capacity_units}` |
| GET | `/locations/stock` | Signed-in / demo read-only | Per-bin SKU placed, allocated and free |
| GET | `/locations/reconciliation` | Signed-in / demo read-only | On-hand, placed, unlocated, pending putaway by warehouse/SKU |
| GET | `/tasks` | Signed-in / demo read-only | 200 newest tasks; optional `warehouse_id` |
| GET | `/tasks/assignees` | Owner / manager | Active employee directory for task assignment |
| GET | `/tasks/{id}/events` | Signed-in / demo read-only | Immutable accepted/rejected event history |
| POST | `/tasks` | Owner / manager | `{warehouse_id,sku,kind,to_bin_id,from_bin_id,quantity,priority,note,assigned_user_id}` |
| POST | `/tasks/{id}/assign` | Owner / manager | `{assigned_user_id: 123}` or `null` to unassign |
| POST | `/tasks/{id}/claim` | Any active worker | Atomically claim queued task |
| POST | `/tasks/{id}/start` | Assigned worker | Enter execution state |
| POST | `/tasks/{id}/complete` | Assigned worker | `{scan_sku,scan_to_bin,scan_from_bin}`; values scanned from physical labels |
| POST | `/tasks/{id}/cancel` | Owner / manager | Cancel work, release reservations |

POST requests require the existing `X-CSRF-Token` session token. Task creation additionally requires the `Idempotency-Key` header: 8–128 safe characters, held constant while retrying the **same** request. A reused key with altered details yields HTTP 409. All warehouse/bin/task identifiers must belong to the actor's business and valid warehouse. Invalid scans return HTTP 409, preserve stock, and create a `scan_rejected` task event.

## Walk-through

1. Sign in to a business workspace; in **Inventory**, receive 20 units of `BOX-001` into a warehouse.
2. In **Storage bins**, create `A-01` and `A-02` in that warehouse with optional capacities.
3. In **Warehouse tasks**, create a putaway of 10 `BOX-001` units to `A-01`. A unique operation key is included by the browser.
4. Claim the task, start it, click **Scan**, and scan/type product `BOX-001` and destination `A-01`. The task is completed; ten units appear in `A-01`, ten remain unlocated; warehouse on-hand stays 20.
5. Create a `move` of 4 from `A-01` to `A-02`. Complete scans for SKU, source and destination. The bins hold 6 and 4.
6. Create `unlocate` for 4 from `A-02`, claim/start, and scan `BOX-001`, `A-02`, destination `UNLOCATED`. That bin decreases by 4; unlocated increases by 4.
7. Existing order fulfillment can now consume enough physically unlocated units (subject to available reservation); it does **not** itself prove order-linked picking.
8. Use the **reconciliation** report and task history to inspect all changes.

## Pre-deployment

1. Stop incompatible application writes/deployments and **back up production**.
2. Apply the earlier transfer migration if not already present.
3. Apply `migrations/20261113_warehouse_execution.sql` on production PostgreSQL before shipping code. It is additive: four new tables; old stock balances are untouched. Run from `psql` with `-v ON_ERROR_STOP=1`.
4. Deploy application code, keeping all sessions pinned to the same migrated database.
5. Run the complete test suite against a disposable test database, including real PostgreSQL concurrency tests in CI; then manually exercise the walk-through on staging.
6. Confirm restore capability, monitoring, access permissions, logs and reconciliation on pilot data before using live warehouse stock.

## Critical limitations and follow-up work

- Order-specific bin reservations are now offered through the separate `/api/outbound` flow; this legacy `unlocate` task is **still not linked to an order** and cannot substitute for a verified pick. Short picks and outbound returns are not supported yet.
- No lot, serial, expiry, ownership, hold, or handling-unit dimension in `BinStock` yet.
- No physical device SDK, offline transaction queue, optimized routing, bulk wave release, configurable exception codes or barcode label printer.
- Capacities are coarse *unit-count* limits across products, not volume/weight or slotting constraints. No UI to edit/deactivate bins yet.
- No import/backfill of old physical stock positions; all historical warehouse stock starts **unlocated** until mapped by tasks.
- Local SQLite is for sequential development; PostgreSQL transaction tests are required before production.
- Browser workbench is desktop-friendly and supports keyboard-wedge scanning, but is **not** the intended production handheld interface.
- For rollback of application code, **do not drop new tables after any work has been recorded** without a migration/rehoming plan. Preserve existing stock data and the new task evidence.


## Phase 1.1: Physical bin counts (November 13, 2026)

The additional `bin_cycle_counts` table and `/api/bin-cycle-counts` endpoints provide physical-bin SKU snapshots, owner-authorized posting, variance audit entries and stale/count-conflict safeguards. Apply `migrations/20261113_bin_cycle_counts.sql` **after** the warehouse-execution migration and before deploying this code. Read `docs/BIN_CYCLE_COUNTS.md` for the exact workflow, permissions and remaining blind-count/freeze limitations.
