# Skill: Agent Architecture Patterns

## Agent Base Class
Every agent inherits from `BaseAgent` and implements these methods:

```python
class BaseAgent(ABC):
    agent_id: str
    state: AgentState  # DORMANT→BOOTING→DELIBERATING→EXECUTING→WAITING→REVIEWING→COMPLETED→ARCHIVED
    parent_id: str | None
    ledger: TaskLedger | None
    event_emitter: EventEmitter

    @abstractmethod
    async def deliberate(self, task: Task, context: Context) -> Plan: ...

    @abstractmethod
    async def execute(self, plan: Plan) -> Result: ...

    @abstractmethod
    async def review(self, result: Result) -> ReviewResult: ...

    async def run(self, task: Task) -> Result:
        """Standard lifecycle — do NOT override this."""
        self.state = AgentState.DELIBERATING
        plan = await self.deliberate(task, await self.get_context())

        self.ledger = TaskLedger.from_plan(plan)
        await self.ledger.persist()

        self.state = AgentState.EXECUTING
        result = await self.execute(plan)

        self.state = AgentState.REVIEWING
        review = await self.review(result)

        if not review.passed:
            result = await self.retry(review.issues)

        self.state = AgentState.COMPLETED
        await self.ledger.gate_check()  # HARD STOP if incomplete
        return result
```

## Agent Hierarchy Rules

### Director (1 per Hauba instance)
- Receives owner tasks
- Deliberates for 30s minimum
- Creates project plan with milestone DAG
- Spawns SubAgents for each milestone
- WAITS for all SubAgents (event-driven, not polling)
- Reviews combined output
- Delivers to owner only after TaskLedger GateCheck passes

### SubAgent (N per project)
- Receives single milestone from Director
- Mini-deliberation (10s minimum)
- Spawns Workers for parallel sub-tasks
- Coordinates Worker dependencies
- Merges Worker outputs
- Reports back to Director

### Worker (N per SubAgent)
- Receives specific task
- Executes in isolated subprocess
- Can spawn CoWorkers for sub-sub-tasks
- Produces artifacts (code, files, analysis)
- Writes worker_log.md

### CoWorker (ephemeral)
- Single task, single result, terminate
- No persistent state
- Cheapest compute (use smallest model)
- Results bubble up to parent Worker

## Event Communication
```python
# Publishing events
await self.emit("task.completed", {
    "agent_id": self.agent_id,
    "task_id": task.id,
    "result_hash": sha256(result),
})

# Subscribing to events
self.on("milestone.completed", self.handle_milestone_done)
self.on("worker.finding_shared", self.handle_cross_team_data)
```

## DAG Execution Pattern
```python
# Milestones with dependencies run as a DAG:
# M1 (research) → M2 (design) → M3 (backend) ─┐
#                                 M4 (frontend) ─┤→ M5 (integrate) → M6 (deploy)
#
# M1 runs first. M2 waits for M1.
# M3 and M4 run IN PARALLEL after M2.
# M5 waits for BOTH M3 and M4.
```

## Memory Writing Convention
Every agent writes to `~/.hauba/agents/{task_id}/` BEFORE executing:
- `understanding.md` — What the agent understood
- `plan.md` — How it will approach the task
- `ledger.json` — TaskLedger tracking
- `todo.md` — Human-readable progress
- `worker_log.md` — Execution notes (Workers)
- `report.md` — Final completion report

**Rule: If an agent didn't write it down, it didn't think it.**
