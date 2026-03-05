import os
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def _create_approved_post(post_id: str) -> None:
    created = client.post(
        '/posts/versioned',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'author'},
        json={'post_id': post_id, 'content': 'draft content'},
    )
    assert created.status_code == 200

    submitted = client.post(
        f'/approval/posts/{post_id}/submit',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'operator-submit'},
    )
    assert submitted.status_code == 200

    approved = client.post(
        f'/approval/posts/{post_id}/approve',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'operator-approve'},
    )
    assert approved.status_code == 200


def _upsert_opt_in(recipient_id: str) -> None:
    response = client.post(
        f'/consents/{recipient_id}',
        headers={'X-Role': 'operator'},
        json={'status': 'opt_in', 'source': 'csv_import', 'proof_ref': 'proof-1'},
    )
    assert response.status_code == 200


def test_delivery_requires_approval_gate() -> None:
    post_id = f"post-{uuid.uuid4().hex[:8]}"
    recipient_id = f"user-{uuid.uuid4().hex[:6]}"

    client.post(
        '/posts/versioned',
        headers={'X-Role': 'operator'},
        json={'post_id': post_id, 'content': 'draft content'},
    )
    _upsert_opt_in(recipient_id)

    scheduled = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_id,
            'content': 'hello',
            'idempotency_key': f'idem-{uuid.uuid4().hex[:8]}',
        },
    )
    assert scheduled.status_code == 400
    assert scheduled.json()['detail'] == 'approval_required'


def test_scheduled_delivery_sent_and_idempotent() -> None:
    post_id = f"post-{uuid.uuid4().hex[:8]}"
    recipient_id = f"user-{uuid.uuid4().hex[:6]}"
    idem = f"idem-{uuid.uuid4().hex[:10]}"

    _create_approved_post(post_id)
    _upsert_opt_in(recipient_id)

    first = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_id,
            'content': 'hello world',
            'idempotency_key': idem,
        },
    )
    assert first.status_code == 200
    assert first.json()['deduplicated'] is False

    duplicate = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_id,
            'content': 'hello world',
            'idempotency_key': idem,
        },
    )
    assert duplicate.status_code == 200
    assert duplicate.json()['deduplicated'] is True
    assert duplicate.json()['delivery_id'] == first.json()['delivery_id']

    processed = client.post(
        '/deliveries/process-due',
        headers={'X-Role': 'operator'},
        json={'force_process': True},
    )
    assert processed.status_code == 200
    assert processed.json()['processed'] >= 1

    result = client.get(
        f"/deliveries/{first.json()['delivery_id']}",
        headers={'X-Role': 'viewer'},
    )
    assert result.status_code == 200
    assert result.json()['status'] == 'sent'


def test_retry_policy_and_consent_enforcement() -> None:
    post_id = f"post-{uuid.uuid4().hex[:8]}"
    recipient_missing = f"user-{uuid.uuid4().hex[:6]}"
    recipient_opt_out = f"user-{uuid.uuid4().hex[:6]}"
    recipient_retry = f"user-{uuid.uuid4().hex[:6]}"

    _create_approved_post(post_id)

    missing = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_missing,
            'content': 'hello',
            'idempotency_key': f'idem-{uuid.uuid4().hex[:8]}',
        },
    )
    assert missing.status_code == 400
    assert missing.json()['detail'] == 'consent_missing'

    out = client.post(
        f'/consents/{recipient_opt_out}',
        headers={'X-Role': 'operator'},
        json={'status': 'opt_out', 'source': 'manual', 'proof_ref': 'proof-optout'},
    )
    assert out.status_code == 200

    revoked = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_opt_out,
            'content': 'hello',
            'idempotency_key': f'idem-{uuid.uuid4().hex[:8]}',
        },
    )
    assert revoked.status_code == 400
    assert revoked.json()['detail'] == 'consent_revoked'

    _upsert_opt_in(recipient_retry)
    retry = client.post(
        '/deliveries/schedule',
        headers={'X-Role': 'operator'},
        json={
            'post_id': post_id,
            'recipient_id': recipient_retry,
            'content': '[force:429] please retry',
            'idempotency_key': f'idem-{uuid.uuid4().hex[:8]}',
        },
    )
    assert retry.status_code == 200
    delivery_id = retry.json()['delivery_id']

    for _ in range(3):
        proc = client.post(
            '/deliveries/process-due',
            headers={'X-Role': 'operator'},
            json={'force_process': True},
        )
        assert proc.status_code == 200

    failed = client.get(f'/deliveries/{delivery_id}', headers={'X-Role': 'viewer'})
    assert failed.status_code == 200
    assert failed.json()['status'] == 'failed'
    assert failed.json()['attempts'] == 3

    alerts = client.get('/alerts/failures?limit=20', headers={'X-Role': 'viewer'})
    assert alerts.status_code == 200
    matched = next((a for a in alerts.json()['alerts'] if a['delivery_id'] == delivery_id), None)
    assert matched is not None
    assert matched['category'] == 'rate_limit'
