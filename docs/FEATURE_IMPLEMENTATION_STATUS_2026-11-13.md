# Elveriq — Feature Delivery Status Against 300-Feature Research

**Last local verification: 2026-11-13.** This page is the **implementation ledger**; it supplements but does not alter the original November 2026 competitor research and feature register. It is not a claim of enterprise-feature parity.

| Reference | Capability | Delivery status | Evidence |
|---|---|---|---|
| Phase 1 physical execution | Physical bins, location capacities and bin stocks | Locally implemented; PostgreSQL deployment pending | `warehouse_execution.py`, migration, tests |
| Phase 1 physical execution | Putaway, move and unlocate with scan confirmation and task events | Locally implemented; pilot pending | `warehouse_execution.py`, `tests_web/test_warehouse_execution.py` |
| EV-097 | Warehouse-wide physical count | Existing implementation | `cycle_count_service.py` |
| EV-098 | Blind bin cycle count | **Not complete** (physical bin count exists, expected quantity visible) | `bin_cycle_count_service.py`, `dashboard.html` |
| EV-096 | Stock freeze during count | Not implemented; stale/active-work guard provided instead | `bin_cycle_count_service.py` |
| EV-102 | Count variance approvals | **Partial:** owner-only posted variances and audit; threshold rules absent | `bin_cycle_count_service.py`, API, tests |
| EV-103 | Count KPI and root cause | Not implemented | Future roadmap |

## Release gates

- **Local regression:** Python suite and JavaScript syntax must pass.
- **Database gate:** Additive PostgreSQL migrations in staging, schema/index validation, PostgreSQL concurrent test suite, recovery rehearsals and rollback review.
- **Warehouse acceptance:** Verify physical stock reconciliation, capacity, reservations, stale counts, canceled tasks, role policy and two-tenant isolation.
- **Deployment gate:** Review branch/pull request, CI, backup/restore, monitoring, and controlled pilot before live warehouse use.

## Next build after Phase 1.1

Unify inventory posting and add order-linked directed picking, followed by receiving inspections, handling units, packing and shipping. Avoid implementing wave picking or AI allocation before the transactional inventory model and physical task engine have passed PostgreSQL staging validation.
