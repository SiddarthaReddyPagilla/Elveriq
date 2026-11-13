"""Concurrent bin counts must serialize on the authoritative warehouse SKU row.

Set ELVERIQ_TEST_POSTGRES_URL to a disposable PostgreSQL instance in CI.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select

from dispatchforge_app.bin_cycle_count_service import start_bin_count, post_bin_count
from dispatchforge_app.errors import DomainError
from dispatchforge_app.models import BinCycleCount, BinStock, StockLevel
from dispatchforge_app.warehouse_execution import create_bin
from tests_web.test_transfers_postgres import pg_store


def test_concurrent_bin_count_start_is_unique_postgres(pg_store):
    factory, _, (bid, uid, wid, _) = pg_store
    with factory.begin() as session:
        bin_id = create_bin(session, bid, wid, 'C-COUNT').id
    gate = Barrier(2)

    def worker():
        gate.wait(timeout=10)
        try:
            with factory.begin() as session:
                count = start_bin_count(session, bid, wid, bin_id, 'BOX', uid)
                return count.id
        except DomainError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(worker), pool.submit(worker)
        results = [a.result(timeout=20), b.result(timeout=20)]
    assert results.count(409) == 1
    with factory() as session:
        assert session.scalar(select(func.count(BinCycleCount.id))) == 1


def test_concurrent_variance_post_applies_delta_only_once_postgres(pg_store):
    factory, _, (bid, uid, wid, _) = pg_store
    with factory.begin() as session:
        bin_id = create_bin(session, bid, wid, 'C-COUNT').id
        cid = start_bin_count(session, bid, wid, bin_id, 'BOX', uid).id
    gate = Barrier(2)

    def worker():
        gate.wait(timeout=10)
        try:
            with factory.begin() as session:
                return post_bin_count(session, bid, cid, 4, uid).status
        except DomainError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(worker), pool.submit(worker)
        results = [a.result(timeout=20), b.result(timeout=20)]
    assert sorted(results, key=str) == sorted(['posted', 409], key=str)
    with factory() as session:
        assert session.scalar(select(StockLevel.on_hand).where(
            StockLevel.business_id == bid, StockLevel.warehouse_id == wid)) == 14
        assert session.scalar(select(func.sum(BinStock.on_hand)).where(
            BinStock.business_id == bid, BinStock.bin_id == bin_id)) == 4
