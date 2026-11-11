# Elveriq — Development Progress

## Latest milestone: Warehouse Cloud web MVP foundation

**Verified in the provided build:** 46 passing tests (29 original Python tests and 17 website/database/security tests). This is a local automated-test result, not evidence of deployment or paying customers.

### Built earlier (preserved)

- Python in-memory simulated inventory availability and reservation.
- Eligibility filtering and stock-based warehouse ranking.
- Geographic Haversine distance function and DFW public reference points.
- 29 original automated tests.
- Git repository history and incremental project documentation.

### Added in this milestone

- Responsive public landing page and read-only fictional Denton warehouse sample.
- Business workspace registration and login with hashed passwords and signed cookies.
- Tenant-scoped SQL database schema using SQLAlchemy (SQLite for local development).
- Warehouse / SKU catalog, receiving, stock movements, stock availability and low-stock alerts.
- Future-dated customer orders, reservations, fulfillment, cancellation and audit history.
- Supplier directory, CSV catalog import and inventory export.
- FastAPI JSON endpoints and example Docker / managed-host deployment configuration.
- 17 new integration tests covering authentication, CSRF, tenant separation, inventory and order flows.

### Not yet delivered

- No actual public website has been deployed by this archive.
- No verified customer integrations, real warehouse onboarding, or subscription billing.
- No production-ready security, employee invitation workflow, or email verification.
- No PostgreSQL migrations, backup policies, or concurrency/load testing.
- No purchase-order workflow, bin scanning, mobile app, or advanced supply chain forecasting yet.

## Product direction

Elveriq is now a **website-first warehouse management and inventory SaaS concept** for independent warehouses and small distributors, beginning with fictional Denton sample data. The plan is to validate real workflows, then build a customer-safe pilot and eventually a mobile client sharing the same backend API. See [ROADMAP.md](ROADMAP.md).

## Engineering note

The original in-memory DFW ranking modules remain separate from the new database-backed tenant inventory system. That is intentional: we are not pretending the old example dictionary is a production stock source.


## Elveriq warehouse purchasing milestone

- Rebranded website and public product documentation to Elveriq.
- Added tenant-scoped purchase orders, line items, receiving and cancellations.
- Partial receipt and an audit ledger are linked to existing inventory.
- Added automated CI and purchase-order regression tests; local target: 56 passing tests.
- Not publicly deployed and not yet production-ready.
