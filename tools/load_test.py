"""Lightweight concurrent load test against a running backend (Phase 12).

Not a claim about production-scale capacity - this is a single-machine,
local-Postgres check that the app holds up under realistic concurrency and
that p95 latency stays reasonable, using only httpx (already a backend
dependency) rather than pulling in a dedicated load-testing framework for
a one-off check.

Usage: python tools/load_test.py [--base-url http://127.0.0.1:8000/api/v1]
                                  [--concurrency 20] [--requests 200]
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def _timed_get(client: httpx.AsyncClient, path: str) -> tuple[float, int]:
    start = time.monotonic()
    try:
        response = await client.get(path)
        status = response.status_code
    except httpx.HTTPError:
        status = -1
    return (time.monotonic() - start) * 1000, status


async def run(base_url: str, path: str, concurrency: int, total_requests: int) -> None:
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_get(client: httpx.AsyncClient) -> None:
        async with semaphore:
            latency_ms, status = await _timed_get(client, path)
            latencies.append(latency_ms)
            statuses[status] = statuses.get(status, 0) + 1

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        wall_start = time.monotonic()
        await asyncio.gather(*(_bounded_get(client) for _ in range(total_requests)))
        wall_seconds = time.monotonic() - wall_start

    latencies.sort()

    def _pct(p: float) -> float:
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    print(f"\n=== {path} - concurrency={concurrency}, requests={total_requests} ===")
    print(f"wall time:   {wall_seconds:.2f}s  ({total_requests / wall_seconds:.1f} req/s)")
    print(f"latency ms:  min={min(latencies):.1f} p50={_pct(0.5):.1f} "
          f"p95={_pct(0.95):.1f} p99={_pct(0.99):.1f} max={max(latencies):.1f} "
          f"mean={statistics.mean(latencies):.1f}")
    print(f"status codes: {statuses}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=200)
    args = parser.parse_args()

    await run(args.base_url, "/courses", args.concurrency, args.requests)


if __name__ == "__main__":
    asyncio.run(main())
