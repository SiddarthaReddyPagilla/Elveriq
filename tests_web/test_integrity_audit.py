"""Warehouse inventory safety audit: API contract and tenant boundaries."""
from tests_web.test_operations_readiness import client
from tests_web.test_warehouse_web import register

def test_integrity_audit_requires_authentication(client):
    assert client.get('/api/reports/integrity-audit').status_code == 401

def test_integrity_audit_empty_workspace_clean(client):
    register(client)
    response=client.get('/api/reports/integrity-audit')
    assert response.status_code==200
    data=response.json()
    assert data['source']=='live_database_read_only'
    assert data['read_only'] and data['no_repairs_performed']
    assert data['checked_rules']==len(data['checks'])==11
    assert data['failed_rules']==0
    assert data['ready_for_manual_review'] is True
    assert all(row['affected_records']==0 for row in data['checks'])

def test_invalid_warehouse_is_hidden(client):
    register(client)
    assert client.get('/api/reports/integrity-audit?warehouse_id=999999').status_code==404

def test_audit_rejects_nonpositive_warehouse_id(client):
    register(client)
    assert client.get('/api/reports/integrity-audit?warehouse_id=0').status_code==422
