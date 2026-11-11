# Elveriq Warehouse Cloud

**A website-first warehouse operations SaaS prototype for independent distributors and small warehouses.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)](https://fastapi.tiangolo.com/) [![Status](https://img.shields.io/badge/status-prototype-CC8736)](#prototype--security-notice)

Elveriq started as a Python inventory and warehouse-ranking exercise. This repository now also includes a responsive web dashboard and a database-backed warehouse workflow. The original learning modules and their tests remain in place.

> **Product status:** Prototype and fictional demo data. Not an operating logistics business and **not yet safe for business-critical production inventory**. There is no live deployment URL included in this archive.

## What you can use today

- **Public sample:** a read-only dashboard with fictional Denton distribution data at `/demo`.
- **Private workspace:** register a business, then sign in using the workspace ID, email and password.
- **Warehouse locations and products:** create locations, add SKUs, and import a product catalog from CSV.
- **Persistent stock:** receive units, inspect available vs. reserved inventory, and download a CSV report.
- **Scheduled customer orders:** reserve products for a future date, fulfill or cancel orders, and automatically update stock.
- **Stock ledger:** audit when stock enters, is reserved, ships, or is released.
- **Supplier directory, low-stock alerts, and overview metrics.**

The frontend is HTML/CSS/JavaScript and can be adapted into a mobile app later using the same backend APIs.

## Run locally (Mac, Linux or Windows with a terminal)

From the **repository root**, not the nested old copy:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn dispatchforge_app.web:app --reload
```

On Windows, activate with `.venv\Scripts\activate` instead. Open:

- Website: http://127.0.0.1:8000
- Read-only example: http://127.0.0.1:8000/demo
- API docs: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/api/health

A development-only SQLite database named `dispatchforge_dev.sqlite3` will be created automatically. It is ignored by Git. The `sample-workspace` dataset is fictional and cannot be modified through public demo endpoints.

To try the interactive workflows: select **Create workspace**, sign up, and **copy your workspace ID** from the left sidebar—you will need it to sign in again. Create a product, receive stock into **Main Warehouse**, schedule an order, and fulfill or cancel it.

### Test everything

```bash
python -m pytest -q
```

Expected at the time of packaging: **46 passing tests** (29 original tests + 17 web/inventory/security tests).

### CSV product import

In your private warehouse dashboard, open **Inventory** → **Import CSV**. Download the sample template or use:

```csv
sku,name,price_cents,reorder_point,unit
SKU-100,Shipping Box,249,20,each
SKU-101,Packaging Tape,499,10,roll
```

Existing SKU rows are skipped. Import creates catalog records, **not stock on hand**. Use **Receive stock** to record the physical goods. The import is limited to 1 MB / 1,000 rows.

## Technology

| Layer | Used now | Later |
| --- | --- | --- |
| Frontend | HTML, CSS, vanilla JavaScript | Mobile client sharing APIs |
| API | Python, FastAPI, Pydantic | Integration APIs and webhooks |
| Data | SQLAlchemy, SQLite in development | PostgreSQL + migrations |
| Authentication | Session cookies, password hashing, CSRF checks | Email verification, invitations, reset, rate limits |
| Tests | pytest, legacy unittest tests | Concurrency, load, security, browser E2E |
| Hosting | Configured for a host with persistent PostgreSQL | Production hardening / monitoring |

## Repository map

```text
dispatchforge_app/
  web.py              Website routes, sessions, landing & sign-in
  api.py              Tenant-scoped JSON endpoints
  database.py         SQLAlchemy database configuration
  models.py           Businesses, warehouses, products, orders, stock ledger
  inventory_service.py  Inventory operations
  order_service.py    Scheduled reservations and fulfillment
  auth.py             Passwords, workspace scope, CSRF
  demo.py             Clearly fictional read-only sample dataset
  settings.py         Local and production environment configuration
  templates/          HTML pages
  static/             CSS, JavaScript, sample CSV
tests_web/              Web and database integration tests
inventory.py ...       Original Elveriq learning modules, unchanged
ARCHITECTURE.md         Technical choices and invariants
SECURITY.md             Production-readiness gaps
ROADMAP.md              Product scope and future milestones
PROGRESS.md             Completed vs. planned work
render.yaml             Example deployment blueprint
Dockerfile              Optional container build
```

## Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** before publishing. Production mode explicitly requires a strong `APP_SECRET` and a persistent PostgreSQL `DATABASE_URL`; it will not silently use ephemeral local SQLite. A Render example and Dockerfile are included but **deployment is not performed by this archive**.

## Original modules

The earlier `inventory.py`, `warehouse_selection.py`, `warehouse_ranking.py`, `distance.py`, and geographic reference module are preserved for comparison and incremental learning. These legacy modules use *simulated* DFW stock. The new SaaS application keeps its business data in its separate database and does **not** pretend to share operational stock with those example dictionaries.

## Prototype / security notice

No email verification, password reset, invite flow, account recovery, data retention policy, database migrations, backups, or rate limiting yet. The frontend has only a one-line order form (the API supports multiple items). Do not invite real warehouses to depend on this service until these areas are addressed and the application receives a professional security review.

Built as an independent educational project, with the goal of validating real warehouse workflows before pursuing a commercial product.
