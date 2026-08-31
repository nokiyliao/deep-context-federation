"""Atomic immutable-generation storage for DCF v2."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from .models import DcfSnapshot, GenerationFile, GenerationManifest, GenerationPointer


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_reference(path: Path, *, repo_root: Path) -> str:
    """Return a repo-relative reference when possible, otherwise an absolute path."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo_root.resolve()))
    except ValueError:
        return str(resolved)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_bytes(path, canonical_json_bytes(payload))


class GenerationUnavailable(RuntimeError):
    """Raised when no consumable generation exists."""


class GenerationTransactionError(RuntimeError):
    """Raised when a generation cannot be built or published."""


class GenerationStore:
    def __init__(self, repo_root: Path, runtime_root: Path | None = None) -> None:
        self.repo_root = repo_root.resolve()
        configured = os.getenv("DCF_RUNTIME_ROOT") or os.getenv("UTM_DCF_V2_RUNTIME_ROOT")
        self.root = (
            runtime_root.expanduser().resolve()
            if runtime_root is not None
            else (
                Path(configured).expanduser().resolve()
                if configured
                else (self.repo_root / "output" / "dcf_runtime" / "v2").resolve()
            )
        )
        self.generations = self.root / "generations"
        self.staging = self.root / ".staging"
        self.failures = self.root / "failures"
        self.current_path = self.root / "current.json"
        self.last_good_path = self.root / "last_good.json"
        self.lock_path = self.root / "refresh.lock"
        self.retention_mode = (
            os.getenv("DCF_RETENTION_MODE")
            or os.getenv("UTM_DCF_RETENTION_MODE")
            or "current_only"
        ).strip().lower()
        if self.retention_mode not in {"current_only", "history"}:
            raise GenerationTransactionError(
                f"unsupported DCF retention mode: {self.retention_mode}"
            )

    @contextmanager
    def single_flight(self, timeout: float = 30.0) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.lock_path), timeout=timeout)
        try:
            with lock:
                yield
        except Timeout as exc:
            raise GenerationTransactionError("another DCF refresh owns the single-flight lock") from exc

    def read_pointer(self, *, last_good: bool = False) -> GenerationPointer | None:
        path = self.last_good_path if last_good else self.current_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return GenerationPointer.model_validate(payload)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return None

    def generation_dir(self, generation_id: str) -> Path:
        if not generation_id or generation_id != Path(generation_id).name:
            raise GenerationUnavailable("invalid generation id")
        return self.generations / generation_id

    def graph_paths(
        self,
        generation_dir: Path,
        *,
        verify_file_hashes: bool = True,
    ) -> tuple[Path, Path | None]:
        overlay_path = generation_dir / "index.sqlite"
        reference_path = generation_dir / "graph_ref.json"
        if not reference_path.is_file():
            return overlay_path, None
        try:
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            relative = Path(str(reference["base_index_relative"]))
            base_path = (self.root / relative).resolve()
            base_path.relative_to(self.root)
            expected_size = int(reference["base_index_size_bytes"])
            expected_sha = str(reference["base_index_sha256"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
            raise GenerationUnavailable(f"graph reference is invalid: {exc}") from exc
        invalid = not base_path.is_file() or base_path.stat().st_size != expected_size
        if verify_file_hashes and not invalid:
            invalid = sha256_file(base_path) != expected_sha
        if invalid:
            raise GenerationUnavailable("referenced static graph verification failed")
        return overlay_path, base_path

    def load_generation(
        self,
        generation_id: str,
        *,
        verify_file_hashes: bool = True,
    ) -> tuple[DcfSnapshot, GenerationManifest, Path]:
        generation_dir = self.generation_dir(generation_id)
        try:
            manifest_payload = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
            context_payload = json.loads((generation_dir / "context.json").read_text(encoding="utf-8"))
            manifest = GenerationManifest.model_validate(manifest_payload)
            snapshot = DcfSnapshot.model_validate(context_payload)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            raise GenerationUnavailable(f"generation {generation_id} is unreadable: {exc}") from exc
        if manifest.generation_id != generation_id or snapshot.generation_id != generation_id:
            raise GenerationUnavailable(f"generation identity mismatch for {generation_id}")
        for relative, metadata in manifest.files.items():
            path = generation_dir / relative
            invalid = not path.is_file() or path.stat().st_size != metadata.size_bytes
            if verify_file_hashes and not invalid:
                invalid = sha256_file(path) != metadata.sha256
            if invalid:
                raise GenerationUnavailable(f"generation file verification failed: {relative}")
        self.graph_paths(generation_dir, verify_file_hashes=verify_file_hashes)
        return snapshot, manifest, generation_dir

    def load_current(
        self,
        *,
        allow_last_good: bool = True,
        verify_file_hashes: bool = True,
    ) -> tuple[DcfSnapshot, GenerationManifest, Path]:
        pointer = self.read_pointer()
        if pointer is not None:
            try:
                manifest_path = self.generation_dir(pointer.generation_id) / "manifest.json"
                if not manifest_path.is_file() or sha256_file(manifest_path) != pointer.manifest_sha256:
                    raise GenerationUnavailable("current pointer manifest digest mismatch")
                return self.load_generation(
                    pointer.generation_id,
                    verify_file_hashes=verify_file_hashes,
                )
            except GenerationUnavailable:
                if not allow_last_good:
                    raise
        if allow_last_good:
            pointer = self.read_pointer(last_good=True)
            if pointer is not None:
                manifest_path = self.generation_dir(pointer.generation_id) / "manifest.json"
                if not manifest_path.is_file() or sha256_file(manifest_path) != pointer.manifest_sha256:
                    raise GenerationUnavailable("last-good pointer manifest digest mismatch")
                return self.load_generation(
                    pointer.generation_id,
                    verify_file_hashes=verify_file_hashes,
                )
        raise GenerationUnavailable("no verified DCF v2 generation is available")

    def publish_staging(
        self,
        *,
        stage_dir: Path,
        snapshot: DcfSnapshot,
        metrics: dict[str, Any],
    ) -> GenerationManifest:
        context_path = stage_dir / "context.json"
        index_path = stage_dir / "index.sqlite"
        if not context_path.is_file() or not index_path.is_file():
            raise GenerationTransactionError("staging generation is incomplete")
        file_names = ["context.json", "index.sqlite"]
        if (stage_dir / "graph_ref.json").is_file():
            file_names.append("graph_ref.json")
        files = {
            name: GenerationFile(sha256=sha256_file(stage_dir / name), size_bytes=(stage_dir / name).stat().st_size)
            for name in file_names
        }
        manifest = GenerationManifest(
            generation_id=snapshot.generation_id,
            generated_at=snapshot.generated_at,
            repo_head=str(snapshot.repo.get("head_commit", "")),
            worktree_fingerprint=str(snapshot.repo.get("worktree_fingerprint", "")),
            input_fingerprint=snapshot.input_fingerprint,
            files=files,
            metrics=metrics,
        )
        atomic_write_json(stage_dir / "manifest.json", manifest.model_dump(mode="json"))
        # Validate the complete staging directory before exposing it.
        GenerationManifest.model_validate_json((stage_dir / "manifest.json").read_text(encoding="utf-8"))
        DcfSnapshot.model_validate_json(context_path.read_text(encoding="utf-8"))

        self.generations.mkdir(parents=True, exist_ok=True)
        final_dir = self.generation_dir(snapshot.generation_id)
        if final_dir.exists():
            raise GenerationTransactionError(f"immutable generation already exists: {snapshot.generation_id}")
        os.rename(stage_dir, final_dir)

        manifest_sha = sha256_file(final_dir / "manifest.json")
        published_at = utc_now()
        pointer = GenerationPointer(
            generation_id=snapshot.generation_id,
            generation_path=path_reference(final_dir, repo_root=self.repo_root),
            published_at=published_at,
            reconciled_at=published_at,
            manifest_sha256=manifest_sha,
        )
        # last_good first: a crash between pointer writes still leaves one verified pointer.
        atomic_write_json(self.last_good_path, pointer.model_dump(mode="json"))
        atomic_write_json(self.current_path, pointer.model_dump(mode="json"))
        return manifest

    def reconcile_current(self, generation_id: str) -> str:
        pointer = self.read_pointer()
        if pointer is None or pointer.generation_id != generation_id:
            raise GenerationTransactionError("cannot reconcile a non-current generation")
        reconciled_at = utc_now()
        reconciled = pointer.model_copy(update={"reconciled_at": reconciled_at})
        atomic_write_json(self.last_good_path, reconciled.model_dump(mode="json"))
        atomic_write_json(self.current_path, reconciled.model_dump(mode="json"))
        return reconciled_at

    def enforce_current_only(self) -> list[str]:
        """Remove every non-current, non-referenced generation after full verification."""
        current = self.read_pointer()
        last_good = self.read_pointer(last_good=True)
        if current is None or last_good is None:
            raise GenerationTransactionError("current-only retention requires both pointers")
        if current.generation_id != last_good.generation_id:
            raise GenerationTransactionError("current-only retention requires converged pointers")

        _, _, current_dir = self.load_generation(current.generation_id)
        if (current_dir / "graph_ref.json").exists():
            raise GenerationTransactionError(
                "current-only retention requires a self-contained generation"
            )

        removed: list[str] = []
        if not self.generations.is_dir():
            return removed
        for path in sorted(self.generations.iterdir()):
            if not path.is_dir() or path.name == current.generation_id:
                continue
            shutil.rmtree(path)
            removed.append(path.name)
        return removed

    @contextmanager
    def new_stage(self) -> Iterator[Path]:
        self.staging.mkdir(parents=True, exist_ok=True)
        stage = self.staging / str(uuid.uuid4())
        stage.mkdir()
        try:
            yield stage
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def write_failure(self, *, reason: str, error: BaseException, generation_id: str | None = None) -> Path:
        payload = {
            "schema_version": "dcf_generation_failure_receipt_v2",
            "generated_at": utc_now(),
            "generation_id": generation_id,
            "reason": reason,
            "error_type": type(error).__name__,
            "error": str(error),
            "authority_effect": "none",
            "no_apply": True,
        }
        path = self.failures / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}.json"
        atomic_write_json(path, payload)
        return path

    def prune_generations(self, *, keep_successful: int = 10, min_age_days: int = 14) -> list[str]:
        if not self.generations.exists():
            return []
        protected = {
            pointer.generation_id
            for pointer in (self.read_pointer(), self.read_pointer(last_good=True))
            if pointer is not None
        }
        rows = sorted(
            (path for path in self.generations.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        protected.update(path.name for path in rows[:keep_successful])
        for path in rows:
            reference_path = path / "graph_ref.json"
            try:
                reference = json.loads(reference_path.read_text(encoding="utf-8"))
                base_generation_id = str(reference.get("base_generation_id") or "")
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            if base_generation_id:
                protected.add(base_generation_id)
        cutoff = datetime.now(UTC).timestamp() - (min_age_days * 86400)
        removed: list[str] = []
        for path in rows:
            if path.name in protected or path.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(path)
            removed.append(path.name)
        return removed

    def prune_retired_v1(self, *, keep_successful: int = 10, min_age_days: int = 14) -> list[str]:
        generation_count = sum(1 for path in self.generations.iterdir() if path.is_dir()) if self.generations.is_dir() else 0
        if generation_count < keep_successful:
            return []
        retired_root = self.repo_root / "output/dcf_runtime/_retired/v1"
        if not retired_root.is_dir():
            return []
        cutoff = datetime.now(UTC).timestamp() - (min_age_days * 86400)
        removed: list[str] = []
        for batch in sorted(retired_root.iterdir()):
            if not batch.is_dir() or batch.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(batch)
            removed.append(str(batch.relative_to(self.repo_root)))
        return removed
