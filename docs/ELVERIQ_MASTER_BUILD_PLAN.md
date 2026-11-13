# Elveriq — Master Development and Delivery Plan

**Date:** 2026-11-12 (research baseline); Phase 1 delivery build prepared from the uploaded `Elveriq-main.zip`
**Status:** Living engineering guide. **Source of truth:** `docs/research/Elveriq_Enterprise_WMS_Research_2026.md` and the 300-row `docs/research/Elveriq_Competitor_Feature_Register_2026.csv`.

> **Operating principle:** Never replace inventory correctness with interface polish. Add real-world warehouse workflows only when physical quantities, customer reservations, worker execution, tenant isolation, auditability and exception handling can all be validated together.

## 1. The goal

Elveriq will become a configurable warehouse-management and execution platform for distribution centers, wholesalers, e-commerce fulfillment, and third-party logistics (3PL) operations. The long-term benchmark is the functional breadth found in SAP EWM, Manhattan Active WM, Blue Yonder, Infor/Infios, Oracle, Deposco, Extensiv, Odoo, and other platforms discussed in the research. **We are not claiming feature-for-feature parity today**; capability names, workflows, pricing, edition limitations and vendor integrations change.

Use one durable feature register for all future work: **EV-001 through EV-300**. Each ticket should contain: feature ID, business outcome, warehouse persona, source evidence, prerequisites, schema changes, state transitions, API contract, UI paths, failure behavior, permissions, observability, test scenarios, migration, and definition of done. Do not mark a feature “built” merely because a screen exists.

### What is already present in the uploaded baseline

Business-scoped accounts; roles/invitations; warehouses and products; warehouse-level stock ledger; receipts and purchases; reservations and customer orders; partial receiving; stock transfers; cycle-count and returns foundations; replenishment suggestions; CSV picking lists; basic operations dashboard and warehouse activity. See `README.md` and `PROGRESS.md` for existing behavior; the research categorization is a source inspection, not a live production certification.

### Phase 1 delivered in this code update

1. **Physical bin registry** per warehouse: unique scan code, zone, aisle, rack, shelf, optional capacity, tenant-scoped APIs.
2. **Bin stock placement**: confirmed quantity, quantity committed to pending moves, available bin stock, reconciled unlocated pool.
3. **Transactional warehouse tasks**: `putaway`, `move`, `unlocate` (bin → unlocated/staging), priority, optional assignee, queue/claim/start/verify/cancel.
4. **Scan verification**: matching SKU, source bin when applicable, destination bin (or the explicit `UNLOCATED` token); rejected and accepted scan events; idempotent completion and creation.
5. **Compatibility guards**: older stock reductions are blocked if they would undercut placed stock or promised putaway. This applies to manual stock adjustments, legacy order fulfillment, transfer debits and cycle count posting.
6. **Role-based workbench**: bin directory, placement reconciliation, work queue, scan station and operator actions in the existing dashboard.
7. **Additive PostgreSQL migration and tests.** SQLite supports local demonstrations. PostgreSQL row locks and production behavior must be proven in CI/pilot before release.

**Critical boundary:** Warehouse-level `StockLevel` remains the accounting authority, and `BinStock` is a known physical subset. Existing stock receipts and fulfillment do not create or consume warehouse tasks automatically. `unlocate` is a staging bridge, **not yet order-linked picking**. Do not describe this increment as a complete WMS, slotting engine, wave picker, shipping engine or true lot/HU ledger. See `docs/WAREHOUSE_EXECUTION.md`.

## 2. Dependency-ordered master phases

The phase names describe capability tracks, not a fixed calendar. Complete each release gate and pilot before expanding to the next track. Cross-cutting reliability, security, auditing and migration work continues **during every phase**.

| Phase | Outcome | Research capability areas | Hard definition of done |
|---|---|---|---|
| **0 — Transaction safety** | Trustworthy operations | SaaS security, tenancy, migrations, stock ledger, reporting | No negative, duplicate, cross-tenant or unexplained balances under concurrent writes; backups and restore verified |
| **1 — Physical execution core** | Know where goods are and which worker moved them | EV-014/015/019/021 and task orchestration (see register) | Every confirmed putaway/relocation has SKU, bin, operator, quantity, state and event trail; totals reconcile |
| **2 — Guided inbound and outbound** | Workers can follow/verify assigned work from dock to dispatch | ASN, inbound, putaway, pick, replenishment, inventory status | Received → inspected → put away → allocated → picked → packed → shipped trace is repeatable end to end |
| **3 — Packaging & carrier shipping** | Real cartons, pallets, labels, shipping confirmations | Handling units, cartons, parcels, carriers, dock staging | Unique physical package ID and contents; shipping label/tracking and loaded goods issue reconcile |
| **4 — Advanced inventory & QA** | Manage constrained stock correctly | Lot/serial, expiry, FIFO/FEFO, quality, quarantine, counts | Allocation never uses blocked/expired/incompatible stock; lot genealogy is queryable |
| **5 — Fulfillment and labor intelligence** | High-throughput directed operations | Waves, clusters, routes, staffing, SLAs, exception queues, real-time KPIs | Task assignment safe under concurrent workers; performance and exception metrics trace to events |
| **6 — 3PL commercial platform** | Multi-client fulfillment and billing | Inventory ownership, customer portal, contracts, activity billing | Each stored/picked/shipped unit bills correct client exactly once; owners can reconcile invoices |
| **7 — Enterprise ecosystem** | Interoperability and automation | ERP, EDI, e-commerce, WCS/WES, robotics, yard, dock, transportation | Every external event is authenticated, idempotent, retry-safe, observable and replayable |
| **8 — Optimization, AI & scale** | Explainable, measured improvements | Slotting, labor forecasts, orchestration, digital twin, AI | Model recommendations tested against ground truth, human overridable and never silently mutating stock |

## 3. The next critical development sequence

### Gate 0.1 — Protect the current product (before merging Phase 1)

- [ ] Create a branch from the team's actual `origin/main`; check it matches the uploaded source snapshot before applying patches.
- [ ] Capture a staging database backup and verify restoration to a disposable environment.
- [ ] Run existing tests, product-specific API smoke tests, GitHub Actions and a PostgreSQL integration pass.
- [ ] Review and apply the new additive migration before new application code is deployed.
- [ ] Record deployment/rollback procedures and choose an initial pilot warehouse.
- [ ] Confirm real production secrets, HTTPS, session security, CSRF and business-level permissions.

### Gate 1.1 — Bin and warehouse address model (implemented foundation, pilot pending)

Define warehouse zones / bins, uniqueness within a warehouse, scannable codes and inactive/blocked state policy. Support easy creation for managers, distinguish physically assigned and unlocated stock, expose a reconciliation report. Test cross-warehouse and cross-tenant misuse. **Still needed:** editable hierarchy, bin block/unblock workflow, per-warehouse access grants, consistent capacity dimensions (volume/weight/units), physical bin label printing, bin counting and operational location status.

### Gate 1.2 — Task lifecycle and physical confirmation (implemented foundation, pilot pending)

Build tasks with type, quantity, source/destination, worker ownership, status and audit events. Idempotency keys guard retries; scans must match SKU and appropriate bins. Test duplicate submission, repeated confirmation, wrong scan, cancellation and concurrent allocation. **Still needed:** employee handheld/PWA interface, offline-safety design, mobile device permission model, scan hardware certification, task SLA/exception codes, reorderable queues and richer supervisor actions.

### Gate 1.3 — Single authoritative inventory posting (next critical architecture upgrade)

Current phase preserves compatibility by treating bin placement as a physical subset of warehouse-level stock. This is correct within the shipped endpoints, but is not yet the final execution model. **Next:** create one canonical posting service/state machine for receipts, stock status, location movements, reservations, picks, HU moves and dispatch. Migrate legacy routes through that service and progressively replace the unlocated bridge. Do not develop wave/lot/serial systems atop two independent ledgers. Use immutable event records, one-transaction state updates, idempotency and reconciliation tests.

### Gate 2.1 — Inbound and putaway automation

Create advance shipment notice and inbound delivery objects; handle planned/unplanned arrivals; scan UPC/GTIN and purchase quantities; record damage/shortage/overage; add hold/release for QC; generate putaway proposals by space/stock rules; direct and verify work; record dock labor and receiving accuracy. Test mismatched SKUs, partial receipts, unknown goods, quarantined quantities, timeouts and damaged cargo.

### Gate 2.2 — Order-linked allocation, picking and packing

Represent allocation by **specific eligible bin/lot/HU** rather than only SKU+warehouse. Create reserved order work, select pick faces and employee queues, scan source and quantity, support short pick with supervisor resolution, move picked stock to totes/HUs, pack into cartons, verify labels, print manifests and dispatch by dock/driver. Precisely define when on-hand and reserved accounting balances change.

### Gate 2.3 — Exceptions and operational monitoring

Track every blocked task/short pick/quantity mismatch, exception code, operator, remediation owner, SLA and closure. Dashboard cards must drill into actionable source records, never fabricated metrics. Measure receiving-to-putaway time, pick rate, order accuracy, pending work, aged inventory and physical-vs-system discrepancies.

## 4. Implementation rules that must remain true

1. **Tenant isolation:** Every externally supplied warehouse, bin, user, SKU, customer, order and task identifier is checked against the authenticated `business_id`. Do not trust a role or tenant ID from browser payloads.
2. **Inventory integrity:** `0 ≤ reserved ≤ on_hand`. Placed quantity must never exceed on-hand. Committed bin transfers must never exceed available quantity in a bin. Open putaway quantities must fit currently unlocated stock; a real transfer must not debit it out from under a task.
3. **Transaction boundaries:** Task state and stock movements must commit atomically. On a rejected write, the database should remain unchanged apart from explicitly saved failure-audit records.
4. **Concurrency:** PostgreSQL is the production transaction authority. Serialize task creation and physical placement with the warehouse/product stock row lock. Recheck any data read before a lock; use conditional SQL updates rather than Python-only if-statements for stock debits.
5. **Idempotency:** Client actions that may be retried carry a stable key. Identical retry returns the existing result; the same key with different details is rejected.
6. **Auditability:** Every accepted state transition records task, actor and UTC time. Rejected scans can be recorded without changing stock. Invented metrics are forbidden.
7. **Access control:** Owners/managers register bins and release/assign/cancel work; staff can claim/start/verify their own work. Disabled staff do not execute work.
8. **Migration discipline:** An additive migration precedes code deployment. Backfills have deterministic counts, data reconciliation and an explicit rollback path.
9. **Reliability:** CI must test browser/API permissions, accounting invariants, concurrency, idempotency, staging migrations and failures under partial writes.
10. **Source of truth:** Every new feature links to a row in the feature register and a test/definition of done. Do not imply unsupported enterprise features are shipped.

## 5. Proposed ultimate architecture (north star, NOT all implemented)

**Control plane:** business/tenancy, plans, identity, permissions, connectors, customer organizations.
**Master data:** warehouse topology, products, units, lot/serial, customer ownership and capacity.
**Inventory accounting:** canonical posting ledger, reservations, stock condition and traceability.
**Execution:** work requests, task assignment/claim/start/confirm, scans, exceptions, labor resources, bins, HUs, picks and packs.
**Fulfillment:** purchase/inbound delivery, customer allocation, wave/waveless planning, packing, shipping/tracking, returns.
**3PL:** client portals, per-client inventory, rate cards, billable work events, invoices and reports.
**Integration:** authenticated APIs, webhooks, durable outbox, EDI, ERP, carriers, marketplaces and material-handling devices.
**Observability:** operational audit, event stream, exception dashboards, reconciliation, trace IDs, uptime/performance, backup/restore.

**Core planned entities** (many not yet built): `WarehouseLocation`, `InventoryBalance`, `StockPosting`, `InventoryOwner`, `Lot`, `Serial`, `HandlingUnit`, `ReservationAllocation`, `WarehouseTask`, `TaskEvent`, `ScanEvent`, `OrderWave`, `PackUnit`, `Shipment`, `CarrierLabel`, `DockAppointment`, `BillableEvent`, `ClientContract`, `IntegrationDelivery`, `OutboxEvent`. See the research's architecture sections and individual feature specifications for detailed acceptance tests.

## 6. Milestone acceptance test matrix

| Test family | Required behavior before pilot |
|---|---|
| Tenant boundary | Another business cannot access or affect bin, task, SKU, staff assignment or task history |
| User roles | Owner/manager can release work; staff cannot administer bins/work queues; disabled staff cannot act |
| Quantity and location | Warehouse on-hand = sum confirmed placed + unlocated; no double placement; no negative quantity |
| Concurrency | Two workers cannot claim a task or allocate the same source units twice under PostgreSQL |
| Replay safety | Same creation/confirmation repeated produces one task and one physical movement |
| Wrong scan | Incorrect SKU/source/destination is rejected, logged, and does not adjust inventory |
| Rollback | Invalid target/capacity/stock or simulated DB failure leaves totals and assignments unchanged |
| Legacy compatibility | Receipts, partial PO, transfers, counts, returns and reserved order fulfillment still work |
| Staging rollout | Additive migration, backup restore and clean staging deployment verified |
| Functional pilot | At least one real warehouse receives, places, relocates, stages and fulfills stock with correct reconciliation |

**Current results on this provided archive:** original automated suite and new SQLite API tests pass locally. PostgreSQL-only integration tests are skipped without `ELVERIQ_TEST_POSTGRES_URL`; real PostgreSQL CI/pilot results remain a release gate, not an assumed success.

## 7. Planned development rhythm

For every feature: **research evidence → feature ticket → data model + API → invariant/concurrency tests → worker workflow → manager UI → audit/metrics → migration → staging → pilot → done.** Ship small, reviewable commits, keep `main` stable and use a feature branch/PR with CI. Have one owner maintain the feature register: **Proposed → Specified → In progress → In review → Staging → Pilot → Production**, with explicit evidence per transition.

### What to build immediately after this package

1. Verify the Phase 1 migration against a real staging PostgreSQL database and audit all legacy accounting reducers again.
2. Add end-to-end order-linked pick tasks and allocation binding to prevent a bin pull being mistaken for proof that a specific order was picked.
3. Build a mobile-first scanning interface with authentication and operator feedback; the current scan station requires text entry or keyboard-wedge scans.
4. Add quality holds, damaged stock, and customer-specific ownership before advanced picking or 3PL billing.
5. Build HU/carton/shipment data models with fully defined posting state transitions.
6. Introduce versioned migration tooling, robust operations monitoring and recovery playbooks before onboarding paying warehouses.

## 8. Working with this paper for the long term

- **Master paper:** `docs/research/Elveriq_Enterprise_WMS_Research_2026.md` (printable PDF and editable DOCX included).
- **Master checklist:** `docs/research/Elveriq_Competitor_Feature_Register_2026.csv`; identifiers EV-001 through EV-300 remain stable.
- **Primary source register:** `docs/research/Elveriq_Research_Sources_2026.csv`; review edition/availability when implementing vendor-inspired capabilities.
- **Release playbook:** `docs/TODAY_RELEASE_CHECKLIST.md`.
- **Actual Phase 1 workflows and limitations:** `docs/WAREHOUSE_EXECUTION.md`.

Treat the research as a **versioned source file in Git**, not an unchangeable memory assertion. Amend it when new competitors or feature evidence emerge, and date every change. This keeps project context available in future sessions even when chat memory is disabled.
