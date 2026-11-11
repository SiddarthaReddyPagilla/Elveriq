# Elveriq — Product Direction

**Domain owned by project founder:** elveriq.com (not connected to hosting by this code update).

## Who it's for

Independent warehouse owners, distributors and small businesses that currently
manage stock and fulfillment across spreadsheets and disconnected tools.

## Problem to validate

Inventory adjustments, incoming supplier shipments, future customer orders
and stock reservations can become difficult to coordinate across staff.
We should verify this problem through interviews, not assume willingness to pay.

## Website-first product

One private workspace per business, showing products, physical stock, reserved
stock, warehouse locations, suppliers, inbound POs, outbound scheduled orders,
and an audit history. Start with CSV onboarding; add authorized integrations
when there are clear customer requirements. The same JSON backend can later
support a dedicated iOS/Android client.

## MVP success criteria

1. A new warehouse owner can create an account and a product without assistance.
2. They can record an inbound purchase and partially receive stock.
3. They can reserve and fulfill customer orders without overselling.
4. Inventory changes have traceable records.
5. Business A cannot access or modify Business B's records.
6. A fictional sample demonstrates the workflow before the user registers.
7. All workflows can be run locally and checked by automated tests.

## Before commercial launch

Deploy a stable, HTTPS website at the purchased domain, migrate the live
database to managed PostgreSQL with schema migrations, protect private business
data, add account recovery, rate limits, monitoring and backups, validate
regulatory obligations, and recruit one genuine pilot customer.

## Not yet implemented

Actual carrier dispatch, supplier ordering/payment, production-grade identity,
mobile apps, predictive analytics, POS/ERP synchronization, and any live warehouse operations.
