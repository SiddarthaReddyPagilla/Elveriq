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

def test_bin_capacity_empty_and_tenant_scope(client):
    register(client)
    row=get(client,'bin-capacity').json()
    assert row['placed_units']==0 and row['bins']==0
    assert row['over_capacity_bins']==0
    assert get(client,'bin-capacity',999999).status_code==404

def test_receiving_quality_matches_real_notice(client):
    from tests_web.test_inbound_notices import purchase, notice, scan
    h,w,po,line=purchase(client)
    nid=notice(client,h,po,line).json()['id']
    assert get(client,'receiving-quality').json()['planned_notices']==1
    assert client.post(f'/api/inbound/notices/{nid}/arrive',headers=h).status_code==200
    lid=client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    assert scan(client,h,nid,lid,accepted=4,damaged=1,damage_note='Damaged on unloading').status_code==200
    data=get(client,'receiving-quality').json()
    assert data['accepted_units']==4 and data['damaged_units']==1
    assert data['expected_units'] >= 5

def test_purchase_backlog_tracks_outstanding_orders(client):
    from tests_web.test_inbound_notices import purchase
    h,w,po,line=purchase(client)
    data=get(client,'purchase-backlog').json()
    assert data['open_purchase_orders']>=1
    assert data['outstanding_units']>=1
    assert data['ordered_units']>=data['received_units']

def test_picking_pipeline_has_bounded_statuses(client):
    register(client)
    data=get(client,'picking-pipeline').json()
    assert data['open_picks']==0 and data['staged_units']==0
    assert set(data['by_status'])=={'queued','assigned','in_progress','picked','packed','shipped','canceled'}
    assert get(client,'picking-pipeline',999999).status_code==404

def test_packing_pipeline_zero_cartons(client):
    register(client)
    data=get(client,'packing-pipeline').json()
    assert data['packed_units']==0 and data['awaiting_seal']==0
    assert data['by_status']=={'open':0,'sealed':0,'shipped':0}

def test_dispatch_activity_no_invented_carrier_telemetry(client):
    register(client)
    data=get(client,'dispatch-activity').json()
    assert data['shipments']==0 and data['shipped_last_7_days']==0
    assert data['top_carriers']==[]
