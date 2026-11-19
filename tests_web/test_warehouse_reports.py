"""End-to-end report contracts: live numbers, authentication, tenant boundaries."""
from tests_web.test_operations_readiness import client, case_open
from tests_web.test_warehouse_web import register


def get(client, name, warehouse=None):
    suffix = f'?warehouse_id={warehouse}' if warehouse is not None else ''
    return client.get(f'/api/reports/{name}{suffix}')
