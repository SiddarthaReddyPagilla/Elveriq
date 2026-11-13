"""PostgreSQL concurrency checks. Reuses an isolated test schema fixture.

CI provisions PostgreSQL; local SQLite-only development skips these tests.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import select, func

from dispatchforge_app.errors import DomainError
from dispatchforge_app.models import BinStock, WarehouseTask
from dispatchforge_app.warehouse_execution import create_bin, create_task
from dispatchforge_app.transfer_service import transfer_stock
from tests_web.test_transfers_postgres import pg_store


def test_concurrent_putaway_never_double_reserves_unlocated_postgres(pg_store):
    factory, _, (bid, uid, wid, other) = pg_store
    with factory.begin() as s:
        bin_id = create_bin(s, bid, wid, "PICK-A").id
    barrier = Barrier(2)
    def worker(key):
        barrier.wait(timeout=10)
        try:
            with factory.begin() as s:
                row, replay = create_task(s, bid, wid, "BOX", "putaway", bin_id, 7,
                                          uid, idempotency_key=key)
                return row.id
        except DomainError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(worker,'putaway-first-key')
        b=pool.submit(worker,'putaway-second-key')
        results=[a.result(timeout=15),b.result(timeout=15)]
    assert results.count(409)==1
    with factory() as s:
        tasks=s.scalar(select(func.count(WarehouseTask.id)).where(
            WarehouseTask.business_id==bid))
        assert tasks==1


def test_pending_putaway_blocks_legacy_stock_transfer_postgres(pg_store):
    factory, _, (bid, uid, wid, other) = pg_store
    with factory.begin() as s:
        bin_id=create_bin(s,bid,wid,'PICK-A').id
        create_task(s,bid,wid,'BOX','putaway',bin_id,8,uid,
                    idempotency_key='pending-putaway-key')
    with pytest.raises(DomainError) as exc:
        with factory.begin() as s:
            transfer_stock(s,bid,wid,other,'BOX',5,user_id=uid,
                           idempotency_key='cannot-transfer-key')
    assert exc.value.status==409


def test_simultaneous_completion_posts_putaway_once_postgres(pg_store):
    from dispatchforge_app.warehouse_execution import claim_task, start_task, complete_task
    factory, _, (bid, uid, wid, _) = pg_store
    with factory.begin() as s:
        bin_id=create_bin(s,bid,wid,'PICK-A').id
        item,_=create_task(s,bid,wid,'BOX','putaway',bin_id,6,uid,
                           idempotency_key='complete-single-key')
        tid=item.id
        claim_task(s,bid,tid,uid)
        start_task(s,bid,tid,uid)
    barrier=Barrier(2)
    def worker():
        barrier.wait(timeout=10)
        with factory.begin() as s:
            t,replayed=complete_task(s,bid,tid,uid,'BOX','PICK-A')
            return t.id,replayed
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(worker)
        second=pool.submit(worker)
        results=[first.result(timeout=15),second.result(timeout=15)]
    assert {x[0] for x in results}=={tid}
    assert sorted([x[1] for x in results])==[False,True]
    with factory() as s:
        assert s.scalar(select(func.sum(BinStock.on_hand)).where(
            BinStock.business_id==bid)) == 6
