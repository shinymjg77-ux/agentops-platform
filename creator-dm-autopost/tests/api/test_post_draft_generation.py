import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath('api'))

from app.main import app


client = TestClient(app)


def test_post_draft_ac2_banned_filtered_and_length_enforced() -> None:
    response = client.post(
        '/posts/draft',
        headers={'X-Role': 'operator', 'X-Actor-Id': 'tester-post'},
        json={
            'persona_name': 'Nova Studio',
            'persona_tone': '친근한 실무형',
            'persona_topic': '온보딩 개선',
            'style_sample': '핵심만 전달합니다.',
            'template': '{product_name}는 사기 없이 빠르게 시작할 수 있게 도와줍니다. {benefit}',
            'variables': {
                'product_name': 'CreatorDM',
                'benefit': '체크리스트를 바로 제공합니다.',
            },
            'banned_keywords': ['사기'],
            'max_length': 180,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body['character_count'] <= body['max_length']
    assert '사기' not in body['content'].lower()
    assert body['violations'] == []
    assert 'product_name' in body['applied_variables']
    assert response.headers.get('X-Audit-Logged') == '1'


def test_post_draft_viewer_forbidden() -> None:
    response = client.post(
        '/posts/draft',
        headers={'X-Role': 'viewer'},
        json={
            'persona_name': 'Kai Lab',
            'persona_tone': '전문가형',
            'persona_topic': '재구매 유도',
            'template': '테스트 메시지',
        },
    )
    assert response.status_code == 403
