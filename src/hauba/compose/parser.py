"""Compose Parser — Parse hauba.yaml into ComposeConfig."""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.core.types import ComposeAgentConfig, ComposeConfig, ComposeSettings
from hauba.exceptions import ComposeError

logger = structlog.get_logger()

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_compose_file(path: Path) -> ComposeConfig:
    """Parse a hauba.yaml file into a ComposeConfig.

    Args:
        path: Path to the hauba.yaml file.

    Returns:
        A validated ComposeConfig.

    Raises:
        ComposeError: If the file cannot be parsed or is invalid.
    """
    if not path.exists():
        raise ComposeError(f"Compose file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ComposeError(f"Cannot read compose file: {exc}") from exc

    if not HAS_YAML:
        raise ComposeError("PyYAML is required for compose files. Install with: pip install pyyaml")

    try:
        data = yaml.safe_load(content)  # type: ignore[possibly-undefined]
    except yaml.YAMLError as exc:  # type: ignore[possibly-undefined]
        raise ComposeError(f"Invalid YAML syntax: {exc}") from exc

    if not isinstance(data, dict):
        raise ComposeError("Compose file must be a YAML mapping")

    return _build_config(data)


def _build_config(data: dict) -> ComposeConfig:
    """Build a ComposeConfig from parsed YAML data."""
    if "team" not in data:
        raise ComposeError("Compose file must have a 'team' field")

    # Parse settings
    settings_data = data.get("settings", {})
    settings = (
        ComposeSettings(**settings_data) if isinstance(settings_data, dict) else ComposeSettings()
    )

    # Parse agents
    agents: dict[str, ComposeAgentConfig] = {}
    agents_data = data.get("agents", {})
    if not isinstance(agents_data, dict):
        raise ComposeError("'agents' must be a mapping of agent name to config")

    for name, agent_data in agents_data.items():
        if not isinstance(agent_data, dict):
            raise ComposeError(f"Agent '{name}' config must be a mapping")
        if "role" not in agent_data:
            raise ComposeError(f"Agent '{name}' must have a 'role' field")
        agents[name] = ComposeAgentConfig(**agent_data)

    # Validate agent dependencies reference existing agents
    for name, agent in agents.items():
        for dep in agent.depends_on:
            if dep not in agents:
                raise ComposeError(f"Agent '{name}' depends on '{dep}' which is not defined")

    # Check for circular dependencies
    _check_circular_deps(agents)

    config = ComposeConfig(
        team=data["team"],
        description=data.get("description", ""),
        model=data.get("model", ""),
        settings=settings,
        agents=agents,
        output=data.get("output", "./output"),
    )

    logger.info("compose.parsed", team=config.team, agents=len(config.agents))
    return config


def _check_circular_deps(agents: dict[str, ComposeAgentConfig]) -> None:
    """Detect circular dependencies in agent graph."""
    visited: set[str] = set()
    in_stack: set[str] = set()

    def visit(name: str) -> None:
        if name in in_stack:
            raise ComposeError(f"Circular dependency detected involving '{name}'")
        if name in visited:
            return
        in_stack.add(name)
        agent = agents.get(name)
        if agent:
            for dep in agent.depends_on:
                visit(dep)
        in_stack.discard(name)
        visited.add(name)

    for agent_name in agents:
        visit(agent_name)


def validate_compose_file(path: Path) -> list[str]:
    """Validate a compose file and return a list of issues (empty if valid).

    This is a non-throwing validation that collects all issues.
    """
    issues: list[str] = []

    if not path.exists():
        issues.append(f"File not found: {path}")
        return issues

    try:
        config = parse_compose_file(path)
    except ComposeError as exc:
        issues.append(str(exc))
        return issues

    if not config.agents:
        issues.append("No agents defined")

    if not config.team:
        issues.append("Team name is empty")

    return issues
