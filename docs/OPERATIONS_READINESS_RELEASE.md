# Operations readiness: exceptions, shipment milestones, live metrics

Status: **development branch / staging acceptance required**. These 26 commits build on the 17-commit inbound ASN batch, which itself builds on the previous 10 outbound commits. **Apply packages in order.**

## New operations

- **Case management** (`/api/exceptions`): staff may open cases, operators may acknowledge an assigned case, owner/manager may assign, resolve and reopen. Required resolution reason; comments and state changes create immutable case events. Source IDs are resolved against the signed-in business, never trusted from a browser-supplied tenant ID. Repeated `Idempotency-Key` returns one case; mismatched reuse is rejected.
- **Automatic receiving exceptions**: damaged ASN scans open `inbound_damage`; closing a short ASN opens `inbound_shortage`. Both are part of the original receiving transaction. **Damaged units are excluded from saleable stock, but not tracked in a physical QC bin.**
- **Manual shipping milestones** (`/api/shipping/tracking`): owner/manager can record in-transit, out-for-delivery, delayed, exception or delivered. This is **not carrier-confirmed tracking**, electronic proof of delivery or real-time shipment visibility. Recorded milestones do **not** change stock or order fulfillment. Once delivered, manual milestones are terminal.
- **Manifest export**: `/api/outbound/orders/{id}/manifest.csv` lists scanned, sealed carton contents only; access is tenant-scoped. Spreadsheet formula injection is escaped.
- **Live metrics** (`/api/operations/metrics`): case backlog, overdue cases, arrived ASNs, queued picks, staged units, queued tasks, warehouse stock and shipped orders. Values are computed from tenant-scoped DB records, not estimated or synthetic dashboards.
- **Dashboard**: new authenticated inbound dock, exceptions and shipping tabs. Keyboard-wedge scanner input; explicit retry keys for intake, manual cases and shipping milestones. Forms handle the standard single PO-line flow; the ASN API supports multiple lines.

## Security / data quality

- All operational source references are checked against the authenticated business. Write endpoints require CSRF and role authorization.
- Service mutations and corresponding audit events share one database transaction.
- Cases and manual shipments have per-tenant idempotency controls. No customer data is sent to external carriers by this release.
- The SLA clock is a dashboard-derived flag, **not** an automatic pager/escalation worker. An overdue case remains visible until a user acts.

## Staging rollout

1. Verify the existing transfer, bins, bin cycle count and `20261114_outbound_execution.sql` migration history.
2. Apply `migrations/20261115_inbound_notices.sql`, **then** `migrations/20261116_operations_readiness.sql` on a backed-up staging database. Do not rerun blindly; use a migration-history system in production.
3. Run `python -m pip install -r requirements-dev.txt && python -m pytest -q` with disposable PostgreSQL configured as `ELVERIQ_TEST_POSTGRES_URL`; PostgreSQL tests are skipped without it.
4. Run `node --check dispatchforge_app/static/app.js && node --check dispatchforge_app/static/advanced_ops.js`.
5. Exercise real scan devices, staff permissions, multi-user conflicts, representative ASNs, short/damaged receipts, sealed cartons and delivery reporting in staging.
6. Check API error logs, health endpoints, reconciliation, audit data, restore-from-backup and staging rollback. Use a PR and successful GitHub CI before merging into main.

## Explicit exclusions before public launch

No supplier EDI or external ASN ingestion; no QC bin inventory, lot or serial traceability, batch expiry or quarantine release; no carrier label purchase, shipment API integration or tracking webhook; no physical proof-of-delivery artifact; no automated SLA dispatch, asynchronous outbound webhooks, scale tests, or real warehouse pilot. These remain backlog gates in `docs/ELVERIQ_MASTER_BUILD_PLAN.md`.
