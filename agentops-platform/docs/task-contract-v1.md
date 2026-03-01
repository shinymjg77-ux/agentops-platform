# Task Contract v1

## 목적
- 신규 작업을 코어 수정 없이 추가하기 위한 최소 규격 정의

## 요청 스키마
- Endpoint: `POST /v1/tasks`
- Body:
  - `template_name` (string, required)
  - `payload` (object, optional)

예시:

```json
{
  "template_name": "sample_echo_task",
  "payload": {
    "message": "hello"
  }
}
```

## 상태 모델
- `queued`
- `started`
- `retry`
- `success`
- `failure`

참고:
- Celery 원시 상태를 소문자 문자열로 저장/반환한다.

## 템플릿 규칙
- 워커 태스크 이름은 `tasks.<template_name>` 규칙을 따른다.
- 각 템플릿은 JSON 직렬화 가능한 결과를 반환해야 한다.
- 오류는 예외로 던지고 재시도는 Celery 정책에 위임한다.

## 입력 검증 규칙
- API는 템플릿별 payload 스키마를 강제한다.
- 유효하지 않은 payload는 `422`로 거부한다.

### sample_echo_task
- `message`: string | null (optional)
- `force_fail`: boolean (optional, 기본값 `false`)

### sample_http_check_task
- `url`: string (optional, 기본값 `http://api:8000/healthz`)
- `timeout_sec`: integer (optional, `1 <= timeout_sec <= 60`, 기본값 `5`)

## 결과 규격
- 공통 필드 권장:
  - `task_id`: Celery task id
  - 템플릿별 결과 필드
