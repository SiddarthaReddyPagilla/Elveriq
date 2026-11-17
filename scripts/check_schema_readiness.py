"""Read-only preflight for warehouse execution schema (never runs migrations)."""
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from dispatchforge_app.models import Base
from dispatchforge_app.settings import load_settings

# Key tables introduced by the warehouse execution, inbound and ops releases.
REQUIRED_TABLES = (
    'warehouse_bins', 'bin_stocks', 'warehouse_tasks', 'warehouse_task_events',
    'bin_cycle_counts', 'outbound_picks', 'outbound_pick_events',
    'outbound_cartons', 'outbound_carton_items', 'outbound_shipments',
    'inbound_notices', 'inbound_notice_lines', 'inbound_receipts',
    'inbound_notice_events', 'warehouse_exceptions',
    'warehouse_exception_events', 'shipment_tracking_updates',
)


def schema_gaps(engine):
    """Return missing tables/columns without modifying the target database."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing_tables = sorted(set(REQUIRED_TABLES) - existing)
    missing_columns = {}
    for name in REQUIRED_TABLES:
        if name not in existing:
            continue
        actual = {col['name'] for col in inspector.get_columns(name)}
        required = set(Base.metadata.tables[name].columns.keys())
        absent = sorted(required - actual)
        if absent:
            missing_columns[name] = absent
    return missing_tables, missing_columns


def main():
    engine = None
    try:
        settings = load_settings()
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        missing_tables, missing_columns = schema_gaps(engine)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        print(f'Schema preflight could not complete: {type(exc).__name__}', file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print('Warehouse schema preflight (read-only)')
    if missing_tables:
        print('Missing tables:', ', '.join(missing_tables))
    for name, columns in sorted(missing_columns.items()):
        print(f'Missing columns in {name}: {", ".join(columns)}')
    if missing_tables or missing_columns:
        print('NOT READY: apply reviewed migrations to staging before release.')
        return 2
    print(f'PASS: {len(REQUIRED_TABLES)} warehouse tables and required columns present.')
    print('Note: this is not a data-integrity, concurrency or migration-history audit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
