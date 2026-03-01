"""Tests for the task queue (Queue + Poll architecture)."""

from __future__ import annotations

import pytest

from hauba.daemon.queue import MAX_QUEUED_PER_OWNER, QueuedTask, TaskQueue


class TestQueuedTask:
    """Tests for the QueuedTask dataclass."""

    def test_default_values(self) -> None:
        task = QueuedTask(task_id="t1", owner_id="o1", instruction="build an app")
        assert task.task_id == "t1"
        assert task.owner_id == "o1"
        assert task.instruction == "build an app"
        assert task.status == "queued"
        assert task.channel == ""
        assert task.channel_address == ""
        assert task.output == ""
        assert task.error == ""
        assert task.metadata == {}

    def test_with_channel_info(self) -> None:
        task = QueuedTask(
            task_id="t2",
            owner_id="o2",
            instruction="deploy",
            channel="whatsapp",
            channel_address="whatsapp:+1234",
        )
        assert task.channel == "whatsapp"
        assert task.channel_address == "whatsapp:+1234"


class TestTaskQueue:
    """Tests for the TaskQueue."""

    def test_submit_creates_task(self) -> None:
        q = TaskQueue()
        task = q.submit("owner1", "build a REST API")
        assert task.task_id
        assert task.owner_id == "owner1"
        assert task.instruction == "build a REST API"
        assert task.status == "queued"
        assert task.created_at > 0

    def test_submit_with_channel(self) -> None:
        q = TaskQueue()
        task = q.submit(
            "owner1",
            "build app",
            channel="whatsapp",
            channel_address="whatsapp:+1234",
        )
        assert task.channel == "whatsapp"
        assert task.channel_address == "whatsapp:+1234"

    def test_submit_increments_size(self) -> None:
        q = TaskQueue()
        assert q.size == 0
        q.submit("o1", "task 1")
        assert q.size == 1
        q.submit("o1", "task 2")
        assert q.size == 2

    def test_submit_max_queue_limit(self) -> None:
        q = TaskQueue()
        for i in range(MAX_QUEUED_PER_OWNER):
            q.submit("o1", f"task {i}")

        with pytest.raises(ValueError, match="Too many queued tasks"):
            q.submit("o1", "one too many")

    def test_submit_limit_per_owner(self) -> None:
        """Different owners have independent limits."""
        q = TaskQueue()
        for i in range(MAX_QUEUED_PER_OWNER):
            q.submit("o1", f"task {i}")

        # Different owner can still submit
        task = q.submit("o2", "another owner's task")
        assert task.owner_id == "o2"

    def test_poll_returns_queued_tasks(self) -> None:
        q = TaskQueue()
        q.submit("o1", "task 1")
        q.submit("o1", "task 2")
        q.submit("o2", "other owner task")

        tasks = q.poll("o1")
        assert len(tasks) == 2
        assert tasks[0].instruction == "task 1"
        assert tasks[1].instruction == "task 2"

    def test_poll_returns_empty_for_unknown_owner(self) -> None:
        q = TaskQueue()
        q.submit("o1", "task 1")
        assert q.poll("unknown") == []

    def test_poll_respects_limit(self) -> None:
        q = TaskQueue()
        for i in range(5):
            q.submit("o1", f"task {i}")

        tasks = q.poll("o1", limit=2)
        assert len(tasks) == 2

    def test_poll_excludes_claimed_tasks(self) -> None:
        q = TaskQueue()
        t1 = q.submit("o1", "task 1")
        q.submit("o1", "task 2")

        q.claim(t1.task_id)
        tasks = q.poll("o1")
        assert len(tasks) == 1
        assert tasks[0].instruction == "task 2"

    def test_claim_task(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        claimed = q.claim(t.task_id)
        assert claimed is not None
        assert claimed.status == "claimed"
        assert claimed.claimed_at is not None

    def test_claim_nonexistent_returns_none(self) -> None:
        q = TaskQueue()
        assert q.claim("nonexistent") is None

    def test_claim_already_claimed_returns_none(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        q.claim(t.task_id)
        assert q.claim(t.task_id) is None

    def test_update_progress(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        q.claim(t.task_id)

        assert q.update_progress(t.task_id, "50% done")
        task = q.get(t.task_id)
        assert task is not None
        assert task.progress == "50% done"
        assert task.status == "running"

    def test_update_progress_queued_fails(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        assert not q.update_progress(t.task_id, "progress")

    @pytest.mark.asyncio
    async def test_complete_task_success(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        q.claim(t.task_id)

        result = await q.complete(t.task_id, "Done!", success=True)
        assert result is True

        task = q.get(t.task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.output == "Done!"
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_task_failure(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        q.claim(t.task_id)

        result = await q.complete(t.task_id, "", success=False, error="timeout")
        assert result is True

        task = q.get(t.task_id)
        assert task is not None
        assert task.status == "failed"
        assert task.error == "timeout"

    @pytest.mark.asyncio
    async def test_complete_nonexistent_returns_false(self) -> None:
        q = TaskQueue()
        assert await q.complete("nonexistent", "out") is False

    @pytest.mark.asyncio
    async def test_completion_callback_fires(self) -> None:
        q = TaskQueue()
        completed_tasks: list[QueuedTask] = []

        async def on_complete(task: QueuedTask) -> None:
            completed_tasks.append(task)

        q.on_completion(on_complete)

        t = q.submit("o1", "task")
        q.claim(t.task_id)
        await q.complete(t.task_id, "Done!")

        assert len(completed_tasks) == 1
        assert completed_tasks[0].task_id == t.task_id
        assert completed_tasks[0].output == "Done!"

    @pytest.mark.asyncio
    async def test_completion_callback_error_does_not_crash(self) -> None:
        q = TaskQueue()

        async def bad_callback(task: QueuedTask) -> None:
            raise RuntimeError("callback failed")

        q.on_completion(bad_callback)

        t = q.submit("o1", "task")
        q.claim(t.task_id)
        # Should not raise
        await q.complete(t.task_id, "Done!")

    def test_get_task(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "task")
        got = q.get(t.task_id)
        assert got is not None
        assert got.task_id == t.task_id

    def test_get_nonexistent(self) -> None:
        q = TaskQueue()
        assert q.get("nonexistent") is None

    def test_get_owner_tasks(self) -> None:
        q = TaskQueue()
        q.submit("o1", "task 1")
        q.submit("o1", "task 2")
        q.submit("o2", "other")

        tasks = q.get_owner_tasks("o1")
        assert len(tasks) == 2

    def test_clear_owner(self) -> None:
        q = TaskQueue()
        q.submit("o1", "task 1")
        q.submit("o1", "task 2")
        q.submit("o2", "other")

        removed = q.clear_owner("o1")
        assert removed == 2
        assert q.size == 1
        assert q.get_owner_tasks("o1") == []

    def test_expire_stale_tasks(self) -> None:
        q = TaskQueue()
        t = q.submit("o1", "old task")
        # Manually set created_at to be very old
        q._tasks[t.task_id].created_at = 0.0

        # Poll triggers expiration
        tasks = q.poll("o1")
        assert len(tasks) == 0

        task = q.get(t.task_id)
        assert task is not None
        assert task.status == "expired"
