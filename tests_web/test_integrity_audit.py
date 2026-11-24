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


def test_warehouse_scope_and_tenant_isolation(client):
    register(client,'Audited tenant','audit-first@example.com')
    first=client.get('/api/warehouses').json()[0]['id']
    assert client.get(f'/api/reports/integrity-audit?warehouse_id={first}').status_code==200
    register(client,'Different tenant','audit-second@example.com')
    assert client.get(f'/api/reports/integrity-audit?warehouse_id={first}').status_code==404
    second=client.get('/api/warehouses').json()[0]['id']
    assert client.get(f'/api/reports/integrity-audit?warehouse_id={second}').status_code==200

def test_capacity_warning_reports_real_record_without_mutating_it(client):
    from sqlalchemy import select
    from dispatchforge_app.models import WarehouseBin
    from tests_web.test_warehouse_web import add_stock
    from tests_web.test_warehouse_execution import endpoint, task, complete
    h=register(client,'Audit capacity','audit-capacity@example.com')
    wid=add_stock(client,h,sku='PRODUCT-1',quantity=20)
    bin_id=endpoint(client,h,name='AUDIT-BIN',wid=wid,cap=15)
    task_id=task(client,h,wid,bin_id,10,key='audit-putaway-key').json()['id']
    assert client.post(f'/api/tasks/{task_id}/claim',headers=h).status_code==200
    assert client.post(f'/api/tasks/{task_id}/start',headers=h).status_code==200
    assert complete(client,h,task_id,target='AUDIT-BIN').status_code==200
    with client.app.state.db.SessionLocal() as session:
        bin_record=session.get(WarehouseBin,bin_id)
        bin_record.capacity_units=5
        session.commit()
    before=client.get('/api/locations/stock').json()
    report=client.get(f'/api/reports/integrity-audit?warehouse_id={wid}').json()
    warning=next(row for row in report['checks'] if row['rule']=='bin_overcapacity')
    assert warning['severity']=='warning'
    assert warning['affected_records']==1
    assert warning['sample_ids']==[bin_id]
    assert report['failed_rules']==1
    assert report['ready_for_manual_review'] is False
    assert client.get('/api/locations/stock').json()==before


def test_samples_are_bounded_even_with_many_warning_bins(client):
    from dispatchforge_app.models import WarehouseBin, BinStock, Product, Warehouse
    from sqlalchemy import select
    register(client,'Audit pagination','audit-many@example.com')
    with client.app.state.db.SessionLocal() as s:
        wid=client.get('/api/warehouses').json()[0]['id']
        w=s.get(Warehouse,wid)
        p=Product(business_id=w.business_id,sku='AUDIT-MANY',name='Audit many')
        s.add(p);s.flush()
        for index in range(30):
            b=WarehouseBin(business_id=w.business_id,warehouse_id=w.id,code=f'R-{index:03}',capacity_units=1)
            s.add(b);s.flush()
            s.add(BinStock(business_id=w.business_id,warehouse_id=w.id,bin_id=b.id,
                product_id=p.id,on_hand=2,allocated=0))
        s.commit()
    row=next(r for r in client.get('/api/reports/integrity-audit').json()['checks']
        if r['rule']=='bin_overcapacity')
    assert row['affected_records']==30
    assert row['samples_truncated'] is True
    assert len(row['sample_ids'])==25


def test_integrity_severity_filter_and_summary(client):
    register(client)
    full = client.get('/api/reports/integrity-audit').json()
    assert full['severity_totals'] == {
        'critical': {'failed_rules': 0, 'affected_records': 0},
        'warning': {'failed_rules': 0, 'affected_records': 0},
    }
    critical = client.get('/api/reports/integrity-audit?severity=critical')
    assert critical.status_code == 200
    data = critical.json()
    assert data['severity_filter'] == 'critical'
    assert data['checked_rules'] == 9
    assert all(row['severity'] == 'critical' for row in data['checks'])
    assert client.get('/api/reports/integrity-audit?severity=high').status_code == 422


def test_integrity_rule_filter_and_invalid_rule(client):
    register(client)
    result = client.get('/api/reports/integrity-audit?rule=bin_overcapacity')
    assert result.status_code == 200
    assert result.json()['checked_rules'] == 1
    assert result.json()['checks'][0]['rule'] == 'bin_overcapacity'
    assert client.get('/api/reports/integrity-audit?rule=does_not_exist').status_code == 422
    assert client.get('/api/reports/integrity-audit?rule=bin_overcapacity&severity=critical').json()['checked_rules'] == 0


def test_integrity_csv_requires_authentication_and_has_safe_columns(client):
    assert client.get('/api/reports/integrity-audit.csv').status_code == 401
    register(client)
    result = client.get('/api/reports/integrity-audit.csv?rule=bin_overcapacity')
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['content-type'].startswith('text/csv')
    lines = result.text.splitlines()
    assert lines[0] == 'rule,severity,affected_records,sample_ids,samples_truncated,description'
    assert len(lines) == 2 and lines[1].startswith('bin_overcapacity,warning,')
    assert client.get('/api/reports/integrity-audit.csv?rule=invalid').status_code == 422


def test_integrity_csv_rejects_other_workspace_warehouse(client):
    register(client, 'First export tenant', 'audit-export-first@example.com')
    wid = client.get('/api/warehouses').json()[0]['id']
    register(client, 'Second export tenant', 'audit-export-second@example.com')
    assert client.get(f'/api/reports/integrity-audit.csv?warehouse_id={wid}').status_code == 404
