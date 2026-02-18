"""Tests for compose parser."""

from __future__ import annotations

import pytest

from hauba.compose.parser import parse_compose_file, validate_compose_file
from hauba.exceptions import ComposeError

VALID_YAML = """
team: "test-team"
description: "A test team"
model: "test-model"

settings:
  max_parallel_agents: 2
  deliberation_min_seconds: 10
  sandbox: "none"

agents:
  backend:
    role: "Backend Engineer"
    description: "Builds APIs"
    skills:
      - code-generation
      - api-design-and-integration
    model: "gpt-4o"

  frontend:
    role: "Frontend Engineer"
    description: "Builds UI"
    skills:
      - code-generation
    depends_on: [backend]

strategy: "saas-building"
output: "./out"
"""

MINIMAL_YAML = """
team: "minimal"
agents:
  worker:
    role: "Worker"
"""

NO_TEAM_YAML = """
agents:
  worker:
    role: "Worker"
"""

NO_ROLE_YAML = """
team: "bad"
agents:
  worker:
    description: "Missing role"
"""

BAD_DEP_YAML = """
team: "bad"
agents:
  worker:
    role: "Worker"
    depends_on: [nonexistent]
"""

CIRCULAR_YAML = """
team: "circular"
agents:
  a:
    role: "A"
    depends_on: [b]
  b:
    role: "B"
    depends_on: [a]
"""

NOT_A_MAPPING_YAML = """
- item1
- item2
"""

AGENTS_NOT_MAPPING_YAML = """
team: "bad"
agents:
  - role: "Worker"
"""


class TestParseComposeFile:
    def test_parse_valid_compose(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(VALID_YAML, encoding="utf-8")

        config = parse_compose_file(f)

        assert config.team == "test-team"
        assert config.description == "A test team"
        assert config.model == "test-model"
        assert config.settings.max_parallel_agents == 2
        assert config.settings.deliberation_min_seconds == 10
        assert config.settings.sandbox == "none"
        assert config.strategy == "saas-building"
        assert config.output == "./out"

        assert "backend" in config.agents
        assert "frontend" in config.agents

        backend = config.agents["backend"]
        assert backend.role == "Backend Engineer"
        assert backend.description == "Builds APIs"
        assert "code-generation" in backend.skills
        assert backend.model == "gpt-4o"
        assert backend.depends_on == []

        frontend = config.agents["frontend"]
        assert frontend.depends_on == ["backend"]

    def test_parse_minimal(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(MINIMAL_YAML, encoding="utf-8")

        config = parse_compose_file(f)
        assert config.team == "minimal"
        assert len(config.agents) == 1
        assert config.agents["worker"].role == "Worker"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ComposeError, match="not found"):
            parse_compose_file(tmp_path / "nope.yaml")

    def test_missing_team(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(NO_TEAM_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="team"):
            parse_compose_file(f)

    def test_missing_role(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(NO_ROLE_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="role"):
            parse_compose_file(f)

    def test_bad_dependency(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(BAD_DEP_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="nonexistent"):
            parse_compose_file(f)

    def test_circular_dependency(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(CIRCULAR_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="[Cc]ircular"):
            parse_compose_file(f)

    def test_not_a_mapping(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(NOT_A_MAPPING_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="mapping"):
            parse_compose_file(f)

    def test_agents_not_mapping(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(AGENTS_NOT_MAPPING_YAML, encoding="utf-8")

        with pytest.raises(ComposeError, match="mapping"):
            parse_compose_file(f)

    def test_invalid_yaml_syntax(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text("team: [\ninvalid: yaml: {{", encoding="utf-8")

        with pytest.raises(ComposeError, match="[Yy]AML"):
            parse_compose_file(f)

    def test_default_settings(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(MINIMAL_YAML, encoding="utf-8")

        config = parse_compose_file(f)
        assert config.settings.max_parallel_agents == 4
        assert config.settings.sandbox == "process"
        assert config.output == "./output"


class TestValidateComposeFile:
    def test_validate_valid(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(VALID_YAML, encoding="utf-8")

        issues = validate_compose_file(f)
        assert issues == []

    def test_validate_missing_file(self, tmp_path):
        issues = validate_compose_file(tmp_path / "nope.yaml")
        assert len(issues) == 1
        assert "not found" in issues[0].lower() or "File not found" in issues[0]

    def test_validate_invalid(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text(NO_TEAM_YAML, encoding="utf-8")

        issues = validate_compose_file(f)
        assert len(issues) >= 1

    def test_validate_no_agents(self, tmp_path):
        f = tmp_path / "hauba.yaml"
        f.write_text("team: empty\nagents: {}\n", encoding="utf-8")

        issues = validate_compose_file(f)
        assert any("agent" in i.lower() for i in issues)
