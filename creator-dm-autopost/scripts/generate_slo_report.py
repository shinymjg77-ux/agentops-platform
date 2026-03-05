#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.metrics.generation import generation_metrics


def build_report() -> str:
    snapshot = generation_metrics.snapshot()
    now = datetime.now(UTC).isoformat()

    creator_ok = snapshot["creator_p95_ms"] <= 60000
    post_ok = snapshot["post_p95_ms"] <= 30000

    return "\n".join(
        [
            "# Weekly SLO Report",
            "",
            f"- generated_at_utc: {now}",
            "",
            "## Targets",
            "- Creator p95 <= 60000ms",
            "- Post draft p95 <= 30000ms",
            "",
            "## Snapshot",
            f"- creator_count: {snapshot['creator_count']}",
            f"- creator_p95_ms: {snapshot['creator_p95_ms']}",
            f"- creator_slo_met: {str(creator_ok).lower()}",
            f"- post_count: {snapshot['post_count']}",
            f"- post_p95_ms: {snapshot['post_p95_ms']}",
            f"- post_slo_met: {str(post_ok).lower()}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly SLO report")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    if args.output:
        output = Path(args.output)
    else:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        output = ROOT / "docs" / "reports" / f"slo-report-{stamp}.md"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
