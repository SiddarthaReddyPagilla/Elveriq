"""Read-only tenant-scoped warehouse integrity audit.

These checks *detect* suspect ledger states; they never repair inventory or
establish physical truth.  All findings are sampled (25 ids per rule), while
counts are exact for the matching scope. No writes or external telemetry.
"""
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import (Warehouse, Product, StockLevel, WarehouseBin, BinStock,
    InboundNotice, InboundNoticeLine, OutboundPick, OutboundCarton,
    OutboundCartonItem, WarehouseTask, WarehouseException, CustomerOrder,
    OrderLine)

SAMPLE_LIMIT = 25
RULES = []

def _scope(session: Session, bid: int, wid: int | None):
    if wid is not None and session.scalar(select(Warehouse.id).where(
            Warehouse.id == wid, Warehouse.business_id == bid)) is None:
        raise DomainError('Warehouse not found', 404)

def _finding(session, name, severity, statement, description):
    # Reuse one already-scoped, ID-only query to derive both exact count and
    # a bounded list of evidence. The client never receives other tenants' IDs.
    ids = statement.order_by(None).subquery()
    count = int(session.scalar(select(func.count()).select_from(ids)) or 0)
    samples = session.scalars(statement.order_by(ids_sort(statement)).limit(SAMPLE_LIMIT)).all()
    return {'rule':name, 'severity':severity, 'description':description,
            'affected_records':count, 'sample_ids':[int(n) for n in samples],
            'samples_truncated':count > SAMPLE_LIMIT}

def ids_sort(statement):
    # Queries below deliberately select the model's primary key first.
    return list(statement.selected_columns)[0]

def audit(session: Session, bid: int, wid: int | None = None):
    _scope(session, bid, wid)
    checks = [fn(session, bid, wid) for fn in RULES]
    return {'source':'live_database_read_only', 'warehouse_id':wid,
        'read_only':True, 'no_repairs_performed':True,
        'checks':checks, 'checked_rules':len(checks),
        'failed_rules':sum(row['affected_records'] > 0 for row in checks),
        'affected_records':sum(row['affected_records'] for row in checks),
        'ready_for_manual_review':not any(row['affected_records'] > 0 for row in checks),
        'caveat':'This is not physical inventory certification or a PostgreSQL concurrency test.'}

def _in_warehouse(q, model, wid):
    return q.where(model.warehouse_id == wid) if wid is not None else q

def check_stock_balance(session, bid, wid):
    m=StockLevel
    q=select(m.id).where(m.business_id==bid, or_(m.on_hand<0,m.reserved<0,m.reserved>m.on_hand))
    return _finding(session,'stock_balance','critical',_in_warehouse(q,m,wid),
        'Warehouse balance is negative or reserved units exceed on-hand')
RULES.append(check_stock_balance)

def check_stock_tenancy(session,bid,wid):
    m=StockLevel
    q=(select(m.id).join(Warehouse, Warehouse.id==m.warehouse_id)
       .join(Product,Product.id==m.product_id).where(m.business_id==bid,
       or_(Warehouse.business_id!=bid,Product.business_id!=bid)))
    return _finding(session,'stock_reference_scope','critical',_in_warehouse(q,m,wid),
        'Stock belongs to a product or warehouse owned by another workspace')
RULES.append(check_stock_tenancy)

def check_bin_allocations(session,bid,wid):
    m=BinStock
    q=select(m.id).where(m.business_id==bid,or_(m.on_hand<0,m.allocated<0,m.allocated>m.on_hand))
    return _finding(session,'bin_allocations','critical',_in_warehouse(q,m,wid),
        'Physically placed or allocated stock has invalid quantities')
RULES.append(check_bin_allocations)
