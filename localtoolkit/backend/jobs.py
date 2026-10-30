"""
In-memory job store for long-running background conversions.
Frontend polls GET /api/jobs/{job_id} for progress updates.
"""
from __future__ import annotations
import uuid, time, threading
from enum import Enum
from typing import Any
from dataclasses import dataclass, field

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    ERROR     = "error"

@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0          # 0-100
    message: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)

_store: dict[str, Job] = {}
_lock = threading.Lock()

def create_job() -> Job:
    job = Job(id=uuid.uuid4().hex)
    with _lock:
        _store[job.id] = job
    return job

def get_job(job_id: str) -> Job | None:
    with _lock:
        return _store.get(job_id)

def update_job(job_id: str, **kwargs: Any) -> None:
    with _lock:
        job = _store.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)

def purge_old_jobs(ttl: float = 3600) -> None:
    now = time.time()
    with _lock:
        old = [jid for jid, j in _store.items() if now - j.created_at > ttl]
        for jid in old:
            del _store[jid]

