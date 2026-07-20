"""Minimal, real concurrent load test against a live backend instance.

Not a mock or a synthetic benchmark against an in-process test client --
this issues real HTTP requests, over the network, against whatever
--base-url points at (a running `uvicorn app.main:app`, in-container or
otherwise), and reports p50/p95/p99 latency and error rate from what
actually came back.

Usage (from inside a container/host with network access to the target):
    python -m scripts.load_test --base-url http://localhost:8001 \
        --concurrency 50 --duration 30

Scope: GET /api/v1/catalog/offers (public, unauthenticated, read-only) --
the one endpoint every anonymous visitor's browsing traffic exercises
regardless of login state, and the only realistic high-volume path this
platform has that requires no seeded per-user state to exercise
meaningfully. Authenticated/write-path load testing (checkout, payment
initiation) needs seeded households/offers/sessions per virtual user and
is intentionally out of scope for this first pass -- see the paired
runbook entry (docs/runbooks/load-testing.md) for what that would require
and why it was not attempted here.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class Result:
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    errors: int = 0


async def _worker(
    client: httpx.AsyncClient, path: str, stop_at: float, result: Result
) -> None:
    while time.monotonic() < stop_at:
        start = time.monotonic()
        try:
            response = await client.get(path)
        except httpx.HTTPError:
            result.errors += 1
            continue
        elapsed_ms = (time.monotonic() - start) * 1000
        result.latencies_ms.append(elapsed_ms)
        result.status_counts[response.status_code] = (
            result.status_counts.get(response.status_code, 0) + 1
        )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return ordered[index]


async def run(base_url: str, concurrency: int, duration: float, path: str) -> None:
    result = Result()
    stop_at = time.monotonic() + duration
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        await asyncio.gather(
            *(_worker(client, path, stop_at, result) for _ in range(concurrency))
        )

    total_requests = len(result.latencies_ms) + result.errors
    print(f"target: {base_url}{path}")
    print(f"concurrency: {concurrency}, duration: {duration}s")
    print(f"total requests: {total_requests} ({total_requests / duration:.1f} req/s)")
    print(f"errors (connection-level): {result.errors}")
    print(f"status codes: {result.status_counts}")
    if result.latencies_ms:
        print(f"latency p50: {_percentile(result.latencies_ms, 0.50):.1f} ms")
        print(f"latency p95: {_percentile(result.latencies_ms, 0.95):.1f} ms")
        print(f"latency p99: {_percentile(result.latencies_ms, 0.99):.1f} ms")
        print(f"latency mean: {statistics.mean(result.latencies_ms):.1f} ms")
        print(f"latency max: {max(result.latencies_ms):.1f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--path", default="/api/v1/catalog/offers")
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.concurrency, args.duration, args.path))


if __name__ == "__main__":
    main()
