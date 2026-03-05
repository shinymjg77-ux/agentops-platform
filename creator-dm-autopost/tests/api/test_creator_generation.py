import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_creator_generation_ac1_default_five_personas() -> None:
    response = client.post(
        '/creators/generate',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'tester-creator'},
        json={
            'campaign_goal': '신규 사용자 온보딩 전환율 개선',
            'target_segment': '초기 운영자',
            'banned_keywords': ['사기'],
            'channel_constraints': ['discord dm 2000 chars'],
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body['requested_count'] == 5
    assert body['generated_count'] == 5
    assert body['elapsed_ms'] < 60000
    assert response.headers.get('X-Audit-Logged') == '1'

    personas = body['personas']
    assert len(personas) == 5
    for persona in personas:
        assert persona['name']
        assert persona['tone']
        assert persona['topic']
        assert persona['style_sample']


def test_creator_generation_respects_custom_count() -> None:
    response = client.post(
        '/creators/generate',
        headers={'X-Role': 'operator'},
        json={
            'campaign_goal': '구매 전환 개선',
            'target_segment': '재방문 유저',
            'count': 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['requested_count'] == 3
    assert body['generated_count'] == 3
    assert len(body['personas']) == 3


def test_creator_generation_viewer_forbidden() -> None:
    response = client.post(
        '/creators/generate',
        headers={'X-Role': 'viewer'},
        json={
            'campaign_goal': '구독 유지율 개선',
            'target_segment': '체험판 사용자',
        },
    )

    assert response.status_code == 403
