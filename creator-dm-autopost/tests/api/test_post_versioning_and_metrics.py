import os
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_post_revision_history_flow() -> None:
    post_id = f"post-{uuid.uuid4().hex[:8]}"

    created = client.post(
        '/posts/versioned',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'editor-1'},
        json={'post_id': post_id, 'content': 'v1 content'},
    )
    assert created.status_code == 200
    assert created.json()['version'] == 1

    appended = client.post(
        f'/posts/{post_id}/revisions',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'editor-2'},
        json={'content': 'v2 content'},
    )
    assert appended.status_code == 200
    assert appended.json()['version'] == 2

    history = client.get(
        f'/posts/{post_id}/revisions',
        headers={'X-Role': 'viewer', 'X-Actor-Id': 'viewer-1'},
    )
    assert history.status_code == 200
    revisions = history.json()['revisions']
    assert [item['version'] for item in revisions] == [1, 2]


def test_generation_metrics_snapshot() -> None:
    client.post(
        '/creators/generate',
        headers={'X-Role': 'operator'},
        json={'campaign_goal': '테스트', 'target_segment': '운영자'},
    )
    client.post(
        '/posts/draft',
        headers={'X-Role': 'operator'},
        json={
            'persona_name': 'Nova Studio',
            'persona_tone': '친근한 실무형',
            'persona_topic': '테스트',
            'template': '{name} 템플릿',
            'variables': {'name': 'CreatorDM'},
        },
    )

    metrics = client.get('/metrics/generation', headers={'X-Role': 'viewer'})
    assert metrics.status_code == 200
    body = metrics.json()

    assert body['creator_count'] >= 1
    assert body['post_count'] >= 1
    assert body['creator_p95_ms'] >= 0
    assert body['post_p95_ms'] >= 0
