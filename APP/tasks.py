"""
tasks.py  –  Celery task definitions for Research Assistant.

Each task is a thin wrapper around the existing synchronous research()
function so the heavy work runs inside a worker process, not inside the
FastAPI event loop.

Task states follow the standard Celery lifecycle:
  PENDING  → task submitted but not yet picked up by a worker
  STARTED  → worker has begun processing (requires task_track_started=True)
  SUCCESS  → research() returned successfully
  FAILURE  → research() raised an exception

Custom META dict is stored via self.update_state() so callers can read
progress details (current stage label) while the task is running.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Optional

from celery import Task
from celery.utils.log import get_task_logger

from celery_app import celery_app
from research import research

logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Progress stage labels — kept in sync with the SSE stages in app.py
# ---------------------------------------------------------------------------
_STAGES = [
    "Planning Research...",
    "Searching Sources...",
    "Extracting Content...",
    "Generating Report...",
    "Creating PDF...",
]


@celery_app.task(
    bind=True,
    name="research_task",
    track_started=True,
    max_retries=0,              # research failures should surface immediately
)
def run_research_task(
    self: Task,
    query: str,
    websites: Optional[List[str]] = None,
) -> dict:
    """
    Run the full research workflow inside a Celery worker.

    Args:
        query:    The research question / topic.
        websites: Optional list of seed websites.

    Returns:
        The dict returned by research() — json_path, pdf_path, summary, sources.

    Raises:
        Exception: Any exception from the workflow is re-raised so Celery
                   marks the task FAILURE and stores the traceback.
    """
    logger.info("Task %s started — query: %.80s", self.request.id, query)

    # Emit "planning" progress immediately
    self.update_state(
        state="PROGRESS",
        meta={"stage": "planning", "message": _STAGES[0], "progress": 0},
    )

    try:
        result = research(query, websites)
    except Exception as exc:
        logger.error("Task %s failed: %s", self.request.id, exc)
        # Re-raise so Celery records FAILURE + traceback
        raise

    logger.info("Task %s completed successfully", self.request.id)
    return result
