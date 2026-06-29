"""Small local benchmark helpers."""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Any

from deep_context_federation.builder import build_federation


def benchmark_build(
    *,
    manifest_path: Path,
    root: Path,
    output_dir: Path,
    iterations: int = 5,
) -> dict[str, Any]:
    timings: list[float] = []
    last_summary: dict[str, Any] = {}
    iterations = max(1, int(iterations))
    for _ in range(iterations):
        start = time.perf_counter()
        payload = build_federation(
            manifest_path=manifest_path,
            root=root,
            output_dir=output_dir,
            write=False,
        )
        timings.append(time.perf_counter() - start)
        last_summary = dict(payload.get("summary") or {})
    return {
        "schema_version": "deep_context_federation_benchmark_v1",
        "iterations": iterations,
        "seconds_min": min(timings),
        "seconds_max": max(timings),
        "seconds_mean": statistics.fmean(timings),
        "seconds_median": statistics.median(timings),
        "last_summary": last_summary,
    }
