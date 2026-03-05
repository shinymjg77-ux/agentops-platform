import math
from dataclasses import dataclass, field


@dataclass(slots=True)
class GenerationMetricsStore:
    creator_latencies_ms: list[int] = field(default_factory=list)
    post_latencies_ms: list[int] = field(default_factory=list)

    def record_creator(self, elapsed_ms: int) -> None:
        self.creator_latencies_ms.append(max(elapsed_ms, 0))

    def record_post(self, elapsed_ms: int) -> None:
        self.post_latencies_ms.append(max(elapsed_ms, 0))

    @staticmethod
    def _p95(values: list[int]) -> int:
        if not values:
            return 0
        sorted_values = sorted(values)
        rank = max(1, math.ceil(len(sorted_values) * 0.95))
        return sorted_values[rank - 1]

    def snapshot(self) -> dict[str, int]:
        return {
            "creator_count": len(self.creator_latencies_ms),
            "creator_p95_ms": self._p95(self.creator_latencies_ms),
            "post_count": len(self.post_latencies_ms),
            "post_p95_ms": self._p95(self.post_latencies_ms),
        }


generation_metrics = GenerationMetricsStore()
