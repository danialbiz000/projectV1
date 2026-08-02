"""In-process HTTP request metrics (M6), exposed at GET /metrics in
Prometheus text-exposition format. Hand-rolled rather than depending on
``prometheus_client``, matching the project's zero-external-services-by-
default philosophy: nothing extra needs to run for a single instance to be
scrapeable.

Process-local only — these counters reset on restart and do not aggregate
across multiple workers/instances. A multi-process deployment needs
per-instance scraping or a push-gateway; see docs/DEPLOYMENT.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_request_count: dict[tuple[str, str, str], int] = defaultdict(int)
_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_started_at = time.time()


def record_request(
    method: str, path_template: str, status_code: int, duration_seconds: float
) -> None:
    with _lock:
        _request_count[(method, path_template, str(status_code))] += 1
        _duration_sum[(method, path_template)] += duration_seconds
        _duration_count[(method, path_template)] += 1


def reset() -> None:
    """Test-only: clear all counters so assertions don't depend on
    whatever else ran earlier in the process."""
    with _lock:
        _request_count.clear()
        _duration_sum.clear()
        _duration_count.clear()


def render_prometheus() -> str:
    lines = [
        "# HELP remip_http_requests_total Total HTTP requests handled.",
        "# TYPE remip_http_requests_total counter",
    ]
    with _lock:
        for (method, path, status_code), count in sorted(_request_count.items()):
            lines.append(
                "remip_http_requests_total"
                f'{{method="{method}",path="{path}",status="{status_code}"}} {count}'
            )
        lines.append(
            "# HELP remip_http_request_duration_seconds_sum Cumulative request time per route."
        )
        lines.append("# TYPE remip_http_request_duration_seconds_sum counter")
        for (method, path), total in sorted(_duration_sum.items()):
            lines.append(
                "remip_http_request_duration_seconds_sum"
                f'{{method="{method}",path="{path}"}} {total:.6f}'
            )
        lines.append(
            "# HELP remip_http_request_duration_seconds_count Requests timed per route."
        )
        lines.append("# TYPE remip_http_request_duration_seconds_count counter")
        for (method, path), count in sorted(_duration_count.items()):
            lines.append(
                "remip_http_request_duration_seconds_count"
                f'{{method="{method}",path="{path}"}} {count}'
            )
    lines.append("# HELP remip_process_uptime_seconds Seconds since process start.")
    lines.append("# TYPE remip_process_uptime_seconds gauge")
    lines.append(f"remip_process_uptime_seconds {time.time() - _started_at:.3f}")
    return "\n".join(lines) + "\n"
