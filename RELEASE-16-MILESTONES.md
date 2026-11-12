# Elveriq Warehouse Cloud — 16 Engineering Milestones

This incremental release builds on the Elveriq purchasing update (the **previous four-commit pack**).
It is an **educational SaaS prototype**, not a production-grade WMS.

## Implemented in this pack

1. Atomic, tenant-scoped inter-warehouse transfers and two movement records.
2. Transfer REST API with inventory integrity and isolation tests.
3. Read-only pick lists for customer orders.
4. Safe, downloadable pick-list CSVs.
5. Replenishment planning that considers open supplier purchase orders.
6. Replenishment CSV report with spreadsheet-formula mitigation.
7. Physical stock count database records.
8. Conditional cycle count reconciliation and stale-snapshot rejection.
9. Cycle count API with reservation, tenancy, and audit tests.
10. Customer return receipts, bounds checking, and stock audit entries.
11. Return receipt API with double-restock and ownership tests.
12. Expiring, single-use staff invitations and roles.
13. Staff API, account deactivation, login protection, and tests.
14. Filtered, paginated stock movement audit API.
15. Browser workflows for transfers, counts, returns, replenishment, and staff invitations.
16. Seven-day operations planner, tests, and release notes.

## Test commands

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check dispatchforge_app/static/app.js
node --check dispatchforge_app/static/join.js
```

## Limits / production prerequisites

- The package introduces **new database tables**. `Base.metadata.create_all` adds
  tables in a local test database, but does **not** replace versioned migrations.
  Use Alembic migrations, tested backups and a rollback procedure before production.
- Sample data is fictional; no real suppliers or carriers are integrated.
- Invites are displayed once for secure owner sharing; **email delivery is not implemented**.
- Returns endpoint represents **confirmed physical intake of resellable goods**;
  do not use it to initiate customer refunds or authorize unsafe restocking.
- Replenishment is a configurable threshold heuristic, not an ML forecast or
  a purchasing automation; it cannot know real physical stock without staff scans.
- Test with concurrent PostgreSQL sessions before relying on critical warehouse
  stock transactions. SQLite is for local demonstration, not real multi-user use.
- Add formal authorization reviews, rate limits, session revocation, password
  recovery, structured logging, monitoring, and privacy controls before a public
  paid SaaS launch. Deployment and real-customer validation remain unfinished.

## Next milestones

Bin-level inventory and scanning; picking/packing states; database migrations;
real role invites by email; payment subscriptions; security review; pilot with
one independent warehouse and verified operational metrics.
