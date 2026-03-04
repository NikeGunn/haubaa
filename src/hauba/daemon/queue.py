"""Task queue — in-memory queue for the Queue + Poll architecture.

Server-side component. Tasks are submitted by channels (WhatsApp, Telegram,
Discord) and polled by the user's local `hauba agent` daemon.

Flow:
    Channel → submit_task() → queue
    Local agent → poll_tasks(owner_id) → claim_task() → execute locally
    Local agent → report_progress() / complete_task()
    Server → notify channel (WhatsApp reply, etc.)

Design:
    - In-memory dict (Railway is single-instance, single-process)
    - owner_id groups tasks by WhatsApp number or user identity
    - Tasks expire after TASK_TTL seconds if unclaimed
    - Completion triggers a callback for channel notification
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# Tasks expire if unclaimed after 1 hour
TASK_TTL = 3600.0

# Maximum queued tasks per owner to prevent abuse
MAX_QUEUED_PER_OWNER = 10


@dataclass
class QueuedTask:
    """A task waiting in the queue for a local agent to pick up."""

    task_id: str
    owner_id: str
    instruction: str
    status: str = "queued"  # queued, claimed, running, completed, failed, expired
    created_at: float = 0.0
    claimed_at: float | None = None
    completed_at: float | None = None
    progress: str = ""
    output: str = ""
    error: str = ""
    # Channel info for sending results back
    channel: str = ""  # "whatsapp", "telegram", "discord"
    channel_address: str = ""  # phone number, chat_id, channel_id
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """In-memory task queue for the Queue + Poll architecture.

    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._tasks: dict[str, QueuedTask] = {}
        self._completion_callbacks: list[Any] = []

    def on_completion(self, callback: Any) -> None:
        """Register a callback for when tasks complete.

        Callback signature: async def callback(task: QueuedTask) -> None
        """
        self._completion_callbacks.append(callback)

    def submit(
        self,
        owner_id: str,
        instruction: str,
        channel: str = "",
        channel_address: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> QueuedTask:
        """Submit a new task to the queue.

        Args:
            owner_id: The user identity (WhatsApp number, user ID, etc.)
            instruction: What to build (plain English)
            channel: Which channel submitted this ("whatsapp", "telegram", etc.)
            channel_address: Where to send the result back
            metadata: Optional metadata

        Returns:
            The created QueuedTask.

        Raises:
            ValueError: If the owner has too many queued tasks.
        """
        # Check queue limit per owner
        owner_count = sum(
            1
            for t in self._tasks.values()
            if t.owner_id == owner_id and t.status in ("queued", "claimed", "running")
        )
        if owner_count >= MAX_QUEUED_PER_OWNER:
            raise ValueError(
                f"Too many queued tasks ({owner_count}). "
                "Wait for current tasks to complete or send /clear."
            )

        task = QueuedTask(
            task_id=str(uuid.uuid4()),
            owner_id=owner_id,
            instruction=instruction,
            status="queued",
            created_at=time.time(),
            channel=channel,
            channel_address=channel_address,
            metadata=metadata or {},
        )
        self._tasks[task.task_id] = task

        logger.info(
            "queue.task_submitted",
            task_id=task.task_id,
            owner_id=owner_id,
            channel=channel,
        )
        return task

    def poll(self, owner_id: str, limit: int = 5) -> list[QueuedTask]:
        """Get queued (unclaimed) tasks for an owner.

        Args:
            owner_id: The owner to poll tasks for.
            limit: Maximum number of tasks to return.

        Returns:
            List of queued tasks, oldest first.
        """
        self._expire_stale_tasks()
        tasks = [t for t in self._tasks.values() if t.owner_id == owner_id and t.status == "queued"]
        tasks.sort(key=lambda t: t.created_at)
        return tasks[:limit]

    def claim(self, task_id: str) -> QueuedTask | None:
        """Claim a task for execution.

        Args:
            task_id: The task to claim.

        Returns:
            The claimed task, or None if not found/already claimed.
        """
        task = self._tasks.get(task_id)
        if not task or task.status != "queued":
            return None

        task.status = "claimed"
        task.claimed_at = time.time()

        logger.info("queue.task_claimed", task_id=task_id)
        return task

    def update_progress(self, task_id: str, progress: str) -> bool:
        """Update the progress message for a running task.

        Args:
            task_id: The task to update.
            progress: Progress message.

        Returns:
            True if updated, False if task not found.
        """
        task = self._tasks.get(task_id)
        if not task or task.status not in ("claimed", "running"):
            return False

        task.status = "running"
        task.progress = progress
        return True

    async def complete(
        self,
        task_id: str,
        output: str,
        success: bool = True,
        error: str = "",
    ) -> bool:
        """Mark a task as completed and trigger notification callbacks.

        Args:
            task_id: The task to complete.
            output: The task output/result.
            success: Whether the task succeeded.
            error: Error message if failed.

        Returns:
            True if completed, False if task not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = "completed" if success else "failed"
        task.completed_at = time.time()
        task.output = output
        task.error = error

        logger.info(
            "queue.task_completed",
            task_id=task_id,
            success=success,
        )

        # Fire completion callbacks (e.g., notify WhatsApp)
        for callback in self._completion_callbacks:
            try:
                await callback(task)
            except Exception as exc:
                logger.error(
                    "queue.callback_error",
                    task_id=task_id,
                    error=str(exc),
                )

        return True

    def get(self, task_id: str) -> QueuedTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_owner_tasks(self, owner_id: str) -> list[QueuedTask]:
        """Get all tasks for an owner (any status)."""
        return [t for t in self._tasks.values() if t.owner_id == owner_id]

    def clear_owner(self, owner_id: str) -> int:
        """Clear all tasks for an owner. Returns count removed."""
        to_remove = [tid for tid, t in self._tasks.items() if t.owner_id == owner_id]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)

    @property
    def size(self) -> int:
        """Total number of tasks in the queue."""
        return len(self._tasks)

    def cancel(self, task_id: str) -> bool:
        """Cancel a queued or running task.

        Returns True if cancelled, False if task not found or already terminal.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in ("completed", "failed", "expired", "cancelled"):
            return False

        task.status = "cancelled"
        task.completed_at = time.time()
        logger.info("queue.task_cancelled", task_id=task_id)
        return True

    def retry(self, task_id: str) -> QueuedTask | None:
        """Retry a failed/cancelled task by creating a new copy.

        Returns the new task, or None if original not found or not retryable.
        """
        original = self._tasks.get(task_id)
        if not original:
            return None
        if original.status not in ("failed", "cancelled", "expired"):
            return None

        return self.submit(
            owner_id=original.owner_id,
            instruction=original.instruction,
            channel=original.channel,
            channel_address=original.channel_address,
            metadata=original.metadata,
        )

    def get_usage(self, owner_id: str) -> dict[str, Any]:
        """Get usage statistics for an owner.

        Returns a summary dict with task counts and estimated cost.
        """
        tasks = self.get_owner_tasks(owner_id)
        return {
            "total_tasks": len(tasks),
            "completed": sum(1 for t in tasks if t.status == "completed"),
            "failed": sum(1 for t in tasks if t.status == "failed"),
            "running": sum(1 for t in tasks if t.status in ("claimed", "running")),
            "queued": sum(1 for t in tasks if t.status == "queued"),
            "cancelled": sum(1 for t in tasks if t.status == "cancelled"),
            "estimated_cost": 0.0,  # Placeholder — daemon tracks actual cost
        }

    def _expire_stale_tasks(self) -> None:
        """Mark old unclaimed tasks as expired."""
        now = time.time()
        for task in self._tasks.values():
            if task.status == "queued" and (now - task.created_at) > TASK_TTL:
                task.status = "expired"
                logger.debug("queue.task_expired", task_id=task.task_id)
