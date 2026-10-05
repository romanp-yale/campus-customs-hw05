"""Locked, atomic JSON-array append; never replace earlier audit entries."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time

from .models import AuditEntry, Role


@contextmanager
def file_lock(path: Path):
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class AuditTrail:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, run_id: str, event: str, role: Role | None = None, **data):
        with file_lock(self.path.with_suffix(".lock")):
            existing = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            if not isinstance(existing, list):
                raise ValueError("Audit trail must be a JSON array; refusing to overwrite it.")
            entry = AuditEntry(sequence=len(existing)+1, recorded_at_utc=datetime.now(timezone.utc).isoformat(), run_id=run_id, event=event, role=role, data=data)
            existing.append(entry.model_dump(mode="json"))
            # Corrupt history fails above. Atomic replacement keeps all old entries.
            fd, temporary = tempfile.mkstemp(prefix="audit-", suffix=".json", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(existing, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                # Windows readers/virus scanning may briefly deny replacement.
                for attempt in range(30):
                    try:
                        os.replace(temporary, self.path)
                        break
                    except PermissionError:
                        if attempt == 29:
                            raise
                        time.sleep(0.05)

            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
