# Elveriq Phase 1.1 — Bin/SKU Cycle Counts and Reconciliation

**Release candidate:** 2026-11-13 · **Status:** Implemented locally; PostgreSQL staging and production rollout NOT validated.

This extends Phase 1 warehouse physical placement with a supervised process for counting **one SKU in one bin**. It is deliberately separate from the existing *warehouse-wide* `/api/cycle-counts` workflow. This is **not** a full blind-count campaign, barcode-scanning implementation, stock freeze system or configurable variance approval threshold.

## Operator workflow

1. Receive product and perform scan-verified putaway so that some warehouse stock is assigned to a bin (or open a count against an empty registered bin when discovering unexpected physical inventory).
2. From **Cycle counts → Count an individual storage bin**, choose warehouse, bin, product and reason. All active moves for the counted bin/SKU must be completed/canceled first.
3. Elveriq stores a snapshot of the bin's placed quantity, allocated quantity, warehouse-level on-hand and the latest movement/task-event IDs. It prevents a second open count for the same bin/SKU.
4. Physically tally the product in that bin. A workspace **owner** chooses **Reconcile**, enters the observed nonnegative quantity, reviews the variance, and confirms. Other active workspace roles may start a count but cannot post or cancel it.
5. The posting transaction atomically adjusts `BinStock.on_hand` and `StockLevel.on_hand` by the exact same difference, adds a `StockMovement` with `kind=bin_cycle_count`, and closes the count with poster and timestamp. The unlocated balance stays unchanged. A zero-variance count creates an audit entry without changing stock.
6. If stock or tasks changed after the snapshot (even if quantities returned to their previous values), the count stays **open** and posting returns HTTP 409. An owner must cancel and start a fresh count. This protects against stale reports and double posts.

## Safeguards and limitations

- Tenant-owned business, warehouse, bin and SKU are validated for every operation; CSRF is required on writes. Public demo access is read-only.
- Posting refuses a bin whose movement tasks are still active, changes that would undercut reserved stock, overflow a bin's coarse *unit* capacity, or create a negative total. Active putaway reservations at the warehouse level remain protected.
- A stock row is locked before the physical-bin row, consistent with warehouse task writes. Conditional SQL updates stop double posting. SQLite is only suitable for local sequential development; production concurrency requires PostgreSQL.
- Historic inventory remains **unlocated** until explicitly placed. A positive variance at an empty bin introduces newly discovered stock into BOTH the physical bin and warehouse aggregate; it is not a reclassification of existing unlocated stock. For reclassification use putaway, not a count.
- There is no scanner-based proof of physical counting, bin quarantine while a count is open, independent counter/reviewer separation enforcement, photo attachment, blind counting, audit threshold, cost valuation or multi-SKU count sheet yet.
- Event watermarks are intentionally conservative: any intervening SKU movement or task event in the warehouse invalidates the count, even if it concerns another bin of the same SKU. This favors inventory integrity over throughput until a versioned inventory posting service exists.
- `bin_cycle_counts` is a separate auditable snapshot register. Never use it as a substitute for the central movement ledger.

## API

| Method | Endpoint | Role | Function |
|---|---|---|---|
| GET | `/api/bin-cycle-counts` | Signed in or demo read-only | Last 200 counts in tenant |
| POST | `/api/bin-cycle-counts` | Owner, manager, staff | `{warehouse_id, bin_id, sku, note}`; creates open snapshot |
| POST | `/api/bin-cycle-counts/{id}/post` | Owner only | `{counted_on_hand}`; guarded variance reconciliation |
| POST | `/api/bin-cycle-counts/{id}/cancel` | Owner only | Cancel an open count |

## Schema and deployment

The new migration `migrations/20261113_bin_cycle_counts.sql` adds one table and two indices; it **depends on** `migrations/20261113_warehouse_execution.sql`. Back up and test migration restore before production. Run migration against **staging** in the following order:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_warehouse_execution.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_bin_cycle_counts.sql
```

Do not point test environment variables at production. Run `ELVERIQ_TEST_POSTGRES_URL=... python -m pytest -q` against disposable PostgreSQL. Check with a real owner, manager and staff account, two tenants, competing warehouse tasks, full bin, and an open customer order before deploying.

## Competitor research traceability

- `EV-097` Aggregate cycle counts: previously implemented, unchanged.
- `EV-098` **Blind** bin cycle count: still **not** implemented. The expected quantity is intentionally visible to the owner in the Phase 1.1 workbench; blind counting remains future work.
- `EV-102` Count variance approvals: **partially implemented** by owner-only posting, but requires configurable thresholds, reason codes and reviewer independence to be complete.
- `EV-096` Inventory freeze during count: still **not** implemented. The count detects and rejects interfering movements instead of freezing the location.

Keep the original vendor research paper and 300-item register as the **historical competitor baseline**. Track delivery progress separately in `docs/FEATURE_IMPLEMENTATION_STATUS_2026-11-13.md`.
