"""Tests for TaskQueue V4.0 features — cancel, retry, usage."""

from __future__ import annotations

from hauba.daemon.queue import TaskQueue


class TestCancel:
    """Test TaskQueue.cancel()."""

    def test_cancel_queued_task(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build something")
        assert q.cancel(task.task_id) is True
        assert q.get(task.task_id).status == "cancelled"  # type: ignore[union-attr]

    def test_cancel_nonexistent(self) -> None:
        q = TaskQueue()
        assert q.cancel("nonexistent-id") is False

    def test_cancel_already_completed(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build something")
        task.status = "completed"
        assert q.cancel(task.task_id) is False

    def test_cancel_already_cancelled(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build something")
        task.status = "cancelled"
        assert q.cancel(task.task_id) is False


class TestRetry:
    """Test TaskQueue.retry()."""

    def test_retry_failed_task(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build dashboard")
        task.status = "failed"

        new_task = q.retry(task.task_id)
        assert new_task is not None
        assert new_task.task_id != task.task_id
        assert new_task.instruction == task.instruction
        assert new_task.status == "queued"
        assert new_task.owner_id == task.owner_id

    def test_retry_cancelled_task(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build api")
        task.status = "cancelled"

        new_task = q.retry(task.task_id)
        assert new_task is not None
        assert new_task.instruction == "build api"

    def test_retry_nonexistent(self) -> None:
        q = TaskQueue()
        assert q.retry("nonexistent") is None

    def test_retry_running_task_fails(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "running task")
        task.status = "running"
        assert q.retry(task.task_id) is None

    def test_retry_preserves_channel_info(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build app", channel="whatsapp", channel_address="whatsapp:+1234")
        task.status = "failed"

        new_task = q.retry(task.task_id)
        assert new_task is not None
        assert new_task.channel == "whatsapp"
        assert new_task.channel_address == "whatsapp:+1234"


class TestGetUsage:
    """Test TaskQueue.get_usage()."""

    def test_empty_usage(self) -> None:
        q = TaskQueue()
        usage = q.get_usage("owner1")
        assert usage["total_tasks"] == 0
        assert usage["completed"] == 0

    def test_usage_with_mixed_tasks(self) -> None:
        q = TaskQueue()
        t1 = q.submit("owner1", "task 1")
        t2 = q.submit("owner1", "task 2")
        q.submit("owner1", "task 3")

        t1.status = "completed"
        t2.status = "failed"
        # t3 stays queued

        usage = q.get_usage("owner1")
        assert usage["total_tasks"] == 3
        assert usage["completed"] == 1
        assert usage["failed"] == 1
        assert usage["queued"] == 1

    def test_usage_per_owner(self) -> None:
        q = TaskQueue()
        q.submit("owner1", "task a")
        q.submit("owner2", "task b")

        usage1 = q.get_usage("owner1")
        usage2 = q.get_usage("owner2")
        assert usage1["total_tasks"] == 1
        assert usage2["total_tasks"] == 1
