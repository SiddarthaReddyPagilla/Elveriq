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
RULE_SEVERITY = {}

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

def audit(session: Session, bid: int, wid: int | None = None,
          severity: str | None = None):
    _scope(session, bid, wid)
    checks = [fn(session, bid, wid) for fn in RULES
              if severity is None or RULE_SEVERITY[fn.__name__] == severity]
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

def check_bin_membership(session,bid,wid):
    m=BinStock
    q=(select(m.id).join(WarehouseBin,WarehouseBin.id==m.bin_id)
       .join(Product,Product.id==m.product_id).where(m.business_id==bid,
       or_(WarehouseBin.business_id!=bid,WarehouseBin.warehouse_id!=m.warehouse_id,
           Product.business_id!=bid)))
    return _finding(session,'bin_reference_scope','critical',_in_warehouse(q,m,wid),
        'Placed stock bin, product, and warehouse references disagree')
RULES.append(check_bin_membership)

def check_placed_vs_accounting(session,bid,wid):
    m=BinStock
    placed=(select(m.warehouse_id.label('wid'),m.product_id.label('pid'),
             func.sum(m.on_hand).label('placed')).where(m.business_id==bid)
             .group_by(m.warehouse_id,m.product_id).subquery())
    q=(select(StockLevel.id).join(placed,and_(StockLevel.warehouse_id==placed.c.wid,
         StockLevel.product_id==placed.c.pid)).where(StockLevel.business_id==bid,
         placed.c.placed>StockLevel.on_hand))
    if wid is not None:q=q.where(StockLevel.warehouse_id==wid)
    return _finding(session,'placed_exceeds_ledger','critical',q,
        'The sum of placed bin units exceeds the warehouse accounting balance')
RULES.append(check_placed_vs_accounting)

def check_capacity(session,bid,wid):
    b=WarehouseBin
    tally=(select(BinStock.bin_id.label('bin_id'),func.sum(BinStock.on_hand).label('units'))
           .where(BinStock.business_id==bid).group_by(BinStock.bin_id).subquery())
    q=(select(b.id).join(tally,tally.c.bin_id==b.id).where(b.business_id==bid,
        b.active.is_(True),b.capacity_units.is_not(None),tally.c.units>b.capacity_units))
    return _finding(session,'bin_overcapacity','warning',_in_warehouse(q,b,wid),
        'Stored units exceed the configured active bin unit capacity')
RULES.append(check_capacity)

def check_inbound_disposition(session,bid,wid):
    m=InboundNoticeLine
    q=(select(m.id).join(InboundNotice,InboundNotice.id==m.notice_id)
        .where(m.business_id==bid,InboundNotice.business_id==bid,
         or_(m.expected<=0,m.accepted<0,m.damaged<0,
             m.accepted+m.damaged>m.expected)))
    if wid is not None:q=q.where(InboundNotice.warehouse_id==wid)
    return _finding(session,'inbound_disposition','critical',q,
        'ASN accepted or damaged units exceed the expected quantity')
RULES.append(check_inbound_disposition)

def check_pick_references(session,bid,wid):
    m=OutboundPick
    q=(select(m.id).join(OutboundCarton,OutboundCarton.order_id==m.order_id,isouter=True)
         .where(m.business_id==bid,or_(m.quantity<=0,
               and_(OutboundCarton.id.is_not(None),OutboundCarton.business_id!=bid))))
    # Multiple cartons on the same order must not duplicate sampled pick IDs.
    q=q.distinct()
    return _finding(session,'pick_quantity_scope','critical',_in_warehouse(q,m,wid),
        'Pick quantity is invalid or linked cartons belong to another workspace')
RULES.append(check_pick_references)

def check_carton_consistency(session,bid,wid):
    m=OutboundCartonItem
    q=(select(m.id).join(OutboundCarton,OutboundCarton.id==m.carton_id)
       .join(OutboundPick,OutboundPick.id==m.pick_id).where(
          m.business_id==bid,OutboundCarton.business_id==bid,
          or_(m.quantity<=0,m.quantity!=OutboundPick.quantity,
              OutboundPick.business_id!=bid,
              OutboundCarton.order_id!=OutboundPick.order_id,
              OutboundCarton.warehouse_id!=OutboundPick.warehouse_id)))
    if wid is not None:q=q.where(OutboundCarton.warehouse_id==wid)
    return _finding(session,'carton_pick_consistency','critical',q,
        'Packed quantity or carton order/warehouse disagrees with verified pick')
RULES.append(check_carton_consistency)

def check_warehouse_tasks(session,bid,wid):
    m=WarehouseTask
    q=(select(m.id).where(m.business_id==bid,or_(m.quantity<=0,
         and_(m.kind=='putaway',m.to_bin_id.is_(None)),
         and_(m.kind=='unlocate',m.from_bin_id.is_(None)),
         and_(m.kind=='move',or_(m.from_bin_id.is_(None),m.to_bin_id.is_(None),
             m.from_bin_id==m.to_bin_id)))))
    return _finding(session,'task_topology','critical',_in_warehouse(q,m,wid),
        'Warehouse task has nonpositive units or invalid source/destination topology')
RULES.append(check_warehouse_tasks)

def check_incident_states(session,bid,wid):
    m=WarehouseException
    q=select(m.id).where(m.business_id==bid,or_(
        and_(m.status=='resolved',m.resolved_at.is_(None)),
        and_(m.status!='resolved',m.resolved_at.is_not(None))))
    return _finding(session,'incident_resolution','warning',_in_warehouse(q,m,wid),
        'Warehouse incident status disagrees with resolution timestamp')
RULES.append(check_incident_states)

# Severity classification for bounded, selective scans.
RULE_SEVERITY.update({
    'check_stock_balance':'critical', 'check_stock_tenancy':'critical',
    'check_bin_allocations':'critical', 'check_bin_membership':'critical',
    'check_placed_vs_accounting':'critical', 'check_capacity':'warning',
    'check_inbound_disposition':'critical', 'check_pick_references':'critical',
    'check_carton_consistency':'critical', 'check_warehouse_tasks':'critical',
    'check_incident_states':'warning',
})
