#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "사용법: scripts/add_work_log.sh \"제목\"" >&2
  exit 1
fi

TITLE="$1"
LOG_FILE="docs/WORK_LOG.md"
NOW_KST="$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M KST')"

cat >> "$LOG_FILE" <<EOF

## ${NOW_KST} - ${TITLE}
- 배경:
  - 
- 문제/미흡점:
  - 
- 원인:
  - 
- 조치:
  - 
- 다음 액션:
  - 
EOF

echo "추가 완료: ${LOG_FILE}"
