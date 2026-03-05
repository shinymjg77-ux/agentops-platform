import os
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_approval_flow_and_invalid_transition_guard() -> None:
    post_id = f"approve-{uuid.uuid4().hex[:8]}"

    created = client.post(
        '/posts/versioned',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'author-1'},
        json={'post_id': post_id, 'content': 'draft content'},
    )
    assert created.status_code == 200

    submitted = client.post(
        f'/approval/posts/{post_id}/submit',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'operator-1'},
    )
    assert submitted.status_code == 200
    assert submitted.json()['status'] == 'pending_approval'

    approved = client.post(
        f'/approval/posts/{post_id}/approve',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'operator-2'},
    )
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'

    invalid = client.post(
        f'/approval/posts/{post_id}/transition',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'operator-3'},
        json={'target_status': 'draft'},
    )
    assert invalid.status_code == 400
    assert invalid.json()['detail'] == 'invalid_state_transition'


def test_approval_read_requires_valid_role() -> None:
    post_id = f"approve-{uuid.uuid4().hex[:8]}"

    client.post(
        '/posts/versioned',
        headers={'X-Role': 'operator'},
        json={'post_id': post_id, 'content': 'draft content'},
    )

    forbidden = client.get(f'/approval/posts/{post_id}')
    allowed = client.get(f'/approval/posts/{post_id}', headers={'X-Role': 'viewer'})

    assert forbidden.status_code == 401
    assert allowed.status_code == 200
