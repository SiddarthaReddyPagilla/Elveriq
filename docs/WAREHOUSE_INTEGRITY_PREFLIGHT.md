# Warehouse integrity preflight — November 22, 2026

The `/api/reports/integrity-audit` endpoint and Warehouse Intelligence panel
perform eleven **read-only** checks against the current tenant's database.
Use `?warehouse_id=<tenant-owned-id>` to narrow the evaluation. Unknown or
other-tenant warehouse IDs return HTTP 404. Authentication is mandatory.

## Checks

- Warehouse stock: no negative hand or reserved, no reserved excess.
- Stock references: product and warehouse ownership agree with tenant.
- Bin stock: no negative stock/allocated or overallocation.
- Bin membership: product and physical bin belong to expected warehouse.
- Placed inventory: physical placed subset never exceeds accounting on-hand.
- Bin capacity: alert for configured active bins exceeding unit limits.
- Inbound disposition: accepted + damaged never exceeds expected units.
- Outbound pick: positive picks, associated carton tenant consistency.
- Carton contents: quantity, order, warehouse and tenant match the pick.
- Warehouse task topology: valid quantities and source/destination shape.
- Incident state: resolved timestamps agree with current state.

Each rule returns the exact matching row count and at most 25 sample IDs.
All queries are tenant scoped. The service makes no inventory or audit writes.

## Operational usage

1. Confirm the staging migration inventory is current and run the full tests.
2. Run the preflight in a disposable warehouse with fixture data.
3. Review all `critical` findings before deployment; confirm any `warning`
   findings against the physical warehouse and current operations.
4. Recheck after correction using the existing audited inventory services;
   **never edit ledger balances directly to silence a preflight warning**.

## Boundaries

A green scan cannot establish physical counts, complete migration readiness,
cross-request isolation under concurrent PostgreSQL writers, certificate
trust, or real-carrier delivery. Deploy only after the existing PostgreSQL
integration gates, HTTPS checks, backup/restore and warehouse pilot.
