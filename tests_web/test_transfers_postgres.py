"""Integration tests with independent PostgreSQL transactions and real row locks.

Run against a throwaway PostgreSQL database:
    ELVERIQ_TEST_POSTGRES_URL=postgresql+psycopg://... pytest -q tests_web/test_transfers_postgres.py
Never point the variable at production: each test creates and drops its own schema.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4
import os
import time

import pytest
from sqlalchemy import create_engine, event, select, func, text
from sqlalchemy.orm import sessionmaker

from dispatchforge_app.errors import DomainError
from dispatchforge_app.models import (Base, Business, User, Warehouse, Product,
    StockLevel, StockMovement, InventoryTransfer)
from dispatchforge_app.transfer_service import transfer_stock


@pytest.fixture
def pg_store():
    url = os.getenv("ELVERIQ_TEST_POSTGRES_URL", "")
    if not url:
        pytest.skip("PostgreSQL not configured; set ELVERIQ_TEST_POSTGRES_URL")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.fail("ELVERIQ_TEST_POSTGRES_URL must point to PostgreSQL")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    schema = "elveriq_transfer_" + uuid4().hex[:16]
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"},
                           isolation_level="READ COMMITTED", pool_pre_ping=True)
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        with factory.begin() as session:
            business = Business(name="Transfer Integration", slug="it-" + uuid4().hex)
            session.add(business)
            session.flush()
            actor = User(business_id=business.id, email="owner@local.invalid",
                         password_hash="not-used", role="owner")
            src = Warehouse(business_id=business.id, name="A", city="Denton")
            dst = Warehouse(business_id=business.id, name="B", city="Denton")
            product = Product(business_id=business.id, sku="BOX", name="Box")
            session.add_all([actor, src, dst, product])
            session.flush()
            session.add_all([
                StockLevel(business_id=business.id, warehouse_id=src.id,
                           product_id=product.id, on_hand=10, reserved=0),
                StockLevel(business_id=business.id, warehouse_id=dst.id,
                           product_id=product.id, on_hand=0, reserved=0),
            ])
            values = (business.id, actor.id, src.id, dst.id)
        yield factory, engine, values
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def snapshot(factory, business_id, src, dst):
    with factory() as session:
        rows = dict(session.execute(select(StockLevel.warehouse_id, StockLevel.on_hand)
            .where(StockLevel.business_id == business_id)).all())
        transfers = session.scalar(select(func.count()).select_from(InventoryTransfer)
            .where(InventoryTransfer.business_id == business_id))
        audit = session.scalars(select(StockMovement).where(
            StockMovement.business_id == business_id,
            StockMovement.kind.in_(("transfer_in", "transfer_out")))).all()
        return (rows[src], rows[dst], transfers,
                [(m.transfer_id, m.kind, m.on_hand_delta) for m in audit])


def test_competing_transfers_cannot_overdraw_postgres(pg_store):
    """First transfer holds both locks; second attempts to consume same stock."""
    factory, engine, (bid, uid, src, dst) = pg_store
    first_modified = Event()
    allow_commit = Event()
    second_started = Event()

    def first_worker():
        with factory.begin() as session:
            result, replayed = transfer_stock(session, bid, src, dst, "BOX", 7,
                user_id=uid, idempotency_key="transfer-first-key")
            first_modified.set()
            assert allow_commit.wait(timeout=10), "Test did not release transaction"
            return result.id, replayed

    def second_worker():
        assert first_modified.wait(timeout=10)
        second_started.set()
        try:
            with factory.begin() as session:
                transfer_stock(session, bid, src, dst, "BOX", 7,
                    user_id=uid, idempotency_key="transfer-second-key")
        except DomainError as exc:
            return exc.status
        return 201

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_worker)
        assert first_modified.wait(timeout=10)
        second = pool.submit(second_worker)
        assert second_started.wait(timeout=10)
        try:
            time.sleep(0.15)  # Give the second transaction time to reach row locks.
            assert not second.done(), "Second transfer should wait for the first row locks"
        finally:
            allow_commit.set()
        first_id, replay = first.result(timeout=10)
        second_status = second.result(timeout=10)
    assert replay is False
    assert second_status == 409
    a, b, count, audit = snapshot(factory, bid, src, dst)
    assert (a, b, count) == (3, 7, 1)
    assert set(audit) == {(first_id, "transfer_in", 7), (first_id, "transfer_out", -7)}


def test_simultaneous_same_key_creates_one_transfer_postgres(pg_store):
    factory, engine, (bid, uid, src, dst) = pg_store
    start = Barrier(2)
    key = "simultaneous-same-key"

    def worker():
        start.wait(timeout=10)
        with factory.begin() as session:
            transfer, replayed = transfer_stock(session, bid, src, dst, "BOX", 6,
                note="Same operation", user_id=uid, idempotency_key=key)
            return transfer.id, replayed

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.submit(worker), pool.submit(worker)
        one, two = left.result(timeout=15), right.result(timeout=15)
    assert one[0] == two[0]
    assert sorted([one[1], two[1]]) == [False, True]
    a, b, count, audit = snapshot(factory, bid, src, dst)
    assert (a, b, count) == (4, 6, 1)
    assert set(audit) == {(one[0], "transfer_in", 6), (one[0], "transfer_out", -6)}


def test_postgres_rolls_back_after_source_debit(pg_store):
    factory, engine, (bid, uid, src, dst) = pg_store
    counter = {"updates": 0}

    def fault_after_first_debit(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("update stock_levels"):
            counter["updates"] += 1
            if counter["updates"] == 2:
                raise RuntimeError("Simulated destination DB failure")

    event.listen(engine, "before_cursor_execute", fault_after_first_debit)
    try:
        with pytest.raises(RuntimeError, match="Simulated destination"):
            with factory.begin() as session:
                transfer_stock(session, bid, src, dst, "BOX", 5,
                    user_id=uid, idempotency_key="rollback-test-key")
    finally:
        event.remove(engine, "before_cursor_execute", fault_after_first_debit)
    assert counter["updates"] == 2
    assert snapshot(factory, bid, src, dst) == (10, 0, 0, [])
