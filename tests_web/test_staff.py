"""Staff invites: single-use tokens, authorization, deactivation and tenant scope."""
from datetime import timedelta
import re
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.models import StaffInvitation, User, utcnow
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'staff.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db, Settings('development','staff-secret',url))) as c:
        c.test_db=db
        yield c
    db.dispose()


def invitation(c,h,email='employee@example.com',role='staff'):
    return c.post('/api/staff/invitations',headers=h,json={'email':email,'role':role})


def test_invitation_acceptance_and_single_use(client):
    h=register(client)
    invite=invitation(client,h)
    assert invite.status_code==201,invite.text
    token=invite.json()['token']
    response=client.post('/api/staff/invitations/accept',json={
        'token':token,'password':'employee-password-123'})
    assert response.status_code==201
    assert response.json()['role']=='staff'
    assert client.post('/api/staff/invitations/accept',json={
        'token':token,'password':'employee-password-123'}).status_code==400
    assert len(client.get('/api/staff').json())==2


def test_deactivated_account_loses_access_and_login(client):
    h=register(client)
    token=invitation(client,h).json()['token']
    staff=client.post('/api/staff/invitations/accept',json={
        'token':token,'password':'employee-password-123'}).json()['id']
    assert client.patch(f'/api/staff/{staff}/role',headers=h,json={'role':'disabled'}).status_code==200
    assert client.patch('/api/staff/1/role',headers=h,json={'role':'disabled'}).status_code==403
    # The disabled account is also blocked from signing back in.
    slug=client.get('/app').text.split('class="slug-code">')[1].split('</code>')[0]
    token=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':token},follow_redirects=False)
    login_csrf=re.search(r'name="csrf" value="([^"]+)"',client.get('/login').text).group(1)
    bad=client.post('/login',data={'csrf':login_csrf,'workspace':slug,
        'email':'employee@example.com','password':'employee-password-123'})
    assert bad.status_code==401


def test_role_permission_and_expiry(client):
    h=register(client)
    assert invitation(client,h,role='owner').status_code==400
    token=invitation(client,h).json()['token']
    with client.test_db.SessionLocal() as session:
        inv=session.scalar(select(StaffInvitation).where(StaffInvitation.email=='employee@example.com'))
        inv.expires_at=utcnow()-timedelta(minutes=1)
        session.commit()
    assert client.post('/api/staff/invitations/accept',json={
        'token':token,'password':'employee-password-123'}).status_code==400
    assert len(client.get('/api/staff').json())==1


def test_owner_only_and_cross_tenant_staff_admin(client):
    h=register(client)
    staff_token=invitation(client,h).json()['token']
    employee=client.post('/api/staff/invitations/accept',json={
        'token':staff_token,'password':'employee-password-123'}).json()['id']
    logout_token=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':logout_token},follow_redirects=False)
    h2=register(client,'Other Company','other@example.com')
    assert len(client.get('/api/staff').json())==1
    assert client.patch(f'/api/staff/{employee}/role',headers=h2,
                        json={'role':'manager'}).status_code==404
    assert client.post('/api/staff/invitations',json={'email':'x@y.com','role':'staff'}).status_code==403
