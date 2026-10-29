"""Run trace: one JSON line per step in code/traces/<trace_id>.jsonl."""
import json
import time
import uuid
from datetime import datetime, timezone

from .config import TRACES_DIR


class Trace:
    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or "tr-" + uuid.uuid4().hex[:12]
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        self.path = TRACES_DIR / f"{self.trace_id}.jsonl"

    def log(self, step: str, **data) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "step": step, **data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def timed(self, step: str):
        return _Timer(self, step)


class _Timer:
    def __init__(self, trace: Trace, step: str):
        self.trace, self.step = trace, step

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        ms = round(1000 * (time.perf_counter() - self.start), 1)
        if exc:
            self.trace.log(self.step, ok=False, ms=ms, error=f"{exc_type.__name__}: {exc}")
        else:
            self.trace.log(self.step, ok=True, ms=ms)
        return False
