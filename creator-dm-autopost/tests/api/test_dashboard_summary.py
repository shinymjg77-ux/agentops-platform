import os
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def _create_approved_post(post_id: str) -> None:
    client.post('/posts/versioned', headers={'X-Role': 'operator'}, json={'post_id': post_id, 'content': 'draft'})
    client.post(f'/approval/posts/{post_id}/submit', headers={'X-Role': 'operator'})
    client.post(f'/approval/posts/{post_id}/approve', headers={'X-Role': 'operator'})


def test_dashboard_delivery_summary_counts() -> None:
    post_id = f"dash-{uuid.uuid4().hex[:8]}"
    recipient_id = f"dash-user-{uuid.uuid4().hex[:6]}"
    _create_approved_post(post_id)

    client.post(
        f'/consents/{recipient_id}',
        headers={'X-Role': 'operator'},
        json={'status': 'opt_in', 'source': 'csv', 'proof_ref': 'p'},
    )

    client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_id,
            'content': 'dashboard test',
            'idempotency_key': f'idem-{uuid.uuid4().hex[:8]}',
        },
    )

    summary = client.get('/dashboard/delivery-summary', headers={'X-Role': 'viewer'})
    assert summary.status_code == 200
    body = summary.json()

    assert body['total'] >= 1
    assert {'queued', 'sending', 'sent', 'failed', 'retrying', 'cancelled'} <= set(body.keys())
