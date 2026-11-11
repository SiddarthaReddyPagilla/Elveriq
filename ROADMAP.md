# Product Roadmap — Website First, Mobile Later

## Current MVP (implemented in this package)

- [x] Public landing page and fictional read-only warehouse sample
- [x] Private business registration and workspace sign-in
- [x] Basic tenant separation and owner/staff role checks
- [x] Multiple warehouse locations, product catalog, supplier directory
- [x] Receive stock and track changes in a movement log
- [x] CSV catalog import and inventory export
- [x] Low-stock dashboard
- [x] Scheduled order reservations, fulfillment and cancellation
- [x] Automated tests across old and new modules
- [x] Container and hosting starter configuration

**Not yet implemented:** production deployment, real merchant onboarding, employee invitations, purchase-order receiving, transfers, scanning, real integrations, and reliable operational billing.

## Phase 2 — A real pilot-ready warehouse workflow

- [ ] Interview at least five warehouse/distributor owners about actual pain points
- [ ] Find one consenting design partner and test with **sanitized sample data**
- [ ] Improve onboarding, CSV field mapping, import preview and reconciliation
- [ ] Employee invitations, role administration and account recovery
- [ ] Incoming purchase orders, supplier shipment receiving and discrepancies
- [ ] Bin / aisle locations and cycle counts
- [ ] Barcode-friendly receiving, pick and pack screens
- [ ] Versioned database migrations, database backups, monitoring, rate limits
- [ ] Browser end-to-end tests, load tests, stronger authorization review

## Phase 3 — Connected operations

- [ ] API keys / OAuth partner integrations for authorized systems
- [ ] Multi-location transfers and replenishment rules
- [ ] Picking lists and fulfillment workflows
- [ ] Demand summaries and reorder suggestions with explainable assumptions
- [ ] Inventory change event/outbox and reliable synchronization jobs
- [ ] Billing, terms, privacy policy, support and tenant onboarding

## Phase 4 — Mobile experience

Develop a mobile-first client, PWA or native mobile app using the **same backend API**. Prioritize warehouse workers' scanner/receiving experience. Build mobile only after the web workflows and product-market validation.

## Commercial hypothesis

Start with independent distributors and warehouse businesses that operate one to three locations and suffer from spreadsheet-heavy stock handling. Test whether the platform reduces stock reconciliation time or order handling errors. Subscription prices and value propositions remain hypotheses until customer interviews and pilot results.
