import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_audit_log_required_fields_ac6() -> None:
    trigger = client.post(
        '/audit/approve',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'ac6-tester'},
    )
    assert trigger.status_code == 200

    logs = client.get('/audit/logs?limit=20', headers={'X-Role': 'viewer'})
    assert logs.status_code == 200

    entries = logs.json()['logs']
    target = next((item for item in entries if item['actor_id'] == 'ac6-tester'), None)
    assert target is not None

    assert target['actor_id']
    assert target['action']
    assert target['target_type']
    assert target['target_id']
    assert target['timestamp']
