"""PostgreSQL retry races; skipped locally, exercised on CI's real database."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import func,select
from dispatchforge_app.models import (Supplier,PurchaseOrder,PurchaseOrderLine,
    InboundReceipt,WarehouseException,StockLevel,Product)
from dispatchforge_app.inbound_service import create_notice,arrive_notice,scan_receipt
from dispatchforge_app.exception_service import open_case
from tests_web.test_transfers_postgres import pg_store


def test_concurrent_identical_inbound_scan_posts_stock_once_postgres(pg_store):
    factory,_,(bid,uid,wid,_) = pg_store
    with factory.begin() as s:
        supplier=Supplier(business_id=bid,name='ASN Test Supplier',email='')
        s.add(supplier);s.flush()
        po=PurchaseOrder(business_id=bid,warehouse_id=wid,supplier_id=supplier.id,
            reference='PO-PG-RECEIVE',status='ordered')
        s.add(po);s.flush()
        product_id=s.scalar(select(Product.id).where(Product.business_id==bid,Product.sku=='BOX'))
        line=PurchaseOrderLine(business_id=bid,purchase_order_id=po.id,
            product_id=product_id,ordered_quantity=5,received_quantity=0)
        s.add(line);s.flush()
        notice=create_notice(s,bid,po.id,'ASN-PG-RACE','', 'DOCK-01',
                             [{'purchase_line_id':line.id,'expected':5}],uid)
        arrive_notice(s,bid,notice.id,uid)
        from dispatchforge_app.models import InboundNoticeLine
        notice_line_id=s.scalar(select(InboundNoticeLine.id).where(InboundNoticeLine.notice_id==notice.id))
        nid=notice.id
    barrier=Barrier(2)
    def work():
        barrier.wait(timeout=10)
        with factory.begin() as s:
            receipt,replay=scan_receipt(s,bid,nid,notice_line_id,'BOX',5,0,'',uid,'pg-asn-scan-retry-key')
            return receipt.id,replay
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(work);b=pool.submit(work)
        result=[a.result(timeout=20),b.result(timeout=20)]
    assert result[0][0]==result[1][0]
    assert sorted(x[1] for x in result)==[False,True]
    with factory() as s:
        assert s.scalar(select(func.count(InboundReceipt.id)))==1
        assert s.scalar(select(StockLevel.on_hand).where(StockLevel.business_id==bid,
            StockLevel.warehouse_id==wid,StockLevel.product_id==product_id))==15


def test_concurrent_identical_case_key_creates_one_incident_postgres(pg_store):
    factory,_,(bid,uid,wid,_) = pg_store
    barrier=Barrier(2)
    def work():
        barrier.wait(timeout=10)
        with factory.begin() as s:
            case,replay=open_case(s,bid,wid,'manual','high','manual',None,
                'Postgres row lock contention','Retry across staff sessions',uid,
                'pg-concurrent-incident-key')
            return case.id,replay
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(work);b=pool.submit(work)
        results=[a.result(timeout=20),b.result(timeout=20)]
    assert results[0][0]==results[1][0]
    assert sorted(x[1] for x in results)==[False,True]
    with factory() as s:
        assert s.scalar(select(func.count(WarehouseException.id)))==1
