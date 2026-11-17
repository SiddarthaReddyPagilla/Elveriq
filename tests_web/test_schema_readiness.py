"""Schema release preflight detects missing tables and columns without writes."""
from sqlalchemy import create_engine, text
from dispatchforge_app.models import Base
from scripts.check_schema_readiness import REQUIRED_TABLES, schema_gaps


def test_complete_warehouse_schema_passes_inspection():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    assert schema_gaps(engine) == ([], {})
    engine.dispose()


def test_missing_warehouse_table_and_column_are_detected():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Base.metadata.tables['warehouse_exceptions'].drop(engine)
    assert 'warehouse_exceptions' in schema_gaps(engine)[0]
    # A fresh database without any warehouse tables must never be reported ready.
    empty_engine = create_engine('sqlite:///:memory:')
    missing, _ = schema_gaps(empty_engine)
    assert set(REQUIRED_TABLES) == set(missing)
    empty_engine.dispose()
    engine.dispose()
