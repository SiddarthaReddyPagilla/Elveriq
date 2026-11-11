# Elveriq — Supplier Purchasing & Receiving

## Why it matters

Independent warehouse operators need to know what they ordered from suppliers,
what has physically arrived, and what is still outstanding. This workflow is
implemented as local records: **Elveriq does not actually purchase goods from suppliers**.

## Use the website

1. Register a private business workspace and sign in.
2. Open **Suppliers** and create an inbound vendor.
3. Open **Inventory** and add a product SKU and destination warehouse.
4. Open **Purchasing & receiving**; create a purchase reference for the supplier,
   destination warehouse, SKU, quantity and optional expected date.
5. When boxes physically arrive, click **Receive**, enter the arrived quantity.
6. Review the updated **Inventory**, **Stock movements** and outstanding PO amount.
7. Repeat until the order is fully received, or cancel outstanding quantities.

The website currently handles one SKU when creating a new PO. The REST API
supports one to 100 different SKU lines. Each line is received independently.

## Authenticated REST API

- `GET /api/purchase-orders`: list the current tenant's POs and line quantities.
- `POST /api/purchase-orders`: create a PO. Example JSON:

```json
{
  "reference": "PO-1001",
  "supplier_id": 1,
  "warehouse_id": 1,
  "expected_date": "2026-12-20",
  "items": [{"sku": "WIDGET-01", "quantity": 24}]
}
```

- `POST /api/purchase-orders/{order_id}/receive` with
  `{"line_id": 1, "quantity": 10}`: record receipt and stock movement.
- `POST /api/purchase-orders/{order_id}/cancel`: cancel any unreceived portion.

Mutating endpoints require a signed-in workspace session and CSRF token.
Use `/docs` locally to explore the API. IDs are examples, not live records.

## Safety and current limits

- **Simulation/prototype**, not an integrated procurement/payment system.
- Business records are tenant-scoped; demo records cannot be edited.
- Receipt tracking uses conditional updates; the database transaction also
  records an append-only stock movement. Repeated receipt after a PO closes is rejected.
- The system does not inspect physical goods; employees must confirm receipt.
- No external supplier API, invoicing, approval routing or reconciliation yet.
- Before using real warehouse data: PostgreSQL migrations, reliability/load testing,
  tenant isolation review, authentication hardening, backup/restore drills,
  observability and operator training are required.
