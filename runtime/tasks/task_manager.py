"""Task lifecycle manager — single public interface to the task system."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from loguru import logger

from runtime.event_bus import EventBus
from runtime.tasks.task_events import (
    TaskCancelled,
    TaskCompleted,
    TaskCreated,
    TaskFailed,
    TaskPaused,
    TaskResumed,
    TaskStarted,
    TaskUpdated,
)
from runtime.tasks.task_models import Task, TaskPriority, TaskStatus, TaskStep
from runtime.tasks.task_store import TaskStore


class TaskManager:
    """
    Owns TaskStore and publishes TaskEvents through the EventBus.

    All task lifecycle operations go through this class.
    Each method:
      1. Loads/validates the task exists
      2. Updates status + updated_at
      3. Persists via TaskStore
      4. Publishes the correct TaskEvent
      5. Logs the state transition
      6. Returns the updated Task
    """

    def __init__(self, event_bus: EventBus, store: TaskStore = None):
        self._event_bus = event_bus
        self._store = store or TaskStore()
        self._running = False
        logger.debug("TaskManager initialized")

    def start(self):
        """Load existing tasks from store on startup."""
        self._running = True
        count = len(self._store.list_tasks())
        logger.info("TaskManager started | existing tasks={}", count)

    def stop(self):
        """Close TaskStore cleanly on shutdown."""
        self._running = False
        self._store.close()
        logger.info("TaskManager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── CRUD ──────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        steps: list[dict] = None,
    ) -> Task:
        """Create a new task and publish task.created event."""
        now = datetime.now()
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            steps=[
                TaskStep(
                    id=str(uuid.uuid4()),
                    title=s.get("title", str(s)),
                    status=TaskStatus.PENDING,
                    created_at=now,
                    updated_at=now,
                )
                for s in (steps or [])
            ],
        )
        self._store.create_task(task)
        self._publish(TaskCreated, {"task": task.to_dict()})
        logger.info("Task created | id={} | title={}", task.id, task.title)
        return task

    def update_task(self, task: Task) -> Task:
        """Update an existing task and publish task.updated event."""
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskUpdated, {"task": task.to_dict()})
        logger.info("Task updated | id={} | title={}", task.id, task.title)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        return self._store.get_task(task_id)

    def list_tasks(self, status: TaskStatus = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        return self._store.list_tasks(status=status)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task. Returns True if deleted."""
        deleted = self._store.delete_task(task_id)
        if deleted:
            logger.info("Task deleted | id={}", task_id)
        return deleted

    # ── Lifecycle transitions ─────────────────────────────

    def start_task(self, task_id: str) -> Optional[Task]:
        """Transition a task from PENDING to RUNNING."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for start: {}", task_id)
            return None
        if task.status != TaskStatus.PENDING:
            logger.warning("Cannot start task {} — status is {}", task_id, task.status.value)
            return None
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskStarted, {"task": task.to_dict()})
        logger.info("Task started | id={} | title={}", task.id, task.title)
        return task

    def pause_task(self, task_id: str) -> Optional[Task]:
        """Transition a task from RUNNING to PAUSED."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for pause: {}", task_id)
            return None
        if task.status != TaskStatus.RUNNING:
            logger.warning("Cannot pause task {} — status is {}", task_id, task.status.value)
            return None
        task.status = TaskStatus.PAUSED
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskPaused, {"task": task.to_dict()})
        logger.info("Task paused | id={} | title={}", task.id, task.title)
        return task

    def resume_task(self, task_id: str) -> Optional[Task]:
        """Transition a task from PAUSED back to RUNNING."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for resume: {}", task_id)
            return None
        if task.status != TaskStatus.PAUSED:
            logger.warning("Cannot resume task {} — status is {}", task_id, task.status.value)
            return None
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskResumed, {"task": task.to_dict()})
        logger.info("Task resumed | id={} | title={}", task.id, task.title)
        return task

    def complete_task(self, task_id: str) -> Optional[Task]:
        """Transition a task from RUNNING to COMPLETED."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for complete: {}", task_id)
            return None
        if task.status not in (TaskStatus.RUNNING, TaskStatus.PAUSED):
            logger.warning(
                "Cannot complete task {} — status is {}", task_id, task.status.value
            )
            return None
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskCompleted, {"task": task.to_dict()})
        logger.info("Task completed | id={} | title={}", task.id, task.title)
        return task

    def fail_task(self, task_id: str, error: str = "") -> Optional[Task]:
        """Transition a task from RUNNING to FAILED."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for fail: {}", task_id)
            return None
        if task.status not in (TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.PAUSED):
            logger.warning(
                "Cannot fail task {} — status is {}", task_id, task.status.value
            )
            return None
        task.status = TaskStatus.FAILED
        task.updated_at = datetime.now()
        if error:
            task.metadata["error"] = error
        self._store.update_task(task)
        self._publish(TaskFailed, {"task": task.to_dict(), "error": error})
        logger.info("Task failed | id={} | title={} | error={}", task.id, task.title, error)
        return task

    def cancel_task(self, task_id: str) -> Optional[Task]:
        """Transition a task from any non-terminal status to CANCELLED."""
        task = self._store.get_task(task_id)
        if task is None:
            logger.warning("Task not found for cancel: {}", task_id)
            return None
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            logger.warning(
                "Cannot cancel task {} — already {}", task_id, task.status.value
            )
            return None
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now()
        self._store.update_task(task)
        self._publish(TaskCancelled, {"task": task.to_dict()})
        logger.info("Task cancelled | id={} | title={}", task.id, task.title)
        return task

    # ── Internal ──────────────────────────────────────────

    def _publish(self, event_class, payload: dict):
        """Publish a task event through the EventBus."""
        try:
            event = event_class(source="task_manager", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)


__all__ = ["TaskManager"]