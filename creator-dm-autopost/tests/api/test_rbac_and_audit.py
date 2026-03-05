import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_rbac_requires_header() -> None:
    response = client.get('/rbac/me')
    assert response.status_code == 401
    assert response.json()['detail'] == 'missing_role_header'


def test_rbac_operator_guard() -> None:
    forbidden = client.post('/rbac/operator', headers={'X-Role': 'viewer'})
    allowed = client.post('/rbac/operator', headers={'X-Role': 'operator'})

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()['role'] == 'operator'


def test_audit_middleware_marks_approval_action() -> None:
    response = client.post(
        '/audit/approve',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'tester-1'},
    )

    assert response.status_code == 200
    assert response.headers.get('X-Audit-Logged') == '1'
    assert response.json()['status'] == 'approved'
