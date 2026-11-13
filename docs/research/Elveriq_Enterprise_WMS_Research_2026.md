---
title: "ELVERIQ | Enterprise Warehouse Management Research & Build Reference"
subtitle: "Cross-platform competitive feature atlas, 300-capability specification, target architecture, delivery roadmap and validation standards"
author: "Product and engineering research dossier"
date: "12 November 2026 | Version 1.0"
lang: en-US
---

# Reference map

This dossier is organized for research review, engineering design and weekly backlog planning. Use the headings in Word navigation or the section titles below.

- **Executive research conclusion** — strategic findings and the gap between transaction recording and physical execution.
- **1. Scope, method, and evidence rules** — how vendor evidence and Elveriq status are classified.
- **2. Competitive landscape** — 17 vendor profiles and a cross-market pattern table.
- **3. Elveriq repository audit** — what the supplied codebase does and does not establish.
- **4. Proposed product model** — architecture, entities, state machines and transaction invariants.
- **5. Master capability register** — 300 numbered feature requirements with testable acceptance criteria across 22 operational areas.
- **6-8. Process blueprints, interfaces and roadmap** — actual warehouse flows, personas and phased outcomes.
- **9-10. Quality and API contracts** — concurrency tests, failure matrix and interface sketches.
- **11-12. Differentiation and research program** — commercially useful focus and how to keep evidence current.
- **13-15. References, glossary and implementation directive** — bibliography, terms and development sequence.

**The companion CSV register** includes the same 300 `EV-NNN` identifiers, feature states, priorities, benchmark source IDs and acceptance tests. Start with the document for context; use CSV IDs to create engineering tickets.

> **Reference status:** Research and engineering-planning document, not a live-product certification, licensed vendor comparison, implementation commitment or security assessment. Prepared against the uploaded `Elveriq-main.zip` repository snapshot and official supplier web materials reviewed for this project.

> **Mission:** Build Elveriq from a transactional warehouse SaaS prototype into a complete, extensible warehouse execution platform, capable of handling real physical workflows as reliably as it handles digital orders.

# Executive research conclusion

The defining competitive gap is **execution**. Elveriq today can maintain a tenant, products, warehouses, stock totals, reservations, purchase orders, basic receipts, transfers, counts and returns. Market-leading products provide a second layer that turns customer demand and physical stock into verified work: directing staff to exact bins, scanning the right item or pallet, holding damaged goods, selecting picking tactics, packing cartons, booking carriers, loading trucks and explaining late shipments. A third layer coordinates customers, equipment, workforce, yards, automation and intelligent decisions. Those three layers must share a single consistent inventory truth.

This study benchmarks **17 named commercial systems or suites** and captures **300 candidate capabilities in 22 operational domains**. It is intentionally broad. The list is an applied union of documented capabilities across the vendor set, not an allegation that any single vendor offers all 300 items, that all editions include them, or that every proposed Elveriq implementation already exists in a competitor product. **Each feature entry describes an Elveriq requirement proposed using its cited source as a design reference**. Vendor statements are separated from our proposed acceptance tests. Feature availability, pricing, integration entitlements and service-level commitments must be rechecked before commercial claims.

The repository audit found **12 implemented capabilities, 14 partial capabilities and 274 gaps in this granular benchmark catalog**. These counts reflect the deliberate detail level and are not a maturity score, competitive ranking or percentage of completed work. The functional status refers to the reviewed archive only. A basic `warehouse` stock balance does not fulfill bin-level, lot-level or pallet-level traceability. A read-only pick list is not warehouse-directed picking. A return receipt is not a full RMA and inspection process. Preliminary repository evidence appears in Section 3.

**Decision recommendation.** Stabilize financial and inventory correctness first; build location-level inventory + warehouse task orchestration + scanning as one integrated platform; then complete picking, packing and dispatch. Add multi-owner/3PL billing and customer self-service for commercially differentiated growth. Preserve a modular path for enterprise labor, yard, manufacturing and automation. Never substitute a beautiful dashboard for validated physical execution.

## Research-at-a-glance

| Indicator | Finding |
|:--|:--|
| Named platforms or suites studied | 17 (enterprise, midmarket, SMB and 3PL-focused) |
| Distinct source links | 38 (predominantly vendor-primary documentation and product pages) |
| Candidate feature specifications | 300 across 22 domains |
| Current archive assessment | 12 built; 14 partial; 274 not established in the reviewed repository |
| Immediate non-negotiable | PostgreSQL concurrency, migrations, backups, security and pilot controls |
| First core product engine | Bin stock + task state machine + scan verification + immutable movement audit |
| First full physical outcome | PO or ASN to receiving, putaway, pick, carton pack, stage, load, ship and trace |

## Six findings that shape the product

1. **Micro-location inventory is foundational.** Odoo, Infor, Microsoft, NetSuite and the enterprise suites distinguish stock in bins, zones, statuses and sometimes handling units. Elveriq's aggregate balance should remain as a reportable roll-up rather than its sole source of physical truth [S01, S10, S21, S22, S24].
2. **Task orchestration is the workflow backbone.** Scanners need to confirm an assigned task with a verified source, destination, quantity, owner, lot and operator. The task engine makes directed receiving, putaway, picking, replenishment and counting possible [S02, S22, S26].
3. **Fulfillment is a chain of stateful evidence.** Enterprise WMS features include waves, scan-verified picking, packing stations, cartons/pallets, staging, loading and carrier documentation. Elveriq currently handles only early reservation/fulfillment logic [S01, S14, S19, S25].
4. **Commercial 3PL software is a distinct competitive category.** Extensiv, ShipHero, Infor and Tecsys document customer portals, multi-owner inventory and event-based service billing. These features create value for a warehouse operator whose customers own the goods [S10, S13, S15, S16, S18].
5. **Advanced vendors now integrate optimization into operations.** Blue Yonder's published 2026 features highlight shift forecasting, slotting heatmaps and robotics orchestration; Oracle and Infor describe wave/operations agents. These are valuable advanced layers, but their outputs require correct transaction data and human override [S07, S09, S11, S38].
6. **Cloud trust is a core WMS feature.** No operational sophistication compensates for lost inventory, duplicate picks, tenant leakage or a failed restore. The prototype explicitly warns that it is not ready for business-critical inventory. Security and reliability are part of the feature backlog, not a final polish phase.

# 1. Scope, method, and evidence rules

**Scope.** A multi-tenant cloud software service for independent warehouses, distributors, e-commerce fulfillment centers and later 3PLs. Elveriq is not itself a freight carrier, retailer, physical warehouse, or custodian of inventory unless future business choices change. We are researching software capabilities relevant to those customer classes; products such as transportation systems or carrier networks may be integrations rather than functionality built natively.

**Evidence approach.** Vendor-specific observations rely on official feature pages, technical help, learning sites and selected release notes. Sources are catalogued in the bibliography by S-number and URL. Product pages demonstrate that a vendor *advertises* a function; they do not prove availability in every edition or performance in a live deployment. Documentation often changes after a release. Features with no suitable primary source were framed as proposed Elveriq architecture, not assigned as verified competitive claims. Security and standards references come from OWASP, NIST, GS1 US and FDA. The supplied competitor write-up was useful context, but this paper rechecked vendor features rather than treating an earlier unsourced summary as independent proof.

**Research limitations.** No demo account of each competitor was operated; no private product manual, price quote, implementation contract, production metrics or customer configuration was examined. Some capabilities require partner products, extra modules, devices, implementations, or licenses. Vendor marketing performance figures were excluded from our internal forecasts; real Elveriq performance targets must be measured in pilots. Pricing, packaging and architectural decisions are not guaranteed across vendors. This is a curated 17-vendor study, not literally every WMS vendor in the world. Revisit at least quarterly.

**Feature-state rules for Elveriq.** "Built" = a relevant component exists in the archive. "Partial" = workflow exists in reduced form, not the accepted advanced capability. "Gap" = no sufficient implementation established in that archive. These are static source-inspection classifications, not comprehensive executed QA results. For each row, an S-reference means a **benchmark or motivating source for the feature area**, not necessarily an exact 1:1 vendor implementation of every design choice in our requirement or acceptance test.

**Priority scheme.** P0 = pre-pilot integrity, security or retained foundation; P1 = essential end-to-end warehouse execution; P2 = competitive operational and commercial expansion; P3 = high-complexity optimization or specialized operations; P4 = advanced automation, regulated niches or optional intelligence. Priority is a proposed sequence, not a calendar commitment.

# 2. Competitive landscape: seventeen platform benchmarks

The selected set includes deep enterprise suites, composable cloud WMS products, midmarket inventory suites and purpose-built e-commerce/3PL systems. We should avoid copying proprietary UI or workflows mechanically. Instead, benchmark outcomes: correct stock; shorter handling time; fewer mispicks; reliable customer billing; and real-time exception resolution.

## 2.1 SAP Extended Warehouse Management

**Position:** Enterprise execution ceiling. **Documented footprint:** Deep inbound/outbound, RF, warehouse monitor, lot/serial, labor, waves, HU and yard; integration with SAP ecosystem. **Commercial caution:** Dense configuration and SAP ecosystem dependencies. **What Elveriq should adopt:** Warehouse tasks, handling units, exception command center. **Sources:** [S01], [S02], [S35].

## 2.2 Manhattan ActiveWarehouse

**Position:** Unified enterprise operations. **Documented footprint:** Unified inventory, yard, labor, automation; editions designed for operational scale. **Commercial caution:** Edition differences: Essentials vs Enterprise vs Premier. **What Elveriq should adopt:** Unified work + dock + workforce model; modular packaging. **Sources:** [S03], [S04].

## 2.3 Blue Yonder Warehouse Management

**Position:** AI-orchestrated warehouse operations. **Documented footprint:** Execution, resource forecasting/orchestration, robotics hub, slotting, returns, analytics and AI. **Commercial caution:** Specific agents, features and packaging vary by version. **What Elveriq should adopt:** Explainable intelligence layered over transactional WMS. **Sources:** [S05], [S06], [S07], [S38].

## 2.4 Oracle Fusion Cloud Warehouse Management

**Position:** Enterprise omnichannel / manufacturing. **Documented footprint:** Advanced wave operations, cross-docking, flow-through, VAS, yard and production-linked inventory. **Commercial caution:** Broader Oracle SCM products may be separate. **What Elveriq should adopt:** Retail/wholesale order complexity and manufacturing edge. **Sources:** [S08], [S09].

## 2.5 Infor WMS

**Position:** High-configurability, multi-owner WMS. **Documented footprint:** Bin and license plate inventory, voice and RF, QC, 3PL billing, 3D visual warehouse, labor standards. **Commercial caution:** Advanced tools and integrations require fit assessment. **What Elveriq should adopt:** Rules, visual operations and financial customer costing. **Sources:** [S10], [S11].

## 2.6 Infios Warehouse Management

**Position:** Modular industrial and automation WMS. **Documented footprint:** Composable labor, voice, WCS, AMR, slotting, yard and warehouse execution. **Commercial caution:** Modules may be licensed separately; focus on deployment needs. **What Elveriq should adopt:** Automation adapters and simulation-ready foundation. **Sources:** [S12].

## 2.7 Tecsys WMS

**Position:** Complex distribution and regulated industries. **Documented footprint:** Visual worker guidance, adaptable receiving/picking/replenishment and commercial 3PL services. **Commercial caution:** Regulated customer compliance requires separate validation. **What Elveriq should adopt:** Accessible worker UX and specialist workflows. **Sources:** [S13].

## 2.8 Deposco Bright Warehouse

**Position:** Cloud omnichannel fulfillment. **Documented footprint:** Wave and waveless fulfillment, directed replenishment, cartonization, shipping rate shopping and robotics. **Commercial caution:** Marketing service-level figures are not Elveriq forecasts. **What Elveriq should adopt:** Packing to carrier pipeline and workflow orchestration. **Sources:** [S14].

## 2.9 Extensiv 3PL Warehouse Manager

**Position:** 3PL commercial reference. **Documented footprint:** 3PL-specific billing, customer portal, scanning, API, EDI, parcel processing, directed putaway. **Commercial caution:** Certain functions belong to additional products or tiers. **What Elveriq should adopt:** Owner-scoped inventory, billable events, portal and self-service. **Sources:** [S15], [S16], [S17].

## 2.10 ShipHero WMS

**Position:** High-volume e-commerce / 3PL. **Documented footprint:** Mobile picking, batch automation, barcode validation, 3PL billing, channels, portal and webhooks. **Commercial caution:** Marketing performance and integration counts are not guaranteed. **What Elveriq should adopt:** Fast worker flows and integration-rich onboarding. **Sources:** [S18].

## 2.11 Logiwa IO

**Position:** DTC fulfillment optimization. **Documented footprint:** Put-wall, walking-path optimization, carrier shipping, many pick methods and client portals. **Commercial caution:** Optimizations should be benchmarked on real warehouse layouts. **What Elveriq should adopt:** Packing workstations and dense pick strategy library. **Sources:** [S19], [S20].

## 2.12 Odoo Inventory

**Position:** Practical SMB functionality baseline. **Documented footprint:** Detailed location rules, FEFO/FIFO, picking strategies, barcodes, reservations, replenishment, return and customer flows. **Commercial caution:** Some features depend on other Odoo apps or configuration. **What Elveriq should adopt:** Minimum usability baseline for serious small warehouses. **Sources:** [S21].

## 2.13 Microsoft Dynamics 365 SCM WMS

**Position:** ERP-linked warehouse operations. **Documented footprint:** Configurable mobile tasks, license plates, waves, small parcel, labels, load, MHAX and monitoring. **Commercial caution:** Some mobile/advanced functions may be release- or module-specific. **What Elveriq should adopt:** Work execution state machines and handheld design. **Sources:** [S22], [S23].

## 2.14 NetSuite WMS

**Position:** ERP-native midmarket warehouse. **Documented footprint:** Mobile force scan, smart counting, bins, receiving, wave and pick tasks, pack and shipping integration. **Commercial caution:** WMS SuiteApps and dependencies matter. **What Elveriq should adopt:** Inventory-linked wave/task transactions and guided count. **Sources:** [S24], [S25], [S26], [S37].

## 2.15 Cin7 Core WMS

**Position:** SMB and inventory-centered operations. **Documented footprint:** Mobile receive, putaway, pick/pack, bins, stocktake, transfers, zone and FIFO/FEFO controls. **Commercial caution:** Advanced functionality differs by plan. **What Elveriq should adopt:** Lean mobile workflows suitable for independent warehouses. **Sources:** [S27].

## 2.16 Made4net SCExpert

**Position:** Warehouse + yard + delivery suite. **Documented footprint:** Core execution with labor, yard, last mile, routing and 3PL extensions. **Commercial caution:** Suite components are not all core WMS features. **What Elveriq should adopt:** Modular extension and supply-chain edges. **Sources:** [S28], [S29].

## 2.17 Fishbowl Advanced Warehouse

**Position:** SMB distribution and stock control. **Documented footprint:** Barcode/mobile work, multi-warehouse, reorder, 3PL separation and EDI-oriented distribution. **Commercial caution:** Capabilities must be confirmed for purchased version. **What Elveriq should adopt:** Simple warehouse onboarding and stock discipline. **Sources:** [S30].

## 2.18 Cross-market patterns and implications

| Market pattern | Repeated competitive signal | Elveriq implementation implication |
|:--|:--|:--|
| Barcode as default interaction | Odoo, NetSuite, Microsoft, ShipHero and 3PL products | Mobile-first scan flows, mandatory location checks, deliberate offline handling |
| Work release instead of flat lists | SAP, NetSuite, Infor and Microsoft | Task state machine with owners, assignment, SLAs, exceptions and audit |
| Location and handling-unit granularity | SAP, Infor, Oracle, Odoo and Microsoft | Location/HU and lot balance become core physical ledger dimensions |
| Mixed fulfillment modes | Infor, Deposco, Logiwa and Odoo | Single, wave, cluster, batch, zone, case/pallet and put-wall as selectable strategies |
| Multichannel integration | ShipHero, Logiwa, Extensiv, Deposco and Oracle | API gateway, adapters, canonical external IDs, webhooks and outbox |
| 3PL is a separate operating model | Extensiv, ShipHero, Infor and Tecsys | Customer-owned stock, client portals, event billing and SLA reporting |
| Enterprise extensions | Manhattan, SAP, Blue Yonder, Infios and Made4net | Modular yard, workforce, MHE/robotics, AI and transportation; avoid early monolith |
| Insight must lead to action | Blue Yonder, Manhattan, Oracle and Infor | KPI card opens corrective workflow, not a static chart |

# 3. Elveriq repository audit: reality before roadmap

**Snapshot basis:** The uploaded `Elveriq-main.zip` archive. It identifies itself as a prototype using a FastAPI web/API layer, SQLAlchemy ORM, SQLite for development and a configured but unproven PostgreSQL production path. It includes vanilla JS/HTML/CSS frontend, automated tests, staff invitations and several warehouse transaction services. Archive labels in earlier documents are not a live deployment check. Do not treat stale sections of ROADMAP.md and PROGRESS.md as more current than feature implementations and `RELEASE-16-MILESTONES.md`.

| Confirmed artifact | Concrete evidence in archive | Interpret carefully |
|:--|:--|:--|
| Workspace / login / role | `dispatchforge_app/auth.py`, `web.py`, `staff_service.py`, `models.py: Business, User, StaffInvitation` | Staff invitations exist, but email delivery and advanced IAM are absent |
| Product and warehouse | `models.py: Warehouse, Product, StockLevel`; `inventory_service.py` | Inventory is aggregated by `warehouse_id` and `product_id`, not by bin, lot, owner or handling unit |
| Stock ledger | `models.py: StockMovement`; `inventory_service.py` | Movement records are present; event sourcing, full posting controls and status breakdowns are not established |
| Customer demand | `models.py: CustomerOrder, OrderLine`; `order_service.py` | Reservation and fulfillment occur but physical pick/pack/load workflow is not modeled |
| Purchasing and receiving | `models.py: PurchaseOrder, PurchaseOrderLine`; `purchasing_service.py` | Partial receiving exists; ASN, QC and directed putaway do not |
| Warehouse transfers | `models.py: InventoryTransfer`; `transfer_service.py`; `TRANSFERS.md` | Retry-safe transfer foundation; PostgreSQL concurrency tests require execution with live DB |
| Counts and returns | `models.py: CycleCount, ReturnReceipt`; services and API routes | Aggregate cycle counts and resellable return intake, not bin counts or full RMA disposition |
| Pick list | `picking_service.py`; `/orders/{id}/pick-list(.csv)` | Read-only list, not staff work execution |
| Planning and replenishment | `operations_service.py`, `replenishment_service.py` | Seven-day queue and threshold heuristic, not demand AI or physical pick-face tasks |
| Frontend | `templates/dashboard.html`, `static/app.js`, CSS | Responsive operations UI but no real RF/scanner workflow established |
| Operational safety | `SECURITY.md`, `RELEASE-16-MILESTONES.md`, `ARCHITECTURE.md` | Prototype explicitly calls for migrations, backup, rate limits, audit, production testing and security review |

**Known stock invariant.** `0 <= reserved <= on_hand` and `available = on_hand - reserved`. Keep these in the stock accounting model, and expand to a balanced inventory ledger with dimensions for tenant, warehouse, location, owner, product, stock condition, lot, serial and HU as appropriate. Aggregate totals should derive from a single authoritative posting model. Do not create simultaneous unreconciled aggregate and granular ledgers.

**Implementation boundary.** Functions in `inventory.py`, `warehouse_selection.py` and `distance.py` are legacy educational/simulation material. They do not establish shipping optimization, real warehouse ranking or live network stock in the SaaS application. The repository's own README says no real customer deployment or production inventory guarantee is established. This paper assumes real user onboarding and live operations are future work.

**Source inspection vs testing.** We inspected repository files and the declared API/model shapes. We did not verify a hosted environment, paid integrations, scanner devices, real customer logs or all advertised automated tests; do not represent this paper as runtime certification.

# 4. The proposed Elveriq product model

## 4.1 Architectural north star

Four layers must remain independently understandable while sharing a single audit trail:

1. **Commercial control plane.** Workspaces, contracts, clients, feature editions, users, roles, licensing, invoices and support. One operator workspace may manage multiple customer inventory owners; those concepts are not interchangeable.
2. **Warehouse transaction core.** Product catalog, facility graph, ownership, lot/serial, HU, stock ledger, orders, inventory reservations and accounting-safe reconciliation.
3. **Physical execution engine.** Work requests, warehouse tasks, workers, scanners, exceptions, receipts, picks, packing stations, shipping loads and completed evidence.
4. **Decision and integration layer.** ERP/carrier/e-commerce adapters, events, dashboards, rules, workload optimization, AI, robotics and optional regulated-sector modules.

```
External systems: ERP | Storefronts | Marketplaces | Carriers | EDI | Devices
                <-> integration adapters / inbox / transactional outbox
                               |
  Workspace / roles / client ownership / rate cards / feature configuration
                               |
       Orders | Purchase Orders | Returns | Production | Appointments
                               |
       Planning + allocation + task orchestration + exception handling
                               |
        Scanner / RF / packing / supervisor / customer portal clients
                               |
             Inventory posting service (atomic + idempotent)
                               |
         Immutable operational journal + physical stock balances
                               |
     PostgreSQL + job queue + metrics/logs/traces + backups + alerts
```

This is an architecture *proposal*, not a claim that the uploaded repository already has each block. Prefer a modular monolith and explicit service boundaries at first, rather than premature microservices. Split components only when teams, throughput and isolation requirements justify it. The competitor references motivate the feature domains, not the exact technology stack.

## 4.2 Critical data model additions

| Proposed entity | Minimum fields / relationships | Non-negotiable rule |
|:--|:--|:--|
| `StorageLocation` | tenant, warehouse, zone, parent, code, type, capacity, restriction | code unique within warehouse; hierarchy cannot cycle |
| `InventoryUnit` or balance key | tenant, warehouse, bin, owner, product, lot, condition, HU, qty | sum to authorized physical stock; no negative available |
| `Lot` / `Serial` | product, supplier lot, dates; serial uniqueness domain | preserve receipt-to-shipment genealogy |
| `HandlingUnit` | barcode/license plate, HU type, parent HU, current bin, owner | no multiple parents or silent merge across owners |
| `WarehouseTask` | type, work request, source, destination, qty, priority, status, assignee | explicit idempotent state transitions |
| `TaskEvent` / `ScanEvent` | actor/device, task, value, timestamp, result, correlation ID | rejected scans audit without stock movement |
| `ReservationAllocation` | demand line, supply bin, lot/HU, condition, qty, expiration | cannot over-allocate available eligible stock |
| `ReceivingDelivery` / `ASN` | PO, supplier, expected line, cartons, shipment, carrier, ETA | discrepancy preserves expected vs actual |
| `Inspection` / `Exception` | reason, evidence, hold, owner, approver, lifecycle | hold never automatically becomes sellable |
| `Package` / `Shipment` / `Load` | order lines, HU/carton, label, carrier, staging, load proof | ship only accepted packed quantities |
| `FulfillmentWave` / `PickBatch` | selection policy, released tasks, cutoff, status | conserve line quantities through split/merge |
| `InventoryOwner` / `ServiceRate` / `BillableEvent` | 3PL client, contract version, operation, amount/currency | exactly-once event charge and full invoice trace |
| `IntegrationConnection` / `InboxEvent` / `OutboxEvent` | tenant, provider, IDs, payload hash, attempt, status | ingest and publish with idempotency and retry |
| `DockAppointment` / `EquipmentResource` | facility, door/asset, capability, schedule, state | no conflicting occupancy or unqualified assignment |

## 4.3 State machines and transactional truth

**Warehouse task:** requested -> queued -> released -> assigned -> started -> completed; exceptional branches are blocked, partially completed, cancelled, or reversed with supervisor authorization. "Done" must be caused by scan-confirmed or explicitly supervised evidence, not by navigation or CSV generation.

**Inventory:** expected (not on hand) -> received/staged (possibly on quality hold) -> bin stock available -> allocated -> picked (in tote/HU) -> packed -> staged -> loaded -> shipped. An inventory state transition should not accidentally double-count a unit in two physical locations. Use one posting API with constrained transitions; reserve a destination and enforce concurrent stock selection where needed.

**Outbound order:** draft -> validated -> allocated/partially allocated -> released -> picking -> packing -> ready to ship -> staged -> loaded -> shipped; alternate branches: on hold, backordered, cancelled, partially shipped, return pending. Define what actor and event is authorized to cross each boundary. Split shipments and carrier manifest voids require traceable compensating events.

**3PL billing:** verified operational event -> candidate charge -> rated charge (effective customer contract) -> review -> invoice draft -> approved/exported -> paid/reconciled. Reprocessing a scan must not bill twice. Disputes and credits must not rewrite the source event.

## 4.4 Concurrency, outbox and idempotency rules

- Represent all physical and monetary actions as database transactions. Under concurrent PostgreSQL sessions, two pickers cannot both consume the last available unit in the same bin.
- Idempotency keys must scope to tenant and operation, include canonical payload fingerprint, and reject mismatched reuses. A retry returns the original result, never a second receipt or shipment.
- Put stock balance updates, task transitions and ledger event creation into a single transaction. Publish integration notifications through a committed outbox, not by calling an external API before commit.
- For multi-step work, model explicitly *in transit* or *staged* inventory. Do not reduce warehouse aggregate stock merely because a worker takes goods from one internal aisle to another.
- Devices offline for minutes may cache an instruction, but server inventory is authoritative. On reconnection, replay via unique event ID; conflicts require review, not silent overwrite.
- Every enterprise KPI must declare source events, formula, timezone, inclusions/exclusions and freshness. An "orders shipped" card reads ship evidence, not orders merely marked fulfilled in a simplistic reservation flow.

# 5. Master competitive capability register (300 specifications)

Every item below is a proposed Elveriq feature requirement that can be tracked as a backlog issue. The code `EV-NNN` is stable within this version. "Requirement" describes target behavior; "Acceptance" is a minimum observable test. "References" point to official industry/vendor sources listed in Section 13. The full register is also supplied as CSV for filtering, editing and importing into a ticket system. **Gap** means missing or not established in our inspected archive, not necessarily absent in every live branch.

## 5.1 SaaS control plane and identity (12 capabilities)

WMS credibility begins with repeatable, secure tenant onboarding, permissions and customer service. **Benchmark references:** [S15], [S16], [S18], [S32], [S33].

### EV-001 | Multi-business workspaces

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S15], [S18].

**Requirement:** Keep every company dataset separate, including workers and stock.  **Acceptance:** Business A cannot list, change, or infer business B records.

### EV-002 | Owner and staff roles

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S15], [S22].

**Requirement:** Apply centrally defined warehouse permissions per action.  **Acceptance:** A picker cannot create users, edit billing, or adjust stock.

### EV-003 | Invitation lifecycle

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S18].

**Requirement:** Invite staff with expiring single-use link and confirmed email delivery.  **Acceptance:** Expired and reused links fail and email delivery is audited.

### EV-004 | Password recovery and verification

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S33].

**Requirement:** Provide secure verified reset, recovery, and account verification.  **Acceptance:** Tokens expire, cannot be reused, and do not reveal accounts.

### EV-005 | Multifactor authentication

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S33].

**Requirement:** Support authenticator/passkey options for privileged accounts.  **Acceptance:** Sensitive actions require appropriate authentication and step-up.

### EV-006 | Device and session administration

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S22], [S33].

**Requirement:** Display and revoke active scanner and web sessions.  **Acceptance:** Revoked handheld stops executing tasks promptly.

### EV-007 | Role and permission designer

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S15].

**Requirement:** Grant scoped actions by warehouse and role, not only owner/staff.  **Acceptance:** Policy tests deny unauthorized resource and action combinations.

### EV-008 | Warehouse-scoped team assignments

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S13].

**Requirement:** A user may work at selected facilities and zones.  **Acceptance:** Assignments cannot surface work from an unassigned facility.

### EV-009 | Role-based homepage and navigation

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S13].

**Requirement:** Show relevant actions for receiver, picker, supervisor, owner, 3PL customer.  **Acceptance:** Each role sees intended queues, KPI cards, and direct actions.

### EV-010 | Customer self-service account

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S16], [S18].

**Requirement:** Allow 3PL inventory owners to see only their own stock and orders.  **Acceptance:** Customer users cannot see another inventory owner's data.

### EV-011 | Feature flags and editions

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S03], [S06].

**Requirement:** Enable modules by edition, customer agreement, and warehouse.  **Acceptance:** Disabled features cannot execute by direct API call.

### EV-012 | Tenant activation and onboarding checklist

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S15], [S18].

**Requirement:** Wizard covers facilities, units, employees, inventory import, first receipt.  **Acceptance:** New tenant can complete a safe sample workflow end to end.

## 5.2 Warehouse topology and space (13 capabilities)

A WMS knows not only which warehouse contains stock but the actual location, capacity and operational path. **Benchmark references:** [S01], [S10], [S20], [S21], [S22].

### EV-013 | Warehouse list and details

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S20], [S21].

**Requirement:** Retain multihouse facility registry with tenant scope.  **Acceptance:** Warehouse records cannot cross tenants.

### EV-014 | Warehouse zones and areas

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Define receiving, reserve, pick, pack, returns, quarantine and dispatch areas.  **Acceptance:** Each zone has type, identifier, and permissible movements.

### EV-015 | Aisles racks shelves bins

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S24].

**Requirement:** Model hierarchical and unique machine-scannable physical locations.  **Acceptance:** One bin belongs to one warehouse and has unique readable code.

### EV-016 | Locations and type flags

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Flag reserve vs pick face, floor storage, temperature zone or hazardous restrictions.  **Acceptance:** Wrong-zone putaway is blocked by rule.

### EV-017 | Put-wall and consolidation cells

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19].

**Requirement:** Track staging and put-wall cubbies allocated to each order.  **Acceptance:** One cubby never silently mixes orders.

### EV-018 | Location capacity dimensions

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S20], [S21].

**Requirement:** Maintain max units, weight, cube, pallet positions, and compatible SKUs.  **Acceptance:** Suggested putaway excludes over-capacity bins.

### EV-019 | Location barcode and printable sign

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S25].

**Requirement:** Print unique shelf/bin identifier that handheld scans must confirm.  **Acceptance:** Scan of different bin fails and records incident.

### EV-020 | Pick path sequence

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S22].

**Requirement:** Define walk order and point-to-point travel graph or sequence.  **Acceptance:** Same items yield reproducible accessible route order.

### EV-021 | Bin availability and blocks

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S24].

**Requirement:** Mark bins available, blocked, full, under maintenance or count-locked.  **Acceptance:** Work cannot allocate from unavailable locations.

### EV-022 | Warehouse occupancy and heatmap

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S07], [S10].

**Requirement:** Aggregate used volume, travel and replenishment hotspot by zone.  **Acceptance:** Utilization calculation reconciles with location stocks.

### EV-023 | Multiple storage conditions

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S21].

**Requirement:** Specify temperature, security or compatibility restrictions by zone.  **Acceptance:** Products are routed only to compliant supported locations.

### EV-024 | Location audit and genealogy

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Maintain history of moves and adjustments per bin.  **Acceptance:** Each on-hand change has actor, source and reason.

### EV-025 | Dynamic and fixed pick faces

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S20], [S21].

**Requirement:** Configure fixed SKU facing or temporarily assign dynamic picking area.  **Acceptance:** Allocation respects location mode and replenishment links.

## 5.3 Product and reference master data (16 capabilities)

Reliable operations require a richer product identity than SKU plus unit price. **Benchmark references:** [S01], [S21], [S22], [S27].

### EV-026 | SKU catalog

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S21].

**Requirement:** Preserve tenant-unique products with units and reorder points.  **Acceptance:** Duplicate SKU in tenant is rejected.

### EV-027 | Supplier directory

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S21].

**Requirement:** Preserve supplier entity and purchasing connections.  **Acceptance:** Supplier cannot be linked to other tenant records.

### EV-028 | GTIN and alternate barcodes

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S31].

**Requirement:** Map multiple vendor barcodes and standard GTIN to a SKU.  **Acceptance:** A configured barcode resolves deterministically.

### EV-029 | Item dimensions and weight

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S21].

**Requirement:** Store length, width, height, weight with declared units.  **Acceptance:** Cartonization and capacity use converted standard units.

### EV-030 | Unit-of-measure conversions

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S10].

**Requirement:** Allow each, inner, carton, case, pallet with exact conversion ratios.  **Acceptance:** Receiving cases preserves base-unit quantity.

### EV-031 | Multi-variant product families

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21].

**Requirement:** Support size, color and other variation attributes.  **Acceptance:** Each sellable variant has separate SKU and inventory.

### EV-032 | Lot and batch attributes

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S21].

**Requirement:** Record batch identity, production dates and supplier lot IDs.  **Acceptance:** Every applicable receipt and pick references the correct lot.

### EV-033 | Unique serial identification

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S25].

**Requirement:** Capture serial at receive, move, pack and return.  **Acceptance:** One active serial cannot appear in two bins.

### EV-034 | Expiration and best-before

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S21].

**Requirement:** Track sell-by, expiry, shelf-life and minimum remaining life.  **Acceptance:** Allocation never violates configured expiry policy.

### EV-035 | Catch weight and variable weight

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S10].

**Requirement:** Track physical units and measured weight when the product requires it.  **Acceptance:** Transaction audits both base units and actual weight.

### EV-036 | Hazard and handling characteristics

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S22], [S10].

**Requirement:** Record product segregation, fragility and temperature instructions.  **Acceptance:** Incompatible picks and putaway trigger approval or rejection.

### EV-037 | Product substitution and cross-reference

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S08], [S21].

**Requirement:** Define permitted substitutes subject to customer approval.  **Acceptance:** Fulfillment uses substitution only within explicit policy.

### EV-038 | Kits and BOM product definitions

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S21].

**Requirement:** Define multi-component bundles and component quantities.  **Acceptance:** Kit availability derives from components without double counting.

### EV-039 | Customer-specific product aliases

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S18].

**Requirement:** Resolve each 3PL customer's item numbers to internal SKU.  **Acceptance:** Client mappings never collide across owners.

### EV-040 | Vendor pack configuration

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S27].

**Requirement:** Track purchase pack sizes, minimum order units and label formats.  **Acceptance:** PO and receipt conversions reconcile to base units.

### EV-041 | Master data change approval

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22].

**Requirement:** Control high-impact edits to product identities and UOM.  **Acceptance:** Revision is logged and historical transactions retain identity.

## 5.4 Inbound planning, ASN and receiving (16 capabilities)

Inbound operations bridge expected supply with real dock receipts, discrepancies and physical units. **Benchmark references:** [S01], [S08], [S10], [S14], [S15].

### EV-042 | Purchase orders

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S15], [S21].

**Requirement:** Preserve supplier PO, destination and line quantities.  **Acceptance:** Each receipt cannot exceed permitted expected quantity.

### EV-043 | Partial receipt against PO

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S14], [S15].

**Requirement:** Preserve incremental receipts with ledger updates.  **Acceptance:** Second receipt reflects outstanding balance correctly.

### EV-044 | Advance shipping notice ingestion

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S14].

**Requirement:** Import supplier ASN/856 expected cartons, items and dates.  **Acceptance:** Supplier ASN matches PO lines or enters discrepancy review.

### EV-045 | Scheduled inbound appointments

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S22].

**Requirement:** Book carrier, trailer, dock, time and planned handling resources.  **Acceptance:** Conflicting dock windows are flagged.

### EV-046 | Expected shipment and container

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S10].

**Requirement:** Track multiple POs, trailers and containers per arrival.  **Acceptance:** Unloaded units tie back to shipment and supplier.

### EV-047 | Unplanned inbound receiving

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S27].

**Requirement:** Receive authorized unannounced stock with controlled exception.  **Acceptance:** Unknown receipt requires supervisor reason and ownership.

### EV-048 | Receiving work queue

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S15].

**Requirement:** Display inbound arrivals and assignment to receiving workers.  **Acceptance:** Supervisor can assign, prioritize and track pending receipts.

### EV-049 | Scan-verified receiving

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S16], [S25].

**Requirement:** Scan expected item, lot, quantity and receiving area.  **Acceptance:** Unexpected barcode does not enter sellable stock silently.

### EV-050 | Blind receiving option

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S25].

**Requirement:** Hide expected qty for chosen counts to improve independent accuracy.  **Acceptance:** Comparison appears after submission, not before.

### EV-051 | Over short and damaged receipts

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S15], [S22].

**Requirement:** Record quantity and damage discrepancy with disposition.  **Acceptance:** Cannot over-receive beyond tolerance without approval.

### EV-052 | Receiving photograph and attachments

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S12], [S15].

**Requirement:** Attach evidence to delivery or discrepancy without exposing other tenant.  **Acceptance:** File types, sizes and retention are controlled.

### EV-053 | Case and pallet label creation

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S31].

**Requirement:** Print unique handling-unit label for received packages.  **Acceptance:** Each label resolves to package contents and location.

### EV-054 | Drop trailer and unloading workflow

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S12].

**Requirement:** Track trailer check in, seal status, unload start and complete.  **Acceptance:** Arrival timestamps and users are auditable.

### EV-055 | Vendor performance scorecard

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S13], [S21].

**Requirement:** Measure PO fill, damage, ASN accuracy and on-time arrivals.  **Acceptance:** Report values reconcile with receipts and planned dates.

### EV-056 | Direct receipt to cross dock

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S08].

**Requirement:** Reserve inbound units against outbound demand without reserve storage.  **Acceptance:** Outbound demand and receipt are linked with traceable transfer.

### EV-057 | Receiving landed-cost reference

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S23].

**Requirement:** Attach freight and duties as optional ERP-facing finance data.  **Acceptance:** Financial amounts never silently change stock quantity.

## 5.5 Inspection, quality and quarantine (10 capabilities)

Counted material is not necessarily available for sale. Quality state must be physically and digitally enforced. **Benchmark references:** [S01], [S10], [S21], [S22].

### EV-058 | Receiving quality inspection

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S10], [S21].

**Requirement:** Run inspection checklist before release to available stock.  **Acceptance:** Rejected lots cannot be allocated to orders.

### EV-059 | Hold and quarantine statuses

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S22].

**Requirement:** Represent quality, damaged, recall, customs, and customer hold.  **Acceptance:** Available-to-pick excludes all nonreleasable stock.

### EV-060 | Disposition workflow

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Authorize release, return to vendor, rework or destruction.  **Acceptance:** Every status change records approver and reason.

### EV-061 | Quality defect codes

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S15].

**Requirement:** Maintain searchable standard reasons for defects and shortages.  **Acceptance:** Exception trend report groups by code.

### EV-062 | Sampling and AQL policy

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S13].

**Requirement:** Configure product- or supplier-specific sample inspection.  **Acceptance:** Failed sample routes lot to quarantine.

### EV-063 | Inbound inspection photos

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S12], [S15].

**Requirement:** Attach evidence with traceable time and actor.  **Acceptance:** Documents remain linked after item relocation.

### EV-064 | Outbound QC gate

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S25], [S14].

**Requirement:** Verify order correctness and special handling before handoff.  **Acceptance:** Failed check stops carrier manifest completion.

### EV-065 | Temperature excursion record

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S13], [S34].

**Requirement:** Optionally record cold chain excursions and mitigation actions.  **Acceptance:** Shipment remains held pending authorized disposition.

### EV-066 | Recall search and stock hold

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S21].

**Requirement:** Identify all on-hand and shipped units sharing affected lot.  **Acceptance:** Recall produces an auditable affected-customer report.

### EV-067 | Quality dashboards and aging

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S13], [S22].

**Requirement:** Show held stock value, unresolved exceptions and turnaround time.  **Acceptance:** Dashboard reconciles to current hold records.

## 5.6 Putaway and internal warehouse tasks (12 capabilities)

The task engine turns transaction intent into accountable physical actions. **Benchmark references:** [S01], [S02], [S10], [S21], [S22].

### EV-068 | Directed putaway suggestion

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S10].

**Requirement:** Choose bin using compatibility, space, velocity and strategy.  **Acceptance:** Candidate bin is valid at confirmation time.

### EV-069 | Putaway scan confirmation

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S25].

**Requirement:** Require source HU and destination bin scan before completion.  **Acceptance:** Wrong bin scan leaves task open and stocks unchanged.

### EV-070 | System-directed task object

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S02], [S22].

**Requirement:** Create task type, source, destination, item, quantity, assignee and status.  **Acceptance:** Task has immutable history and replay-safe completion.

### EV-071 | Task assignment and release

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S02], [S22].

**Requirement:** Assign work by role, zone, priority and worker availability.  **Acceptance:** One task cannot be simultaneously completed twice.

### EV-072 | Task status lifecycle

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S26].

**Requirement:** Support queued, released, assigned, started, blocked, done, cancelled.  **Acceptance:** Only authorized state transitions are allowed.

### EV-073 | Multi-step movement work

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S02], [S22].

**Requirement:** Allow receive-to-staging-to-storage transitions as linked tasks.  **Acceptance:** No missing or duplicated units across chained steps.

### EV-074 | Ad-hoc bin to bin move

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S27].

**Requirement:** Worker may request permitted location move with scan.  **Acceptance:** Source quantity decrements as destination increments atomically.

### EV-075 | Task split and partial completion

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22], [S26].

**Requirement:** Handle shortage, damaged items and residual tasks.  **Acceptance:** Completing partial quantity leaves explicit remainder.

### EV-076 | Task interleaving

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S02], [S35].

**Requirement:** Mix putaway and pick work to reduce empty travel.  **Acceptance:** Sequence selection is explainable and preserves priorities.

### EV-077 | Equipment-aware assignment

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S05], [S12].

**Requirement:** Require forklift skill, equipment availability or aisle access.  **Acceptance:** Unqualified worker cannot accept restricted work.

### EV-078 | Task exception and supervisor resolution

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S19].

**Requirement:** Block workflow on missing stock, blocked bin or scan mismatch.  **Acceptance:** Supervisor can resolve with audit and no phantom inventory.

### EV-079 | Warehouse task SLA and escalation

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S22].

**Requirement:** Set due-by time and raise overdue notifications.  **Acceptance:** Late tasks appear in actionable queue with cause.

## 5.7 Inventory ledger, reservations and traceability (17 capabilities)

Quantity truth must reconcile at each location, condition, lot, serial and owner. **Benchmark references:** [S01], [S10], [S21], [S22], [S24].

### EV-080 | Per-warehouse on hand and reserved

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S21].

**Requirement:** Preserve quantity and reservation invariant at SKU/warehouse level.  **Acceptance:** No transaction makes reserved exceed on hand.

### EV-081 | Append-only movement history

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S21].

**Requirement:** Preserve user and reason for warehouse aggregate changes.  **Acceptance:** Movement history reconciles with aggregate after replay.

### EV-082 | Bin-level on hand and reserved

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S10].

**Requirement:** Add inventory balances keyed by physical bin and stock attributes.  **Acceptance:** Sum of bin balances matches warehouse aggregate.

### EV-083 | Available, allocated, damaged and QC states

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S22].

**Requirement:** Separate physical existence from legal availability.  **Acceptance:** On-hold units never show as available-to-promise.

### EV-084 | Owner and consignment inventory

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S15].

**Requirement:** Track economic owner separately from tenant running warehouse.  **Acceptance:** Orders allocate only from authorized ownership pools.

### EV-085 | Lot genealogy and shipped trace

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S21].

**Requirement:** Connect supplier receipt, movements, orders and shipped lots.  **Acceptance:** Query reveals all orders shipped from an affected lot.

### EV-086 | Serial lifecycle and uniqueness

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S25].

**Requirement:** Track serial event path without duplicated active assignment.  **Acceptance:** Same serial cannot be booked at two locations.

### EV-087 | License plate / handling unit tracking

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S10], [S22].

**Requirement:** Identify pallets, cartons and totes independent of SKU.  **Acceptance:** Moving parent HU moves its contained inventory consistently.

### EV-088 | Available to promise ATP

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S21].

**Requirement:** Calculate future on hand using inbound and outbound commitments.  **Acceptance:** Promise date has traceable supply and demand components.

### EV-089 | Reserved stock expiration and release

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S22].

**Requirement:** Configure timebound soft reservations and release rules.  **Acceptance:** Expired holds free only intended quantity.

### EV-090 | Stock ownership transfer

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S15].

**Requirement:** Record approved change of stock owner while keeping location.  **Acceptance:** Both owners receive immutable audit references.

### EV-091 | Inter-warehouse stock transfer

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S20].

**Requirement:** Preserve retry-safe completed moves between facilities.  **Acceptance:** Retry with same idempotency key doesn't repeat movement.

### EV-092 | In-transit inventory lifecycle

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22], [S29].

**Requirement:** Separate dispatch and destination receipt for transfers.  **Acceptance:** Destination increases only after verified receipt.

### EV-093 | Inventory status reclassification

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S27].

**Requirement:** Move inventory from inspected to sellable or damaged states.  **Acceptance:** Reason and approver are mandatory for restricted statuses.

### EV-094 | Stock aging by lot and bin

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21].

**Requirement:** Compute receipt age and expiry exposure from movements.  **Acceptance:** Report distinguishes FIFO receipt age from last move age.

### EV-095 | Negative adjustment approval policy

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Require privileges, reason and thresholds for manual corrections.  **Acceptance:** Large write-off waits for approval and is logged.

### EV-096 | Cycle count freeze policy

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S24], [S27].

**Requirement:** Allow count-at-snapshot with safe parallel work handling.  **Acceptance:** Detected intervening transaction triggers correct resolution.

## 5.8 Counting, inventory accuracy and replenishment (13 capabilities)

Control discrepancies and keep pick faces supplied without chasing spreadsheets. **Benchmark references:** [S21], [S22], [S24], [S27].

### EV-097 | Aggregate cycle count records

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S24].

**Requirement:** Preserve creation, posting and stale snapshot checks.  **Acceptance:** Posting stale count does not overwrite newer stock.

### EV-098 | Blind bin cycle count

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S24], [S25].

**Requirement:** Guide worker to count bins without expected quantity.  **Acceptance:** Expected value hidden until submission.

### EV-099 | ABC count frequency rules

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S28].

**Requirement:** Schedule counts by velocity, value and historical variance.  **Acceptance:** Schedule is reproducible and honors cycle cadence.

### EV-100 | Triggered exception counts

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22], [S27].

**Requirement:** Create count after missing pick or unexpected receive.  **Acceptance:** Count closes the triggering exception and records variance.

### EV-101 | Location quarantine during count

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22].

**Requirement:** Prevent unsafe allocation or allow version-aware adjustment.  **Acceptance:** Every overlapping move is reconciled explicitly.

### EV-102 | Count variance approvals

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Set quantity/value thresholds and reason taxonomy.  **Acceptance:** Unauthorised variance cannot change stock ledger.

### EV-103 | Count KPI and root cause

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S13], [S24].

**Requirement:** Track accuracy, repeat issues and variance by zone/worker.  **Acceptance:** Report shows denominator and calculation period.

### EV-104 | Threshold-based replenishment

**Elveriq:** Partial  |  **Priority:** P1  |  **References:** [S21].

**Requirement:** Preserve reorder-point analysis and open PO consideration.  **Acceptance:** Recommendation quantity and existing demand reconcile.

### EV-105 | Min/max pick-face replenishment

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Generate replenishment task when pick face below target.  **Acceptance:** Replenishment respects reserve-bin and pick-bin quantities.

### EV-106 | Demand-triggered replenishment

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S21].

**Requirement:** Create task to supply short picking work and due orders.  **Acceptance:** Replenishment priority inherits shipment cutoff.

### EV-107 | Inter-warehouse reorder suggestions

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S20].

**Requirement:** Suggest moves before purchasing when another site has excess.  **Acceptance:** Approved transfer respects available stock and transit time.

### EV-108 | Supplier lead-time and safety stock

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21].

**Requirement:** Model lead time, variability, service level and review cadence.  **Acceptance:** Suggested order documents assumptions and units.

### EV-109 | Auto draft PO or transfer

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21].

**Requirement:** Convert approved rule recommendations to draft source documents.  **Acceptance:** No automatic committed purchase without explicit permission.

## 5.9 Orders, omnichannel and allocation (15 capabilities)

Orders from one or many channels become executable demand with exact promises. **Benchmark references:** [S08], [S14], [S18], [S19], [S21].

### EV-110 | Customer order entry

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S19], [S21].

**Requirement:** Preserve multi-line API order, warehouse and due date.  **Acceptance:** Order quantities reserve inventory only once.

### EV-111 | Scheduled reservation

**Elveriq:** Built  |  **Priority:** P0  |  **References:** [S21].

**Requirement:** Preserve safe reserve, fulfill and cancel behavior.  **Acceptance:** Cancellation releases reserved not shipped stock.

### EV-112 | Order import and validation

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S19], [S18].

**Requirement:** Import CSV/API orders with mapping, errors and deduplication.  **Acceptance:** Duplicate external order is idempotent.

### EV-113 | External sales channel connector

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S18], [S20].

**Requirement:** Pull authorized orders from marketplaces and shops.  **Acceptance:** Connector logs every sync and skips already applied events.

### EV-114 | Omnichannel order normalization

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S19].

**Requirement:** Standardize addresses, units, service, SKU aliases and promises.  **Acceptance:** Same order has unambiguous canonical line and state.

### EV-115 | Inventory allocation rules engine

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S08], [S21].

**Requirement:** Allocate by availability, ownership, lot and priority policy.  **Acceptance:** No unit is allocated to multiple competing orders.

### EV-116 | Partial allocation and backorders

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S26].

**Requirement:** Ship available quantities and retain remainder with ETA.  **Acceptance:** Open backorder reconciles to original order lines.

### EV-117 | Future inbound order allocation

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S21].

**Requirement:** Optionally reserve expected receipts with cautious promise policy.  **Acceptance:** Expected inbound cannot be treated as available stock.

### EV-118 | Order priority and cutoffs

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S05], [S19].

**Requirement:** Set ship-by targets, customer tiers and carrier cutoffs.  **Acceptance:** Higher urgency appears ahead in releasable task queue.

### EV-119 | Multi-warehouse order sourcing

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S20].

**Requirement:** Compare network inventory, shipping distance and split costs.  **Acceptance:** Routing explanation shows chosen facility and stock source.

### EV-120 | Order hold and cancellation

**Elveriq:** Partial  |  **Priority:** P1  |  **References:** [S01], [S21].

**Requirement:** Extend cancel with fraud, payment, customer, QA and address holds.  **Acceptance:** Held order cannot be released to picking.

### EV-121 | Customer order change management

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S08].

**Requirement:** Allow safe address, line and quantity amendments before ship.  **Acceptance:** Every change recalculates stock and work dependencies.

### EV-122 | Wholesale B2B retail compliance

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S18].

**Requirement:** Store retailer routing, labeling, carton and EDI rules.  **Acceptance:** Compliance checklist blocks non-conforming shipment.

### EV-123 | Order aggregation and split shipments

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S22].

**Requirement:** Merge or split fulfillment work without losing source order links.  **Acceptance:** All packages trace to correct original demand.

### EV-124 | Dropship and direct fulfillment

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S19].

**Requirement:** Represent supplier-to-customer dispatch distinct from WMS stock.  **Acceptance:** No phantom warehouse movement is recorded.

## 5.10 Picking and execution strategies (19 capabilities)

This is the operational heartbeat of a serious WMS: verified pick work and adaptable strategies. **Benchmark references:** [S01], [S10], [S19], [S21], [S22], [S26].

### EV-125 | Read-only pick list and CSV

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S19], [S26].

**Requirement:** Preserve printable order item list without claiming execution.  **Acceptance:** Printed list agrees with reserved quantities.

### EV-126 | Single order directed picking

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S25].

**Requirement:** Tell picker exact source bin, lot, qty and target container.  **Acceptance:** Scan verifies correct item and bin before commit.

### EV-127 | Picker work queue

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S26].

**Requirement:** Display accepted, assigned, due, and blocked pick tasks.  **Acceptance:** Picker cannot complete another worker's restricted tasks.

### EV-128 | Scan-to-confirm picks

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S25], [S27].

**Requirement:** Verify item and source bin or require controlled override.  **Acceptance:** Wrong scan cannot ship wrong SKU silently.

### EV-129 | Short pick and substitution exception

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22], [S19].

**Requirement:** Capture available qty, exception reason and reallocation request.  **Acceptance:** No reserved quantity remains locked after final resolution.

### EV-130 | Pick reservation at bin level

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Reserve stock from specific lot/bin and release on cancellation.  **Acceptance:** Two pickers cannot remove same last unit.

### EV-131 | Wave picking

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S10].

**Requirement:** Combine due orders into timed release groups by policy.  **Acceptance:** Wave generates pick tasks and reports remaining work.

### EV-132 | Batch picking

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S21].

**Requirement:** Pick shared SKUs for many orders in one trip.  **Acceptance:** Sorted units are allocated back to correct orders.

### EV-133 | Cluster picking by cart

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S21].

**Requirement:** Use one cart with assigned order totes for many orders.  **Acceptance:** Every scan goes to correct tote and order.

### EV-134 | Zone picking and pick-pass

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S10].

**Requirement:** Divide work among zones and merge results at consolidation.  **Acceptance:** No order marked ready until all zones complete.

### EV-135 | Put-wall / put-to-light

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S19], [S18].

**Requirement:** Sort a batch to cubbies or light-directed locations.  **Acceptance:** A wrong cubby produces an actionable alert.

### EV-136 | Pick-to-carton

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S19].

**Requirement:** Direct picks straight into designated outbound cartons.  **Acceptance:** Carton contents reconcile with packed contents.

### EV-137 | Full pallet and case picks

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S10].

**Requirement:** Support handling whole case/pallet without individual each scans.  **Acceptance:** Movement conserves base-unit quantities.

### EV-138 | Pick path optimization

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S19], [S10].

**Requirement:** Sort pick stops to reduce travel while respecting equipment paths.  **Acceptance:** Generated route improves or equals baseline on test layout.

### EV-139 | FEFO/FIFO selection enforcement

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S27].

**Requirement:** Prefer correct stock age/expiry and enforce when required.  **Acceptance:** Expired or wrong-lot pick is blocked with reason.

### EV-140 | Voice picking interface

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S01], [S10].

**Requirement:** Enable hands-free guided prompts on supported devices.  **Acceptance:** Confirmation logs exact pick with no duplicate posting.

### EV-141 | Wearable scanner support

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S22].

**Requirement:** Support configured glove scanners and scan feedback.  **Acceptance:** Unreliable radio retries never duplicate stock moves.

### EV-142 | Pick productivity and replenishment coupling

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S19].

**Requirement:** Trigger replenishment when pick face becomes insufficient.  **Acceptance:** Picking task blocks rather than silently shorting demand.

### EV-143 | Re-pick and reversal process

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22].

**Requirement:** Reverse errors through permissioned compensating transactions.  **Acceptance:** Original pick remains traceable and stock consistent.

## 5.11 Packing, handling units and VAS (12 capabilities)

Packages and pallets are real warehouse objects, not just printable shipping files. **Benchmark references:** [S01], [S08], [S14], [S19], [S21].

### EV-144 | Carton and pallet handling units

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S31].

**Requirement:** Track package identity, type, hierarchy and current location.  **Acceptance:** A pallet's contents remain queryable after a move.

### EV-145 | Packing station queue

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S19].

**Requirement:** Show picked orders and available packing benches.  **Acceptance:** Packing begins only when required pick work is complete.

### EV-146 | Scan-to-pack verification

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S25], [S18].

**Requirement:** Scan picked items into cartons, track short/over pack.  **Acceptance:** Carton contents reconcile with order lines.

### EV-147 | Multi-carton order support

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S21].

**Requirement:** Split an order into many cartons and track each independently.  **Acceptance:** Pack quantities sum to order shipped quantities.

### EV-148 | Nested handling unit hierarchy

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S31].

**Requirement:** Allow items in cartons, cartons on pallets, pallets in staging.  **Acceptance:** A unit cannot belong to two parents simultaneously.

### EV-149 | Cartonization suggestion

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S19].

**Requirement:** Choose carton based on dimensions, weight and fragility rules.  **Acceptance:** Recommendation never exceeds physical capacity.

### EV-150 | Dunnage and material tracking

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S22].

**Requirement:** Record cartons, bags, tape, inserts and costs per package.  **Acceptance:** Materials update supplies ledger if configured.

### EV-151 | Packing slips and custom documents

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S19].

**Requirement:** Generate document templates per account and service.  **Acceptance:** Reprinted documents have stable source revision.

### EV-152 | GS1 SSCC pallet label

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S31], [S14].

**Requirement:** Generate logistic-unit IDs and compliant label fields for authorized prefixes.  **Acceptance:** Check digit valid and duplicate ID prohibited.

### EV-153 | Weight scale confirmation

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S19], [S22].

**Requirement:** Capture measured package weight and flag variance.  **Acceptance:** Weight mismatch pauses release for review.

### EV-154 | Kitting and bundle assembly

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S21].

**Requirement:** Consume component stock and create traceable assembled item.  **Acceptance:** Each kit build balances source and output quantities.

### EV-155 | Value-added service work orders

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S10].

**Requirement:** Track relabeling, bundling, gift wrap, inspection and rework.  **Acceptance:** VAS task can generate appropriate billable event.

## 5.12 Shipping and dispatch (15 capabilities)

Outbound fulfillment is incomplete until actual packed goods are tendered and audited. **Benchmark references:** [S08], [S14], [S15], [S19], [S22].

### EV-156 | Shipment record lifecycle

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S08], [S22].

**Requirement:** Track created, staged, ready, manifested, loaded and shipped states.  **Acceptance:** Shipped requires evidence of complete accepted quantities.

### EV-157 | Carrier service selection

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S19].

**Requirement:** Choose carrier and service by speed, weight and constraints.  **Acceptance:** Selection is stored with estimated and final cost.

### EV-158 | Multi-carrier rate shopping

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S16].

**Requirement:** Compare eligible provider rates using live credentials.  **Acceptance:** Chosen rate and unavailable provider errors are auditable.

### EV-159 | Parcel labels and tracking IDs

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S15].

**Requirement:** Request printable label, store tracking and label revision.  **Acceptance:** Retry never buys an unintended second label.

### EV-160 | Carrier manifest and closeout

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S19].

**Requirement:** Close packages by manifest or end-of-day handoff.  **Acceptance:** Manifest totals reconcile with recorded packages.

### EV-161 | Address verification

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S18].

**Requirement:** Validate destination before rate purchase and print.  **Acceptance:** Invalid address forces correction or approval.

### EV-162 | Staging lanes by dock and carrier

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S22].

**Requirement:** Assign scanned packed units to staging zone.  **Acceptance:** Unit cannot be loaded from the wrong lane unnoticed.

### EV-163 | Scan-to-load confirmation

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S01], [S22].

**Requirement:** Verify HUs against truck or shipment at dock.  **Acceptance:** Shipment closes only with correct loaded IDs.

### EV-164 | Load plan and trailer capacity

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S08], [S12].

**Requirement:** Assign pallets to loads using weight/cube restrictions.  **Acceptance:** Capacity limits show explicit infeasibility.

### EV-165 | Bill of lading and retail documents

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S19], [S14].

**Requirement:** Produce BOL, packing list, ASN/EDI docs when applicable.  **Acceptance:** Document totals reconcile with loaded contents.

### EV-166 | Proof of delivery integration

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S29].

**Requirement:** Store recipient signature/event from authorized driver or carrier.  **Acceptance:** POD is linked to immutable shipment record.

### EV-167 | Shipment exception management

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S08], [S19].

**Requirement:** Handle short, damaged, carrier error and late cutoff.  **Acceptance:** Shipment status reflects unresolved exception.

### EV-168 | Partial shipment and backorder

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S08], [S21].

**Requirement:** Ship available portion while preserving open balance.  **Acceptance:** No duplicate reservation or delivery on re-run.

### EV-169 | Shipping cost and margin analytics

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S16].

**Requirement:** Track cost per parcel/line/customer/channel.  **Acceptance:** Reports show which costs are estimates versus billed.

### EV-170 | Tracking sync and notifications

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S18], [S19].

**Requirement:** Publish tracking events and customer communications.  **Acceptance:** Duplicate carrier webhook does not duplicate events.

## 5.13 Returns and reverse logistics (10 capabilities)

Advanced returns make condition, ownership and disposition explicit. **Benchmark references:** [S01], [S08], [S21], [S27].

### EV-171 | Restock confirmed customer returns

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S21], [S27].

**Requirement:** Preserve current return intake limited to confirmed resellable units.  **Acceptance:** Duplicate return reference never restocks twice.

### EV-172 | RMA authorization

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S08].

**Requirement:** Create expected return, reason and return labels before arrival.  **Acceptance:** Only authorized qty can be returned without exception.

### EV-173 | Return receiving scan

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S27].

**Requirement:** Scan returned serial/lot/product and inspect condition.  **Acceptance:** Return ID ties item to original order if available.

### EV-174 | Condition grading

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S27].

**Requirement:** Classify new, resellable, damaged, refurbish, scrap and vendor return.  **Acceptance:** Only released units increase sellable inventory.

### EV-175 | Quarantine by default

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S22].

**Requirement:** Hold unknown-condition returns until inspected.  **Acceptance:** Uninspected return cannot fulfill a customer order.

### EV-176 | Rework and refurbishment tasks

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S10].

**Requirement:** Generate traceable repair, repack and retest workflow.  **Acceptance:** Disposition records before/after state and costs.

### EV-177 | Supplier return (RTV)

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S21].

**Requirement:** Create return-to-vendor shipment with stock and claim reference.  **Acceptance:** Inventory leaves warehouse only on verified issue.

### EV-178 | Customer refund link

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S08].

**Requirement:** Connect return disposition to approved external financial action.  **Acceptance:** Refund is never initiated solely by warehouse scan.

### EV-179 | Recall and bulk reverse logistics

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S21].

**Requirement:** Locate impacted packages and return flow for affected lots.  **Acceptance:** Affected stock is held consistently network-wide.

### EV-180 | Returns analytics

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S08], [S15].

**Requirement:** Track reasons, damages, recovery and restock time.  **Acceptance:** Metrics reconcile to actual RMA and receipt records.

## 5.14 3PL customer operations and billing (17 capabilities)

A 3PL WMS manages inventory on behalf of separate customer owners, with accurate charge capture. **Benchmark references:** [S10], [S13], [S15], [S16], [S18].

### EV-181 | 3PL customer accounts

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S18].

**Requirement:** Create inventory-owner entities under each warehouse operator tenant.  **Acceptance:** One owner cannot read or allocate another owner's SKU.

### EV-182 | Customer-specific warehouses and zones

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S10].

**Requirement:** Reserve or share locations by agreement and owner rules.  **Acceptance:** Shared bins retain ownership at every unit level.

### EV-183 | Customer portal inventory

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S16], [S18].

**Requirement:** Expose scoped balances, lots, locations and order status.  **Acceptance:** Customer never sees competing client records.

### EV-184 | Customer portal order creation

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S16], [S18].

**Requirement:** Allow approved clients to submit orders with service rules.  **Acceptance:** Portal order uses same validation as WMS order.

### EV-185 | Service catalog and rate cards

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S16].

**Requirement:** Define billable services and rates per customer and effective date.  **Acceptance:** Rate version applied at event time is immutable.

### EV-186 | Storage billing by pallet/day

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S16].

**Requirement:** Accrue occupied pallet positions or units daily.  **Acceptance:** Accrual reconciles with location and inventory snapshots.

### EV-187 | Receiving transaction charges

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S16].

**Requirement:** Bill by pallet, carton, unit or hour according to contract.  **Acceptance:** One physical receipt emits only intended charge once.

### EV-188 | Pick, pack and VAS event billing

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S18].

**Requirement:** Capture verified execution events with rate and quantity.  **Acceptance:** Partial/failed tasks do not produce completed-task charge.

### EV-189 | Minimums and recurring fees

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S15].

**Requirement:** Handle minimum monthly spend, account fee and thresholds.  **Acceptance:** Recompute invoice deterministically with rate versions.

### EV-190 | Carrier markup and pass-through

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S16], [S18].

**Requirement:** Record freight cost, customer charge and permitted markup.  **Acceptance:** Client invoice reveals contractual price behavior.

### EV-191 | Billing dispute and adjustments

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15].

**Requirement:** Provide audited credit, waiver and dispute workflow.  **Acceptance:** Original charge retained after correction.

### EV-192 | Invoice generation and tax handoff

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S17].

**Requirement:** Create reviewed draft invoice and export to accounting.  **Acceptance:** Reconciliation shows each line's originating work event.

### EV-193 | EDI retail routing compliance

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S15], [S18].

**Requirement:** Map clients' trading partner label and order requirements.  **Acceptance:** EDI failure cannot be silently marked successful.

### EV-194 | Client contract and SLA reporting

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S13].

**Requirement:** Report inbound, fulfillment and accuracy metrics by client.  **Acceptance:** Report data never crosses client ownership.

### EV-195 | Custom branded labels and slips

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S15], [S18].

**Requirement:** Apply customer-specific document templates.  **Acceptance:** Brand selection keyed to inventory owner not staff choice.

### EV-196 | Client visibility notifications

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S16], [S18].

**Requirement:** Send configured stock, backlog, receipt and shipment updates.  **Acceptance:** Each notification has tenant-owner isolation and retry log.

### EV-197 | Multi-currency and invoice integration

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S15], [S17].

**Requirement:** Support explicit currency and tax settings via accounting provider.  **Acceptance:** Totals round deterministically and distinguish currencies.

## 5.15 Labor, resources and shift control (12 capabilities)

Managers require visibility of who should do what, what is blocked and why a shift is falling behind. **Benchmark references:** [S02], [S03], [S05], [S10], [S13].

### EV-198 | Worker availability and shift roster

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S13].

**Requirement:** Record assigned shifts, zone, skill and equipment availability.  **Acceptance:** Task assignment respects availability and permissions.

### EV-199 | Labor task clock events

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S13].

**Requirement:** Capture start, pause, resume, and finish work time.  **Acceptance:** Total effective time excludes configured breaks.

### EV-200 | Task skill matrix

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S12].

**Requirement:** Model forklift, hazardous goods and restricted zone skills.  **Acceptance:** Unsafe task assignment fails policy check.

### EV-201 | Resource and equipment registry

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S05], [S12].

**Requirement:** Track pallet jacks, forklifts, scanner and robot assignments.  **Acceptance:** Unavailable asset cannot be assigned to simultaneous tasks.

### EV-202 | Worker-directed task prioritization

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S22].

**Requirement:** Sort by due time, travel, capability and warehouse policy.  **Acceptance:** Reason for chosen next task is visible to supervisor.

### EV-203 | Labor engineered standards

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S13].

**Requirement:** Configure expected time by travel, piece, case and exceptions.  **Acceptance:** Actual vs standard report uses correct task classes.

### EV-204 | Team and worker productivity

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S10], [S13].

**Requirement:** Track picks per hour, errors, utilization and travel with context.  **Acceptance:** KPI excludes downtime and avoids unsafe quotas by design.

### EV-205 | Shift launch dashboard

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S07].

**Requirement:** Show forecasted workload, headcount gap and priority work.  **Acceptance:** Inputs and forecast error visible to supervisors.

### EV-206 | Labor forecast intraday

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S07].

**Requirement:** Predict shift workload based on orders and arrivals.  **Acceptance:** Forecast is backtested with confidence and override.

### EV-207 | Exception supervisor control room

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S02], [S22].

**Requirement:** Show blocked pick, receive, load and count work in one queue.  **Acceptance:** Every alert links to record and actionable resolution.

### EV-208 | Worker training and certification

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S13], [S22].

**Requirement:** Track approved skills, SOP revisions and acknowledgement.  **Acceptance:** Unsafe or untrained workers denied restricted operations.

### EV-209 | Operator ergonomics and accessibility

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22], [S13].

**Requirement:** Offer large scan targets, audible/visual feedback and accessible flows.  **Acceptance:** Critical flow usable with scanner and keyboard.

## 5.16 Yard, docks and transportation (10 capabilities)

Enterprise users expect coordination between truck arrivals, dock door capacity and warehouse work. **Benchmark references:** [S01], [S08], [S10], [S12], [S22].

### EV-210 | Dock door and resource directory

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S10].

**Requirement:** Define door capabilities, operating hours and receiving/shipping type.  **Acceptance:** Incompatible trailer cannot be assigned to door.

### EV-211 | Dock appointment scheduler

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S10].

**Requirement:** Schedule carrier slots and expected load volume.  **Acceptance:** Double bookings trigger explicit conflict.

### EV-212 | Driver, trailer and vehicle check-in

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S12], [S22].

**Requirement:** Record actual arrival, appointment and physical trailer ID.  **Acceptance:** Check in links to inbound/outbound load.

### EV-213 | Yard position tracking

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S12].

**Requirement:** Track trailer in gate, yard slot, dock and departed.  **Acceptance:** Trailer occupancy map matches events.

### EV-214 | Trailer seal verification

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S12].

**Requirement:** Record seal checks and exceptions at unload/load.  **Acceptance:** Seal variance blocks release pending sign-off.

### EV-215 | Door utilization dashboard

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S22].

**Requirement:** Show planned vs actual door occupancy and idle time.  **Acceptance:** KPIs have correct scheduled/actual denominators.

### EV-216 | Dock-to-task coordination

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S08], [S22].

**Requirement:** Open unload or staging tasks when appropriate arrival is checked in.  **Acceptance:** Wrong shipment cannot auto-trigger a receiving task.

### EV-217 | Cross-dock lane planning

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S08].

**Requirement:** Reserve staging slots for immediate outbound demand.  **Acceptance:** Inbound and outbound linkage visible in real time.

### EV-218 | Transportation load tender status

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S08], [S29].

**Requirement:** Capture booked, dispatched and tendered freight outcomes.  **Acceptance:** Failed tender does not show shipped.

### EV-219 | Yard alert and detention exposure

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S12], [S29].

**Requirement:** Alert on trailer dwell time and missed dock slots.  **Acceptance:** Dwell reports distinguish carrier vs warehouse delay.

## 5.17 Automation, equipment and digital workers (11 capabilities)

Automation is optional yet needs safe interoperability, observability and failure handling from day one of design. **Benchmark references:** [S01], [S05], [S06], [S12], [S14], [S22].

### EV-220 | Robotics integration gateway

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S01], [S05].

**Requirement:** Use vendor-neutral command and event adapter for AMRs.  **Acceptance:** Adapter failure leaves reversible WMS task state.

### EV-221 | Conveyor and sorter integration

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S12], [S22].

**Requirement:** Exchange material flow events with WCS/MHE safely.  **Acceptance:** Messages are ordered or idempotently reconciled.

### EV-222 | Automated storage retrieval interface

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S01], [S12].

**Requirement:** Send retrieval requests and handle equipment exceptions.  **Acceptance:** Unavailable device does not lose reserved inventory.

### EV-223 | Pick-to-light interface

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S14], [S18].

**Requirement:** Show and confirm pick quantities on supported hardware.  **Acceptance:** Misconfirmed quantity is traceable to pick task.

### EV-224 | Voice-directed workflow adapter

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S01], [S10].

**Requirement:** Convert WMS tasks to voice instruction and confirmation.  **Acceptance:** Every accepted voice command performs validated task step.

### EV-225 | Scale, dimensioner and print services

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S22].

**Requirement:** Capture validated measurements and printer job results.  **Acceptance:** Device data has timestamp, unit and source identity.

### EV-226 | RFID portal event processing

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S02], [S19].

**Requirement:** Deduplicate reads and corroborate physical movement events.  **Acceptance:** Repeated tag reads do not create phantom shipments.

### EV-227 | Offline-first handheld queue

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S22].

**Requirement:** Allow safe local step capture during short network interruptions.  **Acceptance:** Reconnection replays without duplicate stock changes.

### EV-228 | Automation simulator and digital twin

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S12], [S10].

**Requirement:** Test bottlenecks and equipment events using synthetic orders.  **Acceptance:** Simulation never modifies production stock.

### EV-229 | Manual override and failsafe

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S12], [S22].

**Requirement:** Offer permissioned emergency stop and alternate manual execution.  **Acceptance:** System recovers from robot outage without double execution.

### EV-230 | Equipment failure event monitoring

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S05], [S12].

**Requirement:** Classify faults and reroute tasks to manual queues.  **Acceptance:** Active stock and task ledgers remain consistent.

## 5.18 Dashboards, analytics and operational intelligence (16 capabilities)

The command center should display live actionable facts, not disconnected decorative tiles. **Benchmark references:** [S02], [S05], [S07], [S13], [S16], [S22].

### EV-231 | Basic overview KPIs and seven-day planning

**Elveriq:** Partial  |  **Priority:** P1  |  **References:** [S13], [S22].

**Requirement:** Preserve current aggregate counts and simple queue.  **Acceptance:** KPIs reconcile to current orders and stock ledger.

### EV-232 | Open task operational command center

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S02], [S22].

**Requirement:** Show work by stage, SLA, warehouse and owner with drill-down.  **Acceptance:** Every card opens a correctly filtered action list.

### EV-233 | Inbound receiving performance

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S13], [S16].

**Requirement:** Monitor ASN compliance, dwell, discrepancies and receipts per hour.  **Acceptance:** Numbers reconcile with posted receiving work.

### EV-234 | Outbound throughput and backlog

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S14], [S19].

**Requirement:** Track orders due, late, lines picked, packed and shipped.  **Acceptance:** Status filters match immutable shipment events.

### EV-235 | Inventory accuracy by count cycle

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S13], [S24].

**Requirement:** Show variance count, value, SKU and location scope.  **Acceptance:** Accurate denominators and exclusions documented.

### EV-236 | Labor productivity dashboards

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S10].

**Requirement:** Show tasks/hour, pick errors and utilization with context.  **Acceptance:** No fabricated utilization when time clock unavailable.

### EV-237 | Warehouse space utilization

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S07], [S10].

**Requirement:** Measure occupied positions and cube by zone and aisle.  **Acceptance:** Aggregate reconciles with bin occupancy.

### EV-238 | Cost-to-serve by customer

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S13], [S15].

**Requirement:** Calculate work minutes, packaging and freight expense by client.  **Acceptance:** Costs link to billable events and actual resources.

### EV-239 | Client 3PL billing dashboards

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S16].

**Requirement:** Show unbilled work, invoice amount and disputes.  **Acceptance:** Charges can be traced to verified operations.

### EV-240 | SLA breach prediction

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S05], [S07].

**Requirement:** Flag likely missed cutoffs using remaining work and capacity.  **Acceptance:** Every prediction includes risk driver and historical precision.

### EV-241 | Alert routing and escalation

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S02], [S22].

**Requirement:** Route operational exceptions by shift and urgency.  **Acceptance:** Alert acknowledgement and resolution are auditable.

### EV-242 | Custom report builder

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S13], [S16].

**Requirement:** Enable safe curated dimensions and exports by role.  **Acceptance:** Cross-tenant joins are impossible in generated queries.

### EV-243 | Scheduled exports

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S16], [S21].

**Requirement:** Send approved report via scoped link or destination.  **Acceptance:** Exports honor role, audit and retention policy.

### EV-244 | Network-wide multiwarehouse view

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S03], [S20].

**Requirement:** Roll up facilities while preserving drilldown and owner filter.  **Acceptance:** Totals equal sum of selected sites.

### EV-245 | Near-real-time dashboard updates

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S22].

**Requirement:** Push or poll new events with freshness indicator.  **Acceptance:** User can distinguish stale sync from zero activity.

### EV-246 | KPI definition catalog

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S13], [S35].

**Requirement:** Document formulas, units, timezone, cutoffs and source tables.  **Acceptance:** Each KPI has automated reconciliation test.

## 5.19 AI, optimization and decision support (11 capabilities)

AI belongs on top of reliable event data and must be measurable, explainable and reversible. **Benchmark references:** [S03], [S05], [S07], [S09], [S11], [S38].

### EV-247 | Slotting ABC recommendations

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S05], [S21].

**Requirement:** Recommend fast movers near shipping and maintain constraints.  **Acceptance:** Recommendations disclose input velocity and constraints.

### EV-248 | Slotting heatmap

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S07].

**Requirement:** Show travel time and slot deviation over facility map.  **Acceptance:** Heatmap is supported by actual paths and timestamps.

### EV-249 | Picker route optimizer

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S19].

**Requirement:** Suggest sequence minimizing weighted travel under zone rules.  **Acceptance:** Route is benchmarked against simple serpentine baseline.

### EV-250 | Workload and shift forecast

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S07].

**Requirement:** Forecast expected line/task volumes from recent actual arrivals.  **Acceptance:** Backtest includes mean absolute error and coverage.

### EV-251 | Dynamic labor rebalancing

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S05], [S07].

**Requirement:** Suggest staff reassignment during bottlenecks.  **Acceptance:** Supervisor can accept, reject and audit suggestion.

### EV-252 | Warehouse operations assistant

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S05], [S09].

**Requirement:** Answer natural-language questions with linked source records.  **Acceptance:** Assistant never executes write operation without confirmation.

### EV-253 | Explainable wave advisor

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S09], [S11].

**Requirement:** Analyze wave failure and recommend alternative grouping.  **Acceptance:** Advice identifies measured cause and forecast impact.

### EV-254 | Replenishment forecast suggestions

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S21], [S07].

**Requirement:** Estimate shortfalls and proposed reorder quantities.  **Acceptance:** Model performance compared with threshold baseline.

### EV-255 | Anomaly detection in stock movements

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S05], [S07].

**Requirement:** Flag unusual adjustments, inventory shrink or repeated short picks.  **Acceptance:** Alerts show evidence and false positive tracking.

### EV-256 | Capacity and simulation workbench

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S12], [S07].

**Requirement:** Simulate shift workload, resources, picking policies and peak days.  **Acceptance:** Sandbox results cannot alter real order state.

### EV-257 | Guardrails and AI evaluation registry

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S05], [S09].

**Requirement:** Track prompt/tool policy, version, evaluation and human approval.  **Acceptance:** No unapproved model output changes inventory.

## 5.20 Integrations, APIs and interoperability (16 capabilities)

Modern WMS must fit into customers existing ERP, e-commerce and carrier infrastructure. **Benchmark references:** [S01], [S08], [S15], [S18], [S19], [S22].

### EV-258 | Tenant-scoped REST API

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S15], [S17].

**Requirement:** Extend existing APIs with documented scopes, versions and pagination.  **Acceptance:** Auth and tenant boundary tests pass on all resources.

### EV-259 | API keys OAuth and scopes

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S18].

**Requirement:** Issue rotating credentials with fine-grained least privilege.  **Acceptance:** Revoked token cannot access warehouse APIs.

### EV-260 | Inbound webhooks

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S18], [S19].

**Requirement:** Accept signed events from connected systems with replay protection.  **Acceptance:** Duplicate webhook is idempotently processed.

### EV-261 | Outbound webhooks and outbox

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S15], [S22].

**Requirement:** Publish inventory and order events only after commit.  **Acceptance:** Retry and reconnect cannot lose or duplicate state.

### EV-262 | Integration job monitoring

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S17], [S22].

**Requirement:** Track sync offset, errors, rate limits and retry DLQ.  **Acceptance:** Failed messages are visible and safely replayable.

### EV-263 | Shopify integration

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S18], [S20].

**Requirement:** Ingest authorized orders and publish inventory on chosen source-of-truth rules.  **Acceptance:** Repeated shop updates cannot create negative stock.

### EV-264 | Amazon marketplace integration

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S18], [S19].

**Requirement:** Use authorized marketplace APIs for orders and shipping data.  **Acceptance:** External IDs and cutoff rules are recorded.

### EV-265 | TikTok and other channels

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S18].

**Requirement:** Offer modular channel connector with normalized events.  **Acceptance:** Connector can be disabled without stopping core WMS.

### EV-266 | QuickBooks accounting connector

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S15], [S17].

**Requirement:** Export approved invoices or purchasing accounting entries.  **Acceptance:** Financial and inventory totals reconcile by reference.

### EV-267 | NetSuite/ERP connector

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S18], [S22].

**Requirement:** Synchronize item master, POs, orders and receipts with ownership rules.  **Acceptance:** No infinite echo loop between systems.

### EV-268 | EDI 850 856 940 945 846 mapping

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S15], [S18].

**Requirement:** Support trading-partner profiles and controlled translation.  **Acceptance:** Test documents validate partner requirements and acknowledgements.

### EV-269 | Carrier and postal APIs

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S14], [S19].

**Requirement:** Integrate labels, rates, tracking, void and manifests.  **Acceptance:** Provider failure is retry-safe and observable.

### EV-270 | GS1 and barcode parsing

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S21], [S31].

**Requirement:** Parse configured GS1 application identifiers with validation.  **Acceptance:** GTIN, lot, date and SSCC are not confused.

### EV-271 | Print and document service

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S22], [S14].

**Requirement:** Template ZPL/PDF labels by printer and package type.  **Acceptance:** Label generation is idempotent and document audit stored.

### EV-272 | Bulk data import and export

**Elveriq:** Partial  |  **Priority:** P1  |  **References:** [S16], [S21].

**Requirement:** Extend existing CSV tools to map, preview, reconcile and undo.  **Acceptance:** Import rejects malformed rows with error workbook/report.

### EV-273 | Partner integration sandbox

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S15], [S22].

**Requirement:** Provide test tokens, sample payloads, status page and docs.  **Acceptance:** Test callbacks never touch production tenant inventory.

## 5.21 Security, reliability and operational governance (17 capabilities)

A high-feature-count prototype is not a trustworthy WMS until financial and physical transactions survive real conditions. **Benchmark references:** [S22], [S32], [S33].

### EV-274 | Tenant authorization regression suite

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S32].

**Requirement:** Extend tested tenant scoping to every new endpoint and parent-child reference.  **Acceptance:** IDOR and privilege escalation tests fail closed.

### EV-275 | PostgreSQL transaction validation

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S22].

**Requirement:** Run concurrent reserve, receipt, transfer and picking tests on PostgreSQL.  **Acceptance:** Race tests preserve invariants under retries and crashes.

### EV-276 | Versioned schema migrations

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S22].

**Requirement:** Use Alembic forward and backward versioned migrations.  **Acceptance:** Deploy and rollback tested from previous release.

### EV-277 | Backup and point-in-time recovery

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S22].

**Requirement:** Schedule encrypted backups and perform restore drills.  **Acceptance:** Defined RPO/RTO demonstrated in timed test.

### EV-278 | Structured audit events

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S21], [S32].

**Requirement:** Record stock actions, roles, actor, reason and correlation ID.  **Acceptance:** Auditor can reconstruct who changed inventory and when.

### EV-279 | Rate limiting and abuse prevention

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S32].

**Requirement:** Limit login, exports, automation calls and bulk writes.  **Acceptance:** Abusive request pattern is blocked and audited.

### EV-280 | Encryption and secret governance

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S33].

**Requirement:** Protect secrets, sensitive fields and TLS in all environments.  **Acceptance:** Keys rotate and no secret appears in logs.

### EV-281 | Session revocation and MFA

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S33].

**Requirement:** Provide administrator invalidation and step-up for high-risk actions.  **Acceptance:** Revoked tokens remain unusable across devices.

### EV-282 | Monitoring and alerting

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S22].

**Requirement:** Record uptime, traces, errors, queue lag and inventory anomalies.  **Acceptance:** Operational pages identify failing job and affected tenant.

### EV-283 | Disaster recovery game day

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22].

**Requirement:** Practice restore, worker failover and data reconciliation.  **Acceptance:** Recovery produces documented actual downtime and data loss.

### EV-284 | Idempotency on stock mutations

**Elveriq:** Partial  |  **Priority:** P0  |  **References:** [S22].

**Requirement:** Generalize transfer retry rules to receiving, picks, webhooks and shipments.  **Acceptance:** Same idempotency key never executes physical transaction twice.

### EV-285 | Event outbox and dead-letter jobs

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22].

**Requirement:** Atomically persist events and deliver with safe retries.  **Acceptance:** Fault injection does not lose committed event.

### EV-286 | Audit retention and privacy policy

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S32], [S33].

**Requirement:** Set data retention, export, deletion and tenant offboarding rules.  **Acceptance:** Policies have tested access and redaction behavior.

### EV-287 | Least-privilege and security review

**Elveriq:** Gap  |  **Priority:** P0  |  **References:** [S32], [S33].

**Requirement:** Review API permissions and isolate roles, DB and queues.  **Acceptance:** Independent findings resolved before production pilot.

### EV-288 | Load and large-order performance

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S22].

**Requirement:** Benchmark realistic SKU counts, multi-line orders, concurrent scanners.  **Acceptance:** Service targets met with documented workload.

### EV-289 | Feature rollback and safe rollout

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S03], [S22].

**Requirement:** Use migration-safe rollout flags and recovery playbooks.  **Acceptance:** A disabled feature neither loses data nor breaks core workflow.

### EV-290 | Operational support and change history

**Elveriq:** Gap  |  **Priority:** P1  |  **References:** [S16], [S22].

**Requirement:** Provide ticket-linked audit, incident status and release notes.  **Acceptance:** Support can investigate without impersonating clients.

## 5.22 Vertical specializations and optional extensions (10 capabilities)

Do not imply sector-specific regulatory compliance merely because a generic tracking feature exists. **Benchmark references:** [S01], [S08], [S13], [S22], [S34].

### EV-291 | Food lot traceability and recall exports

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S34], [S01].

**Requirement:** For applicable customers capture traceability events and lot genealogy.  **Acceptance:** Export matches configured critical event and element rules.

### EV-292 | FEFO and shelf-life customer policy

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S21], [S27].

**Requirement:** Apply minimum shelf life per customer and order destination.  **Acceptance:** Picking refuses lot with insufficient remaining days.

### EV-293 | Pharma serial verification adapter

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S13], [S01].

**Requirement:** Design serial and event boundaries for regulated supply chains.  **Acceptance:** Do not claim DSCSA compliance before legal/partner validation.

### EV-294 | Cold chain monitoring integration

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S13], [S22].

**Requirement:** Capture device evidence and hold affected inventory on excursions.  **Acceptance:** Exception cannot be auto-cleared without rule and approver.

### EV-295 | Manufacturing raw material staging

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S01], [S08].

**Requirement:** Direct materials to production lines with lot traceability.  **Acceptance:** Consumption and return reconcile with warehouse stock.

### EV-296 | Kitting to stock and to order

**Elveriq:** Gap  |  **Priority:** P2  |  **References:** [S01], [S10].

**Requirement:** Support component pick, assembly and serial association.  **Acceptance:** Finished kits trace to exact source components.

### EV-297 | Wholesale customer pallet labels

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S14], [S31].

**Requirement:** Support retailer-compliant logistics labels and shipping documentation.  **Acceptance:** Required label data validates before print.

### EV-298 | Heavy/oversized item putaway

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S13], [S10].

**Requirement:** Restrict equipment routes, floor bins and loading techniques.  **Acceptance:** Oversize task requires suitable resource and location.

### EV-299 | Apparel style color size matrix

**Elveriq:** Gap  |  **Priority:** P3  |  **References:** [S10], [S21].

**Requirement:** Support variant attribute hierarchy and bulk order interfaces.  **Acceptance:** Search and exports preserve variant identity.

### EV-300 | Hazmat operational flags

**Elveriq:** Gap  |  **Priority:** P4  |  **References:** [S15], [S22].

**Requirement:** Represent customer rules, segregated storage and shipping constraints.  **Acceptance:** No safety/regulatory certification claim without expert review.

# 6. End-to-end reference process blueprints

The sequences below are operational design hypotheses inspired by the WMS sources. They are not direct descriptions of any one vendor's proprietary internal process. Every step must be traceable to a tenant and warehouse, actor/system, physical unit and auditable time.

## 6.1 Supplier-to-shelf: purchase order to available bin

**Trigger:** approved PO or advance shipping notice expects 120 cartons at Facility A. **Sequence:** appointment check-in (if enabled) -> receive work created -> dock staging lane selected -> cartons/HUs scanned -> received quantities, lots and serials verified -> shortages/damage exceptions captured -> quality holds separated -> putaway rules propose valid bin -> worker scans carton/HU and destination bin -> physical location movement posted -> inventory becomes available according to quality disposition -> dashboards and customer/ERP integration events update. **Critical failure branches:** duplicate scan, overreceipt tolerance, invalid SKU alias, full bin, wrong lot, expired item, Wi-Fi loss. **Acceptance:** no unit appears as available before the required receive/inspection/putaway conditions; quantity in all bins plus staging reconciles with receipt ledger and transfers. [S01, S10, S14, S15, S21, S25]

## 6.2 Order-to-truck: order import to carrier handoff

**Trigger:** retail or e-commerce order arrives with ship-by cutoff. **Sequence:** ingest/dedupe -> validate item/customer/channel -> allocate eligible inventory by owner, lot/expiry and location -> create work request -> choose single/batch/wave/cluster/zone strategy -> assign tasks -> scan source bin/item/qty -> resolve short pick or replenishment -> direct picked HUs to pack station -> scan to pack cartons -> compute weight/labels/carrier service -> create shipment -> stage at correct dock -> scan cartons/pallets onto load -> confirm departure -> transmit tracking/ASN/EDI if configured. **Failure branches:** order hold after wave release, shortage, wrong carton, printer failure, carrier API timeout, missing loaded pallet. **Acceptance:** order quantity = shipped + explicitly unshipped/backordered/cancelled quantities; all shipped units have a chain of custody through the task and HU ledger. [S08, S14, S18, S19, S22, S26]

## 6.3 Cycle count without corrupting active stock

**Trigger:** ABC count plan, exception short pick or supervisor request. **Sequence:** choose bin/products -> select snapshot/freeze policy -> issue blind count task -> worker scans correct location, lot and quantity -> detect overlapping moves -> review threshold variance -> supervisor posts authorized adjustment -> create immutable ledger entry -> update count accuracy KPI. **Failure:** simultaneous pick or receive changes on-hand after snapshot. **Acceptance:** no stale count overwrites current stock, and no negative available stock is introduced. Preserve Elveriq's existing aggregate stale-snapshot protection but adapt it to each location balance. [S21, S24, S25, S27]

## 6.4 3PL client order plus charge capture

**Trigger:** Client B (inventory owner) submits order using portal/API. **Sequence:** validate client permissions -> resolve client SKU aliases -> allocate only B-owned inventory -> pick, pack, label, ship -> emit verified billable events for unit/case handling, packaging, storage days and VAS -> rate through effective contract -> review invoice -> export to accounting -> show shipment, stock and charges to B portal only. **Critical risk:** physically commingled identical SKUs for different owners. **Acceptance:** cross-client read and allocation tests deny access; identical actions replayed cannot generate duplicate billable lines. [S10, S15, S16, S18]

## 6.5 Recall and quarantine

**Trigger:** vendor or customer flags impacted lot. **Sequence:** identify affected lots/serials -> find all warehouse bins, HUs, orders and shipped customers -> block current inventory -> stop unfinished picks and pack/load release -> export relevant trace results -> initiate approved return/destruction/rework -> preserve event-level evidence. **Acceptance:** confirmed affected stock cannot be allocated while held; released and shipped lineage remain reconstructable. Sector-specific trace requirements are customer- and jurisdiction-dependent; legal advice is needed before compliance claims. [S01, S21, S34]

## 6.6 3PL seasonal peak shift

**Trigger:** demand doubles ahead of a cutoff. **Sequence:** receive order forecast and due lanes -> surface work by cutoff, location, skills and equipment -> supervisor changes priorities -> select appropriate wave/batch release -> task router assigns work -> dashboard shows blocker/replenishment and labor deviations -> supervisor resolves exceptions -> after shift, report actual travel, throughput, on-time performance and rate of errors. **Acceptance:** replan preserves all original order commitments and explains changed assignments. AI advice is optional and must not auto-post inventory. [S03, S05, S07, S10, S11]

# 7. User experience and application map

Avoid a vast cluttered navigation menu. Expose a role-based workspace. Desktop supervisor applications and scanner worker applications are different interfaces sharing the same tasks and posting services.

| Persona | Primary workspace | Essential actions and evidence |
|:--|:--|:--|
| Business owner / administrator | Business console | Onboarding, facilities, staff, subscription/contract, integration, KPI, audit |
| Warehouse operations manager | Operations command center | Backlog, due shipments, blocked work, productivity, inventory accuracy, task assignment |
| Receiving worker | Inbound handheld / tablet | ASN/PO lookup, scan, inspect, print HU, directed putaway, photo exception |
| Forklift / putaway operator | Material-movement handheld | Assigned HU moves, destination scans, replenishment, blocked task resolution |
| Picker | Pick handheld | Next task, source bin, item/lot, exact qty, tote, short pick, route |
| Packer | Packing workstation | Order/tote scan, cartonize, scale, QC, labels, release to staging |
| Shipping lead | Dispatch console | Staging lanes, load scans, manifests, BOL, exceptions, departure |
| Inventory controller | Stock accuracy console | Counts, holds, lot genealogy, variance approval, replenishment and adjustment |
| 3PL client | Customer portal | Authorized owned inventory, order upload, tracking, SLAs, invoices and disputes |
| Integration operator | Integration console | Partner tokens, sync status, failed jobs, webhooks, resync and replay |

**Suggested top-level navigation:** My Work; Operations; Inbound; Stock & Locations; Outbound; Returns & Quality; Workforce; Yard; Clients & Billing; Insights; Integrations; Administration. Hide optional areas by subscription, facility configuration and permission. A tap on an overdue alert must lead to the exact source order/task rather than a generic report.

**Scanning design doctrine:** full-screen confirmation, large readable location code, audio/vibration feedback, ergonomic step order, no hidden data entry, explicit conflict resolution, resilient network reconnect, disabled dangerous actions until server confirmation. Work states must not be inferred from the user closing a screen. Accessibility is a measurable requirement, not a decoration.

# 8. Delivery strategy and dependency-ordered roadmap

A large feature catalogue is only useful if engineers can build it without fragmenting stock truth. The roadmap below groups outcomes by dependency, not by number of UI screens. The phase timings are intentionally unspecified until engineering capacity and a pilot partner are known.

## Gate 0: production safety and honest operational baseline (P0)

**Deliver:** versioned DB migrations, PostgreSQL load/concurrency tests, backups and restore drills, isolated tenant policies, authentication recovery and MFA plan, rate limiting, secrets handling, structured logs, observability, CI regression and a safe release/rollback procedure. Preserve the existing business, product, PO, order, count, return and transfer flows. **Exit evidence:** realistic simultaneous purchase/receipt/reservation/transfer tests produce the expected stock ledger after retry and failure. A clean encrypted backup is restored and totals reconcile. Do not onboard business-critical stock before these gates are complete.

## Gate 1: warehouse spatial model and task core (P1)

**Build order:** location hierarchy -> physical balances keyed by bin/lot/owner/status -> stock posting API -> task schema/state machine -> worker/zone queue -> scan verifier -> directed receiving/putaway -> location transfer -> exception resolution -> reconciliation/report. **Exit demo:** receive a pallet, label it, inspect it, scan it to a compatible bin, transfer it, count it, and trace every operation from audit to UI; two workers cannot consume the same units simultaneously.

## Gate 2: complete outbound physical execution (P1 to P2)

**Build order:** allocations at bin level -> picking tasks -> short-pick flows -> pick-face replenishment -> batch/wave/cluster -> carton/HU and packing bench -> scan-to-pack -> carrier integration -> staging/load -> tracking and external notification. **Exit demo:** multi-line customer order with lot rules is picked by staff, split across two cartons, labeled, staged, scan-loaded and shipped; quantity and tracking reconcile. Both negative and exception cases pass.

## Gate 3: competitive SMB and 3PL commercial surface (P2)

**Build order:** external order import and API authentication -> marketplace sync with clear stock source of truth -> client inventory owners -> customer portal -> chargeable event engine -> rate cards and contract versions -> invoice drafts and accounting export -> SLA reporting. **Exit demo:** two 3PL customers hold identical SKUs but cannot see, pick or bill each other's goods; client charges originate from verified events and survive replays.

## Gate 4: advanced execution and optimization (P3)

**Build order:** higher-order waves, put-wall, dynamic slotting, supervisor workload plans, labor standards, ASN/dock schedule, cross-dock, VAS, retail compliance, advanced traceability, space analytics and simulation. **Exit demo:** a complex peak-shift operating scenario can be replanned without losing inventory correctness and with auditable reasons for changed tasks.

## Gate 5: enterprise extensions and validated intelligence (P4)

**Explore only with suitable customers:** robotics adapters, conveyors/MHE, yard/transport integration, voice/RFID, manufacturing, pharmaceutical or cold-chain verticals, AI slotting and labor predictions. **Exit demo:** safe hardware integration with timeouts and operator fallback; measured improvement over baseline; sector-specific external review where compliance is claimed.

## Backlog ordering logic

For each candidate feature score **customer pain (0-5)**, **frequency (0-5)**, **risk reduction (0-5)**, **commercial differentiation (0-5)**, **implementation complexity (1-5)** and **dependency readiness (0-5)**. Use a transparent initial score: `2*pain + frequency + 2*risk_reduction + differentiation + dependency_readiness - 2*complexity`. This is an internal ranking *proposal*, not a market-measured coefficient. Always override scoring when safety, financial integrity or regulatory obligations demand earlier work. Attach evidence from an interview, pilot or customer ticket.

# 9. Quality engineering and test catalog

## 9.1 Invariants that must never be broken

- Every `InventoryUnit` can belong to exactly one current physical storage position or explicitly modeled transit stage; pending delivery forecasts are not physical inventory.
- The aggregate by warehouse/product/owner/status/lot reconciles with all current location balances and handling units.
- `available >= 0` unless a deliberate business adjustment model explicitly accepts controlled negative stock; the initial WMS should not.
- All state-changing endpoints enforce tenant boundary, warehouse permission, actor authorization and idempotency key where relevant.
- Reservations plus verified picks and other commitments cannot allocate more eligible units than exist.
- Every physical movement has an immutable journal entry and, if scanned, source scan evidence and destination confirmation.
- Shipment content and customer order fulfilled quantities reconcile with packed and loaded HUs, with explicit exceptions for partially shipped orders.
- A 3PL operational event creates at most one intended charge for a particular service rate; a correction creates a credit or reversal record rather than altering history.
- Integration retries, server restarts, device reconnects and timeout races cannot duplicate an inventory posting.

## 9.2 Test matrix by failure mode

| Scenario | Test method | Required result |
|:--|:--|:--|
| Two pickers claim one final unit | Parallel PostgreSQL transactions | One succeeds; the other sees explicit shortage/blocked task |
| Wrong bin scan | Handheld integration test | Task unconfirmed; no silent stock move |
| Duplicate ASN or carrier webhook | Idempotency and replay test | One effective transaction, auditable duplicate event |
| Serial appears in two cartons | Unique serial check | Second pack rejected unless documented correction |
| Expired lot picked to restricted customer | Rule engine test | Ineligible lot not allocated or scanned |
| Uninspected returned item reserved | Stock-status authorization | Hold excludes it from ATP and pick |
| Worker from another tenant guesses order ID | Object-level authorization | No data or mutation; audit relevant denial |
| Count overlaps receipt | Snapshot conflict simulation | Variance resnapshot/review; no stale overwrite |
| Carrier request times out after label purchased | Network chaos test | Retry finds original label, no duplicate charge |
| Wi-Fi drops during pick confirmation | Offline replay test | Acknowledgment reconciles once at reconnect |
| Transfer ships but destination not received | Two-stage transit test | Stock appears in transit, not destination usable |
| 3PL client portal leaks another owner | Contract test across tenant-owner hierarchy | Strict owner isolation |
| Backup restore after large shift | Disaster recovery drill | RPO/RTO verified; reconciled stock ledger |
| Wave cancelled mid-pick | State transition test | Picked goods remain accountable, unpicked reservations released correctly |

## 9.3 Test pyramid and pilot strategy

**Unit:** allocation selectors, lot/FEFO, UOM math, charge rating, invariant checkers and task state transitions. **Service/API:** tenant and owner boundaries, CSRF/session, role checks, transactional posting, revisions, webhooks and bulk imports. **Database:** PostgreSQL serializability/read-committed behavior under actual concurrent requests; isolation and retry. **Browser / handheld:** scanner simulation across receive, count, pick, pack and ship; keyboard accessibility and device rotation. **Integration:** contract tests against sandbox carrier/ERP APIs, signature validation and dead-letter replay. **Load:** synthetic stress resembling a real design partner's SKU/order throughput rather than an invented target. **Pilot:** a consenting warehouse with sanitized initial data, staff training, daily reconciliations, observed time-on-task and documented rollbacks.

**Launch acceptance metrics:** choose actual targets after pilot baseline. Recommended measured metrics are inventory location accuracy, pick accuracy, stock reconciliation variance, order cycle time, dock-to-stock duration, on-time ship rate, return inspection time, 3PL invoice disputes, support tickets per thousand transactions, API error rate, delayed outbox events and restore effectiveness. Do not promise vendor marketing percentages as Elveriq service guarantees.

# 10. Engineering work packages and core API contracts

The following interface sketches are planning examples. Endpoint naming, versioning and event schemas must be decided in API design review. Do not use this section as an assertion that these endpoints already exist.

## 10.1 Location and stock API

`POST /api/v1/locations`, `GET /api/v1/locations/{id}/stock`, `POST /api/v1/inventory/movements`, `GET /api/v1/trace/lots/{lot_id}`. A stock movement request must identify source location (if any), destination, item, quantity/UOM, owner, stock condition, lot/serial/HU, actor, reason, work reference, tenant and idempotency token. Permission checks and inventory capacity validation are server-side. Avoid accepting arbitrary client-supplied balance totals.

## 10.2 Work orchestration API

`POST /api/v1/work/requests`, `GET /api/v1/work/tasks?assignee=me`, `POST /api/v1/work/tasks/{id}/claim`, `POST /api/v1/work/tasks/{id}/confirm-step`, `POST /api/v1/work/tasks/{id}/exception`. Response includes expected scan type, expected bin/product/HU, quantity, allowed overrides and task revision. The confirmation handler validates source, destination, lot and concurrency before ledger posting. "Claim" is atomic and may include a lease or revision strategy to prevent conflicting supervisors.

## 10.3 Receiving, outbound and shipping API

`POST /api/v1/asns`, `POST /api/v1/receipts`, `POST /api/v1/waves`, `POST /api/v1/packages`, `POST /api/v1/shipments/{id}/labels`, `POST /api/v1/loads/{id}/scan`. Each API must have explicit lifecycle constraints. Receipt, pack and load confirmation are not interchangeable. Label creation may be a separate external side effect with a transaction/outbox and cancellation/void model.

## 10.4 Billable event API

`POST /api/v1/billing/events` should ordinarily be internal or protected from arbitrary client charges. It references the validated physical event, service category, customer owner, rate card version, quantity, unit and correlation ID. Events settle into rated charges and invoices with immutable audit. Reference counts and decimals must not use floating-point arithmetic for currency; store integer minor units or exact decimals with currency controls.

## 10.5 Canonical event envelope

```json
{
  "event_id": "evt_...unique...",
  "event_type": "warehouse.task.completed",
  "schema_version": 1,
  "occurred_at": "2026-11-12T17:20:00Z",
  "tenant_id": "...",
  "warehouse_id": "...",
  "actor_id": "...",
  "aggregate_id": "...",
  "aggregate_version": 5,
  "correlation_id": "...",
  "data": {"task_id": "...", "quantity": 4, "unit": "each"}
}
```

This is an illustrative schema with synthetic identifiers and timestamp, not live warehouse data. Define event ownership, dedupe, redaction, retention, compatibility, schema evolution and replay semantics before using it in production.

# 11. Competitive differentiation that is achievable

To be taken seriously, Elveriq cannot merely claim "everything". It should deliver an end-to-end verified workflow for its chosen initial buyers before broadening. Large enterprise products are feature-rich but often require significant design and configuration; modern small-warehouse products put speed and mobility first. Elveriq's opportunity is a **modular, intuitive execution system with enterprise-grade audit and practical pricing**. Pricing itself is outside this paper because current customer willingness to pay has not been validated.

**First target buyer:** independent distributor or warehouse with one to three sites and recurring physical receiving/picking problems. **Second target buyer:** small-to-mid-sized 3PL with multiple client inventory owners and billing friction. **Later enterprise buyers:** multi-site operators requiring custom ERP rules, sophisticated labor and automation interfaces. Do not promise unsupported regulated use cases.

**Suggested differentiators:** fast setup with importer preview; task-first UX rather than menu-first ERP; traceable, truthful KPI cards; configurable workflow templates rather than thousands of default controls; excellent mobile scan feedback; strong exception handling; visible client-level service profitability; and high quality support and training material. Each differentiator needs pilot evidence, not slogans.

**Avoid product debt:** Do not build five independent inventory counters for picking, returns, HU tracking, ERP sync and dashboard metrics. Avoid premature AI chat that suggests or executes unsafe stock corrections. Do not make a "quick ship" button bypass packing audit. Do not represent a CSV import as a bidirectional integration. Do not copy vendors' proprietary graphics or code; implement interoperable, independently designed patterns.

# 12. Operating research program and research questions

Keep this document alive. On every vendor release, add or amend source links, evidence date, feature status, edition requirement, proposed acceptance and competitor screenshot/test notes (with permission). On every Elveriq pull request, link to one or more `EV-NNN` records and update classification only after verified tests. Every pilot incident becomes an exception-handling acceptance test.

**Questions to ask actual warehouse supervisors:** Which scans are required today? How are damaged/short receipts handled? Which WMS does the customer use? How much stock is held on the floor versus bins? Are pallet labels and SSCC used? How often does customer inventory mix in one facility? How are carrier manifests produced? What causes daily rework? Which KPIs do managers trust? What features are unused even in their current enterprise WMS? What compliance obligations come from contractual customers rather than law? Which hours of operation and Wi-Fi failure modes must be supported?

**Vendor verification template:** vendor, product, edition, feature, source, dated capture, observed user flow, limits, external integrations, configuration required, license dependency, hardware requirements, security/control implications, Elveriq design translation and acceptance tests. Never make a "feature parity" claim without a transparent scope and test procedure.

# 13. Source bibliography and vendor documentation

Links are direct official sources whenever possible. The label `[Sxx]` in a feature requirement is an evidence trail and a design prompt. It does **not** imply that the cited vendor ships the exact custom Elveriq acceptance test wording or includes that capability in every edition. Sources should be recrawled and saved in an internal research repository when later editions are reviewed.

- **[S01] SAP — SAP EWM features.** [https://www.sap.com/canada/products/scm/extended-warehouse-management/features.html](https://www.sap.com/canada/products/scm/extended-warehouse-management/features.html). *Evidence note:* Official feature overview; scope varies by deployment and license.

- **[S02] SAP — SAP Learning: EWM processes.** [https://learning.sap.com/courses/exploring-business-processes-in-sap-ewm-for-sap-s-4hana-cloud-private-edition/introducing-sap-s4-hana-extended-warehouse-management](https://learning.sap.com/courses/exploring-business-processes-in-sap-ewm-for-sap-s-4hana-cloud-private-edition/introducing-sap-s4-hana-extended-warehouse-management). *Evidence note:* Warehouse monitor, RF, VAS, labor, slotting, cross-docking.

- **[S03] Manhattan Associates — ActiveWarehouse platform and editions.** [https://www.manh.com/solutions/supply-chain-management-software/activewarehouse](https://www.manh.com/solutions/supply-chain-management-software/activewarehouse). *Evidence note:* Inventory, labor, automation, yard; feature differences across editions.

- **[S04] Manhattan Associates — Supply Chain Execution 26.2.** [https://www.manh.com/releases/2026/waypoints-supply-chain-execution-26.2](https://www.manh.com/releases/2026/waypoints-supply-chain-execution-26.2). *Evidence note:* Unified warehouse, yard, labor, slotting and AI release capabilities.

- **[S05] Blue Yonder — Warehouse Management Solution.** [https://blueyonder.com/solutions/warehouse-management](https://blueyonder.com/solutions/warehouse-management). *Evidence note:* Warehouse execution, resource orchestration, slotting, robotics, analytics.

- **[S06] Blue Yonder — WMS FAQ.** [https://blueyonder.com/resources/blue-yonder-ai-powered-wms-unified-faq](https://blueyonder.com/resources/blue-yonder-ai-powered-wms-unified-faq). *Evidence note:* Features may vary by package, edition and release.

- **[S07] Blue Yonder — 2026.2 cognitive execution release.** [https://blueyonder.com/release-announcements/2026-2-release/cognitive-solutions-for-execution](https://blueyonder.com/release-announcements/2026-2-release/cognitive-solutions-for-execution). *Evidence note:* Shift forecasts, labor insight, slotting heatmaps.

- **[S08] Oracle — Fusion Cloud Warehouse Management.** [https://www.oracle.com/scm/logistics/warehouse-management/](https://www.oracle.com/scm/logistics/warehouse-management/). *Evidence note:* Waving, cross docking, VAS, manufacturing and yard operations.

- **[S09] Oracle — WMS AI agent innovations.** [https://blogs.oracle.com/scm/log-ai-innovations-26a](https://blogs.oracle.com/scm/log-ai-innovations-26a). *Evidence note:* Wave research and task prioritization agents.

- **[S10] Infor — Infor WMS capability overview.** [https://www.infor.com/solutions/scm/warehouse-management-system](https://www.infor.com/solutions/scm/warehouse-management-system). *Evidence note:* Multi-owner, bin, wave, voice, 3PL billing, labor, 3D.

- **[S11] Infor — October 2026 supply chain AI agents.** [https://www.infor.com/blog/supply-chain-ai-agents-october-2026-release](https://www.infor.com/blog/supply-chain-ai-agents-october-2026-release). *Evidence note:* Wave and slotting agents; release-specific.

- **[S12] Infios — Infios WMS capabilities.** [https://www.infios.com/en/supply-chain-solutions/warehouse-management-systems](https://www.infios.com/en/supply-chain-solutions/warehouse-management-systems). *Evidence note:* Modular labor, yard, voice, WCS, robotics and execution.

- **[S13] Tecsys — Tecsys WMS.** [https://www.tecsys.com/solutions/warehouse-management](https://www.tecsys.com/solutions/warehouse-management). *Evidence note:* Visual Logistics, warehouse tasks, replenishment and billing.

- **[S14] Deposco — Bright Warehouse WMS.** [https://deposco.com/solutions/supply-chain-execution/warehouse-management/](https://deposco.com/solutions/supply-chain-execution/warehouse-management/). *Evidence note:* Waved and waveless, ASN, scanning, shipping, automation.

- **[S15] Extensiv — 3PL Warehouse Manager product.** [https://www.extensiv.com/3pl/products/3pl-warehouse-manager](https://www.extensiv.com/3pl/products/3pl-warehouse-manager). *Evidence note:* 3PL billing, REST API, ASN, picking, scanning, lot/serial.

- **[S16] Extensiv — 3PL solutions.** [https://www.extensiv.com/solutions/3pls](https://www.extensiv.com/solutions/3pls). *Evidence note:* Customer portal, SmartScan, rate shopping, analytics, dock.

- **[S17] Extensiv — 3PL knowledge base.** [https://help.extensiv.com/en_US/3pl-warehouse-manager](https://help.extensiv.com/en_US/3pl-warehouse-manager). *Evidence note:* Operational submodules, shipping, EDI, 3PL billing and scanning.

- **[S18] ShipHero — Warehouse management software.** [https://www.shiphero.com/warehouse-management-software](https://www.shiphero.com/warehouse-management-software). *Evidence note:* Client billing, portals, barcode verification and channel integrations.

- **[S19] Logiwa — Outbound operations.** [https://www.logiwa.com/solutions/fulfillment-of-orders-outbound-operations](https://www.logiwa.com/solutions/fulfillment-of-orders-outbound-operations). *Evidence note:* Pick/pack/ship, put-wall, many pick methods, integrations.

- **[S20] Logiwa — Digital warehouse software.** [https://www.logiwa.com/solutions/digital-warehouse-management-software](https://www.logiwa.com/solutions/digital-warehouse-management-software). *Evidence note:* Location rules, capacities, mobile scanners, e-commerce sync.

- **[S21] Odoo — Inventory detailed feature catalog.** [https://www.odoo.com/app/inventory-features](https://www.odoo.com/app/inventory-features). *Evidence note:* Location, putaway, picking, lot/serial, FEFO, portals, replenishment.

- **[S22] Microsoft — Dynamics 365 Warehouse Management overview.** [https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-management-overview](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-management-overview). *Evidence note:* Work rules, mobile scanning, load handling, label printing, MHAX.

- **[S23] Microsoft — Dynamics 365 SCM documentation.** [https://learn.microsoft.com/dynamics365/supply-chain](https://learn.microsoft.com/dynamics365/supply-chain). *Evidence note:* Module overview including QA, transportation, mobile and planning.

- **[S24] NetSuite — NetSuite WMS features.** [https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/wms.shtml](https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/wms.shtml). *Evidence note:* Mobile WMS, smart counting, bins, waves.

- **[S25] NetSuite — NetSuite mobile WMS.** [https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/mobile-warehouse-management.shtml](https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/mobile-warehouse-management.shtml). *Evidence note:* Force scan verification, RF receiving, counting and picking.

- **[S26] Oracle NetSuite — Releasing orders to warehouse.** [https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1548078373.html](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1548078373.html). *Evidence note:* Wave release and pick-task tracking.

- **[S27] Cin7 — Cin7 Core WMS documentation.** [https://help.core.cin7.com/hc/en-us/articles/9034461577487-Introduction-to-Warehouse-Management-System-WMS](https://help.core.cin7.com/hc/en-us/articles/9034461577487-Introduction-to-Warehouse-Management-System-WMS). *Evidence note:* Mobile picking, FIFO/FEFO validation, packing, counting, scanning.

- **[S28] Made4net — WMS core and extended capabilities.** [https://made4net.com/knowledge-center/warehouse-order-fulfillment-software-guide/](https://made4net.com/knowledge-center/warehouse-order-fulfillment-software-guide/). *Evidence note:* Practical core vs. extended scope; cross-dock, WMS, labor, yard.

- **[S29] Made4net — Supply chain execution suite.** [https://made4net.com/](https://made4net.com/). *Evidence note:* WMS, 3PL, yard, labor, routing, proof of delivery.

- **[S30] Fishbowl — Advanced Warehouse.** [https://www.fishbowlinventory.com/warehouse-management/](https://www.fishbowlinventory.com/warehouse-management/). *Evidence note:* Multi-warehouse, mobile, 3PL, EDI, stock controls.

- **[S31] GS1 US — What is SSCC and logistics label.** [https://www.help.gs1us.org/barcodes-available-in-gs1-us-data-hub](https://www.help.gs1us.org/barcodes-available-in-gs1-us-data-hub). *Evidence note:* SSCC is logistic-unit identity; not GTIN.

- **[S32] OWASP — API Security Top 10 2023.** [https://owasp.org/projects/api-security-project](https://owasp.org/projects/api-security-project). *Evidence note:* Object level and function level authorization risks.

- **[S33] NIST — Digital Identity Guidelines 800-63B-4.** [https://csrc.nist.gov/pubs/sp/800/63/b/4/final](https://csrc.nist.gov/pubs/sp/800/63/b/4/final). *Evidence note:* Authentication and authenticator management guidance.

- **[S34] FDA — Food Traceability Rule and effective timetable.** [https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods](https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods). *Evidence note:* Traceability for covered foods; enforcement timing jurisdiction dependent.

- **[S35] SAP — What is a WMS?.** [https://www.sap.com/products/scm/extended-warehouse-management/what-is-a-wms.html](https://www.sap.com/products/scm/extended-warehouse-management/what-is-a-wms.html). *Evidence note:* Labor, yard, monitoring, KPIs and task interleaving.

- **[S36] NetSuite — Warehouse processing help.** [https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2317586.html](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2317586.html). *Evidence note:* Barcode, bin management, assembly, counts.

- **[S37] NetSuite — WMS overview.** [https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_156382517509.html](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_156382517509.html). *Evidence note:* Availability/requirements of WMS SuiteApps; packaging caveat.

- **[S38] Blue Yonder — 2026.3 execution release.** [https://blueyonder.com/release-announcements/2026-3-release/cognitive-solutions-for-execution](https://blueyonder.com/release-announcements/2026-3-release/cognitive-solutions-for-execution). *Evidence note:* Multi-vendor automation integration and explainable slotting.


# 14. Glossary of critical warehouse terms

| Term | Meaning in this paper |
|:--|:--|
| WMS | Warehouse Management System: inventory location plus directed execution, counting, shipping and visibility |
| WES | Warehouse Execution System: real-time operational orchestration that can sit within/alongside a WMS |
| WCS | Warehouse Control System: automation device or material-handling control interface |
| ERP | Enterprise Resource Planning; product, purchasing, finance and supply chain source systems |
| 3PL | Third-Party Logistics; a warehouse operator serves inventory-owning customers |
| PO | Purchase Order; expected supplier order |
| ASN | Advance Shipping Notice; advance receipt details for an arriving shipment |
| HU / LPN | Handling Unit / License Plate Number; uniquely identified carton, pallet or tote |
| SSCC | Serial Shipping Container Code; GS1 identifier for a logistic unit, distinct from product GTIN |
| GTIN | Global Trade Item Number; identity of a trade item rather than a shipment unit |
| RF | Radio Frequency; handheld workflow using scanner and mobile device |
| FIFO / FEFO | First In First Out / First Expiring First Out stock-removal logic |
| Wave | Released work group of one or many outbound orders |
| Put-wall | Consolidation/sortation cells used after bulk or batch picking |
| Cross-docking | Moving inbound goods to outbound demand with minimal long-term storage |
| Slotting | Planned allocation of SKU locations to improve travel and space use |
| ATP | Available to Promise; calculation of eligible inventory against commitments and future supply |
| VAS | Value-Added Services such as kitting, labeling, relabeling and repacking |
| MHE | Material Handling Equipment (conveyors, sorters, AS/RS, etc.) |
| AMR | Autonomous Mobile Robot |
| EDI | Electronic Data Interchange; structured trading-partner documents such as orders and shipping notices |
| RMA / RTV | Return Merchandise Authorization / Return to Vendor |
| RPO / RTO | Recovery Point Objective / Recovery Time Objective for disaster recovery |
| SOP | Standard Operating Procedure |
| Idempotency | Repeated same business command has one intended effective result |
| Transactional outbox | Reliable committed events delivered to external systems after database commit |

# 15. Final implementation directive

Elveriq's mission is **not to clone a vendor's interface or chase a perfect feature count**. It is to build warehouse software that can safely direct real people and goods with the breadth to grow into more complex operations. The practical sequence is: transaction correctness -> bin inventory -> warehouse tasks -> scanning -> full picking/packing/dispatch -> 3PL customer workflows and billing -> labor/yard/optimization -> robotics and AI where customers justify it.

Treat the 300-line CSV register as the engineering backlog source, this paper as the researched architecture and requirements record, and pilot evidence as the authority for deciding which features earn priority. A warehouse should be able to answer at any moment: **what stock do we have, who owns it, where is it, what work is next, what went wrong, who confirmed it, what is leaving, and what service should be billed?**

**Document revision:** Version 1.0, research snapshot 12 November 2026. Feature presence and release packaging should be reconfirmed before external competitive claims or regulated customer commitments.
