"""Real PostgreSQL multi-connection serialization: CI exercises row locks; SQLite skips."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

from sqlalchemy import func, select
from dispatchforge_app.errors import DomainError
from dispatchforge_app.models import OrderLine, OutboundPick, OutboundShipment, StockLevel
from dispatchforge_app.order_service import create_order
from dispatchforge_app.outbound_service import (plan_pick, claim_pick, start_pick, scan_pick,
    create_carton, pack_pick, seal_carton, dispatch_order)
from dispatchforge_app.warehouse_execution import create_bin, create_task, claim_task, start_task, complete_task
from tests_web.test_transfers_postgres import pg_store


def prepare(pg_store):
    factory, _, (bid, uid, wid, _) = pg_store
    with factory.begin() as s:
        bin_id = create_bin(s,bid,wid,'PG-PICK').id
        task,_ = create_task(s,bid,wid,'BOX','putaway',bin_id,10,uid,
                             idempotency_key='postgres-putaway-001')
        claim_task(s,bid,task.id,uid)
        start_task(s,bid,task.id,uid)
        complete_task(s,bid,task.id,uid,'BOX','PG-PICK')
        order = create_order(s,bid,wid,'Pg Client',
            (date.today()+timedelta(days=1)).isoformat(),[{'sku':'BOX','quantity':8}],uid)
        oid = order.id
        lid = s.scalar(select(OrderLine.id).where(OrderLine.order_id==oid))
    return factory,bid,uid,wid,bin_id,oid,lid


def test_competing_pick_plans_do_not_double_reserve_postgres(pg_store):
    factory,bid,uid,wid,bin_id,oid,lid=prepare(pg_store)
    barrier=Barrier(2)
    def run(key):
        barrier.wait(timeout=10)
        try:
            with factory.begin() as s:
                row,replayed=plan_pick(s,bid,oid,lid,bin_id,7,uid,key)
                return row.id
        except DomainError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(run,'pg-pick-unique-a')
        b=pool.submit(run,'pg-pick-unique-b')
        output=[a.result(timeout=20),b.result(timeout=20)]
    assert output.count(409)==1
    with factory() as s:
        assert s.scalar(select(func.count(OutboundPick.id)))==1


def test_concurrent_duplicate_dispatch_goods_issues_once_postgres(pg_store):
    factory,bid,uid,wid,bin_id,oid,lid=prepare(pg_store)
    with factory.begin() as s:
        pick,_=plan_pick(s,bid,oid,lid,bin_id,8,uid,'pg-dispatch-pick-key')
        claim_pick(s,bid,pick.id,uid)
        start_pick(s,bid,pick.id,uid)
        scan_pick(s,bid,pick.id,uid,'BOX','PG-PICK')
        carton=create_carton(s,bid,oid,'PG-CARTON',uid)
        pack_pick(s,bid,carton.id,pick.id,uid,'BOX','PG-CARTON')
        seal_carton(s,bid,carton.id,uid)
    barrier=Barrier(2)
    def run():
        barrier.wait(timeout=10)
        with factory.begin() as s:
            shipment,replayed=dispatch_order(s,bid,oid,uid,'Manual','PG-TRACK','pg-dispatch-idempotent')
            return shipment.id,replayed
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(run)
        b=pool.submit(run)
        results=[a.result(timeout=20),b.result(timeout=20)]
    assert {x[0] for x in results}=={results[0][0]}
    assert sorted([x[1] for x in results])==[False,True]
    with factory() as s:
        assert s.scalar(select(func.count(OutboundShipment.id)))==1
        assert s.scalar(select(StockLevel.on_hand).where(StockLevel.warehouse_id==wid))==2
        assert s.scalar(select(StockLevel.reserved).where(StockLevel.warehouse_id==wid))==0
