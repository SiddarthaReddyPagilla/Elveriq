# Elveriq Architecture (MVP)

## Product boundaries

Customer: a small distributor / independent warehouse operator. The product stores their warehouse data and provides workflows; Elveriq does not own the customer's inventory, sell goods, or dispatch real drones.

## System map

```text
Browser (HTML/CSS/JS)
    │
    ├─ public landing + fictional read-only /demo
    └─ authenticated private /app
                │
                ▼
         FastAPI /api/*
                │
       Authentication + CSRF
                │
       Business / tenant checks
                │
        Warehouse services
          ├─ inventory_service (receive, adjust, catalog, audit)
          └─ order_service (reserve, cancel, fulfill)
                │
          SQLAlchemy ORM
                │
      SQLite locally / PostgreSQL in production
```

## Data entities

- `Business`: tenant/workspace; each business owns its data.
- `User`: email, password hash, role, business association. Registration initially creates an owner. Staff invitation is not yet implemented.
- `Warehouse`: each business can own multiple named locations.
- `Product`: SKU, name, unit, price in cents, reorder point; unique SKU within a business.
- `StockLevel`: per-product per-warehouse `on_hand` and `reserved` counts.
- `StockMovement`: append-only application ledger of inventory adjustments and reservations.
- `Supplier`: simple business-specific directory.
- `CustomerOrder` / `OrderLine`: scheduled customer fulfillment and per-SKU quantities.

## Inventory invariant

```text
0 <= reserved <= on_hand
available = on_hand - reserved
```

**Receiving:** add `on_hand` and append a receipt movement.

**Reserve:** if enough units are available, increment `reserved` and append a reservation movement; `on_hand` does not change.

**Fulfill:** decrement **both** `reserved` and `on_hand` and append a fulfillment movement.

**Cancel:** decrement `reserved` only and append a cancellation movement.

Conditional SQL `UPDATE` statements protect each stock row from being reserved beyond its availability. Multi-SKU order changes and ledger writes are committed together; if a step fails, the request transaction rolls back. This is a foundation, not a substitute for load testing and database-level concurrency testing.

## Data isolation

All business-owned objects carry `business_id`. Each API query and stock/order operation filters using the authenticated user's business ID. The publicly visible sample business is explicitly read-only. Tests prove one tenant cannot read or modify another tenant's product, stock, warehouse, or order records through the tested routes.

## Future integration approach

A warehouse may already use QuickBooks, Shopify, a POS, or spreadsheets. Only connect through supported authorized APIs, file imports, or customer-owned exports. Record an `external_id`, source system, sync timestamps, and resolution rules before attempting two-way stock synchronization. Define one authoritative system for each inventory quantity to prevent conflicting updates.

## Migration plan

1. Keep SQLite for local demos and tests.
2. Use persistent PostgreSQL in hosted production environments.
3. Introduce Alembic versioned migrations before evolving schemas for actual customers.
4. Add reliable backups/restores, background jobs, event/outbox processing, and monitoring.

The original `inventory.py` and ranking/distance modules remain as **separate teaching/simulation modules**. This new SaaS persistence layer does not overwrite them; mapping the two systems is future work.


## Inbound purchasing domain

`PurchaseOrder` belongs to a tenant, warehouse and supplier; each `PurchaseOrderLine`
references a product and tracks ordered versus received units. Receipt operations
atomically update the line's received quantity and the stock ledger in a single
database transaction. The list endpoint is tenant-scoped and the read-only demo
uses fictional orders. This MVP does not send purchase orders to suppliers or
maintain invoice/payment state.
