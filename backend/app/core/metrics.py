from __future__ import annotations

from collections import Counter
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._duration_ms: Counter[tuple[str, str]] = Counter()

    def observe(self, method: str, route: str, status_code: int, duration_ms: int) -> None:
        with self._lock:
            self._requests[(method, route, status_code)] += 1
            self._duration_ms[(method, route)] += duration_ms

    def render_prometheus(self) -> str:
        lines = [
            "# HELP pet_platform_http_requests_total Completed HTTP requests.",
            "# TYPE pet_platform_http_requests_total counter",
        ]
        with self._lock:
            requests = self._requests.copy()
            durations = self._duration_ms.copy()
        for (method, route, status_code), value in sorted(requests.items()):
            labels = f'method="{method}",route="{route}",status="{status_code}"'
            lines.append(f"pet_platform_http_requests_total{{{labels}}} {value}")
        lines.extend(
            (
                "# HELP pet_platform_http_request_duration_milliseconds_total "
                "Accumulated request duration.",
                "# TYPE pet_platform_http_request_duration_milliseconds_total counter",
            )
        )
        for (method, route), value in sorted(durations.items()):
            labels = f'method="{method}",route="{route}"'
            lines.append(
                f"pet_platform_http_request_duration_milliseconds_total{{{labels}}} {value}"
            )
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
