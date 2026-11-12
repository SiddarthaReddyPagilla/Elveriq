# Reliable Warehouse Transfers — Elveriq

This is an actual inventory workflow in Elveriq, not a fabricated portfolio feature.
A staff member with a permitted business role can move unreserved units of one
SKU from one of that business's warehouses to another, with an immutable audit
trail and retry protection.

## API and permission model

Authenticated: `POST /api/transfers`. Existing cookie session + `X-CSRF-Token`
and required `Idempotency-Key` header (8–128 characters, letters/digits/dots/
colons/hyphens/underscores). Body:

```json
{
  "source_warehouse_id": 1,
  "destination_warehouse_id": 2,
  "sku": "WATER-500ML",
  "quantity": 5,
  "note": "Restock second location"
}
```

Status `201` for a new transfer; response `{"id": 123, "quantity": 5,
"replayed": false}`. Same authorized organization, same key and normalized body:
status `200` with original ID and `replayed: true`, no second movement. Same
key and different operation: `409`. Insufficient unreserved source stock:
`409`. Wrong-tenant warehouse or product: `404`. Missing key: `422`.

The existing roles are **organization-wide**. Owners, managers and staff can
move stock between any two warehouses of their organization. There are NO
per-warehouse permission assignments yet. Both warehouses are checked against
the caller's organization, and the active actor must belong to the organization.
Adding location-specific grants is future work.

## Reproduce via the website

1. Start Elveriq and sign in to a business workspace.
2. Create two warehouses, one product SKU, and receive 10 units into warehouse A.
3. Use the **Transfers** section to move 4 units from A to B. The page displays
   the transfer ID. Inventory reads 6 and 4, and audit history shows linked
   `transfer_out` / `transfer_in` records with the **same transfer_id**.
4. To verify replay explicitly, open browser DevTools Console while logged in,
   replace warehouse IDs and SKU below, and run the whole snippet. It uses the
   existing CSRF token in the authenticated page:

```javascript
const body = {source_warehouse_id: 1, destination_warehouse_id: 2,
              sku: 'WATER-500ML', quantity: 1, note: 'Replay example'};
const idempotencyKey = crypto.randomUUID();
const callTransfer = async () => {
  const response = await fetch('/api/transfers', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json',
              'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content,
              'Idempotency-Key': idempotencyKey},
    body: JSON.stringify(body),
  });
  return {status: response.status, data: await response.json()};
};
console.log(await callTransfer()); // 201 / replayed false
console.log(await callTransfer()); // 200 / replayed true, same ID
```

The browser transfer form automatically reuses an in-progress key if a request
fails due to a network issue; it generates a new key when the operator changes
any form data or after a successful response. An actual retry after reloading
the page requires reusing the original key through the API.

## Transaction and concurrency design

The FastAPI handler uses a single SQLAlchemy session and **one commit** after
service success. On any error, it explicitly rolls back. In PostgreSQL:

- A unique index on `(business_id, idempotency_key)` plus
  `INSERT ... ON CONFLICT DO NOTHING` serializes simultaneous retries with
  the same key. The request SHA-256 fingerprint detects conflicting payloads.
- The two `stock_levels` rows are locked with `SELECT ... FOR UPDATE` in
  ascending primary-key order. This avoids opposite-direction transfer deadlocks.
- Source debit is conditional on `on_hand - reserved >= quantity` and the
  destination credit is additive. Both records, the transfer and its two
  structured movement rows share the same **database transaction**.
- On insufficient stock or injected destination failure, the transaction
  is rolled back, including the idempotency claim and all audits.
- PostgreSQL READ COMMITTED isolation is expected and tested. For this app,
  separate SQLite demos cannot prove the row-lock and retry concurrency rules.

## Upgrade an existing database BEFORE deploying new code

**Back up your data first.** For an existing PostgreSQL app, use your existing
migration/release process to run:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261112_reliable_stock_transfers.sql
```

If `DATABASE_URL` uses the SQLAlchemy `postgresql+psycopg://` prefix, replace it
with `postgresql://` for the `psql` command; `psql` cannot parse the driver suffix.
On a brand-new database, SQLAlchemy `create_all` builds the current schema.
The existing project does not yet use Alembic; move to versioned migrations
before production operation.

For an EXISTING local SQLite file only, back it up and run:

```bash
python scripts/upgrade_transfers_sqlite.py dispatchforge_dev.sqlite3
```

This is a one-time additive demo-schema upgrade; rerunning it is safe. Never
use SQLite for business-critical concurrent inventory operations.

## Test commands

Local (SQLite, business behavior):

```bash
python -m pytest -q tests_web/test_transfers.py
python -m pytest -q
```

**Real PostgreSQL with independent concurrent transactions** (must use a
throwaway database, never production):

```bash
export ELVERIQ_TEST_POSTGRES_URL='postgresql+psycopg://elveriq_test:elveriq_test@localhost:5432/elveriq_test'
python -m pytest -q tests_web/test_transfers_postgres.py -rs
```

Example local disposable PostgreSQL using Docker, if installed:

```bash
docker run --rm --name elveriq-transfer-pg -e POSTGRES_USER=elveriq_test \
  -e POSTGRES_PASSWORD=elveriq_test -e POSTGRES_DB=elveriq_test \
  -p 5432:5432 -d postgres:16
# wait for readiness: docker exec elveriq-transfer-pg pg_isready -U elveriq_test
```

GitHub Actions provides a PostgreSQL 16 service and runs the complete test
suite on Python 3.11 and 3.13. If the URL is absent, PostgreSQL tests SKIP;
they do NOT silently substitute SQLite. The tests each create and drop an
isolated temporary PostgreSQL schema.

## Review checklist

- `dispatchforge_app/transfer_service.py`: identity and tenant verification;
  single-key claim; sorted row locks; conditional writes; two linked audits.
- `dispatchforge_app/models.py`: unique key per business and audit `transfer_id`.
- `dispatchforge_app/api.py`: required key and rollback on error.
- `tests_web/test_transfers.py`: success, replay, conflict, unauthorized,
  insufficient, failed destination write, linked audit.
- `tests_web/test_transfers_postgres.py`: two competing transactions, two
  same-key transactions, and rollback using actual PostgreSQL.

### Design tradeoff

An idempotency record is stored on each completed transfer, not in a separate
request table. That is simple and durable, and a failed attempt can be retried
because its transaction rolled back. It also means identical retries remain
recognized while the original transfer record exists; deleting history would
break this guarantee. We must retain transfer records and associated keys.
