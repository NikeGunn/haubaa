"""Strategy Engine — Parse .yaml strategy files and auto-create TaskLedgers.

Strategies are cognitive playbooks that teach agents HOW to think about a domain.
They define milestones, tasks, dependencies, quality gates, and agent team compositions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from hauba.core.constants import STRATEGIES_DIR
from hauba.core.types import Milestone, TaskStep
from hauba.ledger.tracker import TaskLedger

logger = structlog.get_logger()

# Minimum score required for a strategy to match a task.
# Domain keyword match = 5, name-word match = 2, description-word match = 1.
# A threshold of 5 prevents weak false-positive matches (e.g., score=2).
MINIMUM_STRATEGY_MATCH_SCORE = 5

# Use yaml if available, otherwise fall back to basic parsing
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class AgentSpec:
    """Specification for an agent in a strategy."""

    role: str
    skills: list[str] = field(default_factory=list)
    model: str = ""


@dataclass
class Strategy:
    """A parsed strategy from a .yaml file."""

    name: str
    description: str
    file_path: Path
    domain: str = ""
    agents: list[AgentSpec] = field(default_factory=list)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_milestone_objects(self) -> list[Milestone]:
        """Convert strategy milestones to Milestone type objects."""
        result: list[Milestone] = []
        for ms in self.milestones:
            tasks = []
            for i, task in enumerate(ms.get("tasks", []), 1):
                if isinstance(task, str):
                    tasks.append(
                        TaskStep(
                            id=f"{ms['id']}-task-{i}",
                            description=task,
                        )
                    )
                elif isinstance(task, dict):
                    tasks.append(
                        TaskStep(
                            id=task.get("id", f"{ms['id']}-task-{i}"),
                            description=task.get("description", str(task)),
                            tool=task.get("tool"),
                            dependencies=task.get("dependencies", []),
                        )
                    )

            result.append(
                Milestone(
                    id=ms.get("id", f"milestone-{len(result) + 1}"),
                    description=ms.get("description", ""),
                    dependencies=ms.get("dependencies", []),
                    tasks=tasks,
                )
            )
        return result

    def create_ledger(self, workspace: Path | None = None) -> TaskLedger:
        """Auto-create a TaskLedger from this strategy's milestones."""
        milestones = self.to_milestone_objects()
        steps = []
        for ms in milestones:
            steps.append(
                {
                    "id": ms.id,
                    "description": ms.description,
                    "dependencies": ms.dependencies,
                }
            )

        ledger = TaskLedger.from_plan(steps, f"strategy-{self.name}", workspace)
        logger.info("strategy.ledger_created", strategy=self.name, tasks=len(steps))
        return ledger


class StrategyEngine:
    """Loads, matches, and applies .yaml strategy files."""

    def __init__(self, strategy_dirs: list[Path] | None = None) -> None:
        self._strategy_dirs = strategy_dirs or [STRATEGIES_DIR]
        self._strategies: dict[str, Strategy] = {}
        self._loaded = False

    def load_all(self) -> dict[str, Strategy]:
        """Load all .yaml strategy files."""
        self._strategies.clear()

        for sdir in self._strategy_dirs:
            if not sdir.exists():
                continue
            for yaml_file in sdir.rglob("*.yaml"):
                try:
                    strategy = self._parse_strategy_file(yaml_file)
                    if strategy:
                        self._strategies[strategy.name] = strategy
                except Exception as exc:
                    logger.warning("strategy.load_error", file=str(yaml_file), error=str(exc))
            # Also support .yml extension
            for yml_file in sdir.rglob("*.yml"):
                try:
                    strategy = self._parse_strategy_file(yml_file)
                    if strategy:
                        self._strategies[strategy.name] = strategy
                except Exception as exc:
                    logger.warning("strategy.load_error", file=str(yml_file), error=str(exc))

        self._loaded = True
        logger.info("strategies.loaded", count=len(self._strategies))
        return self._strategies

    def get(self, name: str) -> Strategy | None:
        """Get a strategy by name."""
        if not self._loaded:
            self.load_all()
        return self._strategies.get(name)

    def match_domain(self, task_description: str) -> Strategy | None:
        """Find the best strategy for a task based on domain keywords."""
        if not self._loaded:
            self.load_all()

        task_lower = task_description.lower()
        best_match: Strategy | None = None
        best_score = 0

        for strategy in self._strategies.values():
            score = 0
            # Check domain keyword
            if strategy.domain and strategy.domain.lower() in task_lower:
                score += 5
            # Check name keywords
            for word in strategy.name.replace("-", " ").split():
                if word.lower() in task_lower:
                    score += 2
            # Check description keywords
            if strategy.description:
                for word in strategy.description.lower().split():
                    if len(word) > 4 and word in task_lower:
                        score += 1

            if score > best_score:
                best_score = score
                best_match = strategy

        # Enforce minimum score threshold to prevent false-positive matches
        if best_match and best_score >= MINIMUM_STRATEGY_MATCH_SCORE:
            logger.info("strategy.matched", name=best_match.name, score=best_score)
            return best_match

        if best_match and best_score > 0:
            logger.info(
                "strategy.below_threshold",
                name=best_match.name,
                score=best_score,
                threshold=MINIMUM_STRATEGY_MATCH_SCORE,
            )

        return None

    def list_strategies(self) -> list[str]:
        if not self._loaded:
            self.load_all()
        return sorted(self._strategies.keys())

    @property
    def strategies(self) -> dict[str, Strategy]:
        if not self._loaded:
            self.load_all()
        return self._strategies

    def _parse_strategy_file(self, path: Path) -> Strategy | None:
        """Parse a .yaml strategy file."""
        content = path.read_text(encoding="utf-8")

        data = yaml.safe_load(content) or {} if HAS_YAML else self._basic_yaml_parse(content)

        if not data:
            return None

        # Parse agents
        agents = []
        for agent_data in data.get("agents", []):
            if isinstance(agent_data, dict):
                agents.append(
                    AgentSpec(
                        role=agent_data.get("role", "worker"),
                        skills=agent_data.get("skills", []),
                        model=agent_data.get("model", ""),
                    )
                )

        strategy = Strategy(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            file_path=path,
            domain=data.get("domain", ""),
            agents=agents,
            milestones=data.get("milestones", []),
            quality_gates=data.get("quality_gates", []),
            raw_data=data,
        )
        return strategy

    def _basic_yaml_parse(self, content: str) -> dict[str, Any]:
        """Very basic YAML-like parser for when pyyaml isn't installed.

        Only handles simple key: value pairs and lists. For production
        use, install pyyaml.
        """
        result: dict[str, Any] = {}
        current_key = ""
        current_list: list[Any] = []

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            len(line) - len(line.lstrip())

            if stripped.startswith("- ") and current_key:
                item = stripped[2:].strip()
                current_list.append(item)
                result[current_key] = current_list
            elif ":" in stripped and not stripped.startswith("-"):
                # Save previous list
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()

                if value:
                    result[key] = value
                else:
                    current_key = key
                    current_list = []
                    result[current_key] = current_list

        return result
