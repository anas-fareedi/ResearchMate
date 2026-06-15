"""
celery_app.py  –  Celery application factory for Research Assistant.

The broker and result backend both point at Redis.  The URL is read from
the REDIS_URL environment variable (set in .env or docker-compose.yml).
Default: redis://localhost:6379/0
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery import Celery

# ---------------------------------------------------------------------------
# Redis URL — configurable via env so local dev and Docker both work
# ---------------------------------------------------------------------------
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def make_celery() -> Celery:
    """Create and configure the Celery application."""
    app = Celery(
        "research_assistant",
        broker=_REDIS_URL,
        backend=_REDIS_URL,
        include=["tasks"],          # auto-discover tasks module in the same dir
    )

    app.conf.update(
        # Serialisation
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Result TTL: keep results for 24 h so clients can fetch them later
        result_expires=86400,

        # Worker behaviour
        worker_prefetch_multiplier=1,       # one task at a time per worker slot
        task_acks_late=True,                # ack only after task completes
        task_reject_on_worker_lost=True,    # re-queue if worker crashes mid-task

        # Route all tasks to the default queue
        task_default_queue="research",

        # Task time limits (seconds)
        task_soft_time_limit=300,           # raises SoftTimeLimitExceeded → graceful
        task_time_limit=360,                # hard kill after 6 min
    )

    return app


celery_app = make_celery()

# Celery CLI discovers the app by looking for an attribute named 'app' or 'celery'
# in the module passed to -A.  Export both so `celery -A celery_app` works.
app = celery_app
