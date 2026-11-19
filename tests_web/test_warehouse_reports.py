"""End-to-end report contracts: live numbers, authentication, tenant boundaries."""
from tests_web.test_operations_readiness import client, case_open
from tests_web.test_warehouse_web import register


def get(client, name, warehouse=None):
    suffix = f'?warehouse_id={warehouse}' if warehouse is not None else ''
    return client.get(f'/api/reports/{name}{suffix}')

def test_inventory_health_authenticated_and_empty(client):
    assert get(client,'inventory-health').status_code == 401
    register(client)
    row=get(client,'inventory-health').json()
    assert row['source']=='live_database_snapshot'
    assert row['on_hand_units']==row['reserved_units']==row['available_units']==0
    assert get(client,'inventory-health',999999).status_code==404
