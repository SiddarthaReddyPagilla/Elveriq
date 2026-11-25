"""Staging/CI-only transaction proof; requires ELVERIQ_TEST_POSTGRES_URL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from dispatchforge_app.dock_service import create_door, schedule
from dispatchforge_app.models import DockAppointment
from tests_web.test_transfers_postgres import pg_store


def test_two_workers_cannot_double_book_same_dock_postgres(pg_store):
    factory, _, (bid, uid, wid, _) = pg_store
    with factory.begin() as session:
        door_id = create_door(session, bid, wid, 'PG-DOCK-A', 'both')['id']
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    end = start + timedelta(hours=1)
    barrier = Barrier(2)
    def book(key):
        barrier.wait(timeout=10)
        from dispatchforge_app.errors import DomainError
        try:
            with factory.begin() as session:
                result, replay = schedule(session,bid,wid,door_id,'inbound',
                   'ASN-PG-BOOK',start.isoformat(),end.isoformat(),uid,key)
                return ('ok', result['id'])
        except DomainError as err:
            return ('error', err.status)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(book, 'pg-dock-concurrent-a')
        two = pool.submit(book, 'pg-dock-concurrent-b')
        results = [one.result(timeout=25), two.result(timeout=25)]
    assert sorted(x[0] for x in results) == ['error', 'ok']
    assert ('error',409) in results
    with factory() as session:
        assert session.scalar(select(func.count(DockAppointment.id)).where(
            DockAppointment.business_id==bid, DockAppointment.door_id==door_id))==1
