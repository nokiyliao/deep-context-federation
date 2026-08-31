"""Cheap event queue used by hooks, task leases, and the refresh watchdog."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from filelock import FileLock, Timeout

from .storage import atomic_write_json, utc_now

EventKind = Literal["git", "lease", "receipt", "operator"]


class EventReconcileBusy(RuntimeError):
    """Another event reconciler owns the bounded batch."""


def event_root(repo_root: Path, *, runtime_root: Path | None = None) -> Path:
    configured = os.getenv("DCF_RUNTIME_ROOT") or os.getenv("UTM_DCF_V2_RUNTIME_ROOT")
    base = (
        runtime_root.expanduser().resolve()
        if runtime_root is not None
        else (
            Path(configured).expanduser().resolve()
            if configured
            else repo_root / "output" / "dcf_runtime" / "v2"
        )
    )
    return base / "events"


@contextmanager
def event_reconcile_lock(
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
    timeout: float = 30.0,
) -> Iterator[None]:
    root = event_root(repo_root, runtime_root=runtime_root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(root / "reconcile.lock"), timeout=timeout):
            yield
    except Timeout as exc:
        raise EventReconcileBusy("another DCF event reconciler owns the batch") from exc


def enqueue_event(
    repo_root: Path,
    *,
    kind: EventKind,
    payload: dict[str, Any] | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    pending = event_root(repo_root, runtime_root=runtime_root) / "pending"
    event_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
    event = {
        "schema_version": "dcf_refresh_event_v2",
        "event_id": event_id,
        "created_at": utc_now(),
        "kind": kind,
        "payload": payload or {},
        "authority_effect": "none",
        "no_apply": True,
    }
    atomic_write_json(pending / f"{event_id}.json", event)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {**event, "enqueue_ms": round(elapsed_ms, 3), "target_ms": 50, "target_met": elapsed_ms < 50}


def pending_events(
    repo_root: Path, *, runtime_root: Path | None = None
) -> list[tuple[Path, dict[str, Any]]]:
    pending = event_root(repo_root, runtime_root=runtime_root) / "pending"
    rows: list[tuple[Path, dict[str, Any]]] = []
    if not pending.is_dir():
        return rows
    for path in sorted(pending.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            payload = {
                "event_id": path.stem,
                "kind": "unknown",
                "payload": {},
                "malformed": True,
                "parse_error": f"{type(exc).__name__}: {exc}",
            }
        rows.append((path, payload))
    return rows


def acknowledge_events(rows: list[tuple[Path, dict[str, Any]]], *, generation_id: str) -> Path | None:
    if not rows:
        return None
    root = rows[0][0].parent.parent
    receipts = root / "processed"
    batch_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
    malformed_rows = [(path, payload) for path, payload in rows if payload.get("malformed") is True]
    receipt = {
        "schema_version": "dcf_event_batch_receipt_v2",
        "batch_id": batch_id,
        "processed_at": utc_now(),
        "generation_id": generation_id,
        "event_ids": [str(payload.get("event_id", path.stem)) for path, payload in rows],
        "kinds": sorted({str(payload.get("kind", "unknown")) for _, payload in rows}),
        "malformed_event_count": len(malformed_rows),
        "quarantined_event_ids": [str(payload.get("event_id", path.stem)) for path, payload in malformed_rows],
        "authority_effect": "none",
        "no_apply": True,
    }
    receipt_path = receipts / f"{generation_id}-{batch_id}.json"
    atomic_write_json(receipt_path, receipt)
    quarantine = root / "quarantine"
    for path, payload in rows:
        try:
            if payload.get("malformed") is True:
                quarantine.mkdir(parents=True, exist_ok=True)
                os.replace(path, quarantine / path.name)
            else:
                path.unlink()
        except FileNotFoundError:
            pass
    return receipt_path
