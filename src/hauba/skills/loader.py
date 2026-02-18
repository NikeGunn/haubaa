"""Skill Loader — Parse .md skill files into structured skill objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from hauba.core.constants import SKILLS_DIR
from hauba.exceptions import SkillNotFoundError

logger = structlog.get_logger()


@dataclass
class Skill:
    """A parsed skill from a .md file."""

    name: str
    file_path: Path
    capabilities: list[str] = field(default_factory=list)
    when_to_use: list[str] = field(default_factory=list)
    approach: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    raw_content: str = ""

    @property
    def keywords(self) -> set[str]:
        """Extract keywords from capabilities and when_to_use for matching."""
        words: set[str] = set()
        for text in self.capabilities + self.when_to_use:
            words.update(w.lower() for w in re.findall(r'\w+', text) if len(w) > 3)
        return words


class SkillLoader:
    """Loads and parses .md skill files into Skill objects.

    Skill files follow a standard format:
    ```
    # Skill: my-skill
    ## Capabilities
    - What this skill enables
    ## When To Use
    - Trigger conditions
    ## Approach
    1. Steps
    ## Constraints
    - Limitations
    ```
    """

    def __init__(self, skill_dirs: list[Path] | None = None) -> None:
        self._skill_dirs = skill_dirs or [SKILLS_DIR]
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def load_all(self) -> dict[str, Skill]:
        """Load all .md skill files from configured directories."""
        self._skills.clear()

        for skill_dir in self._skill_dirs:
            if not skill_dir.exists():
                continue
            for md_file in skill_dir.rglob("*.md"):
                try:
                    skill = self._parse_skill_file(md_file)
                    if skill:
                        self._skills[skill.name] = skill
                except Exception as exc:
                    logger.warning("skill.load_error", file=str(md_file), error=str(exc))

        self._loaded = True
        logger.info("skills.loaded", count=len(self._skills))
        return self._skills

    def get(self, name: str) -> Skill:
        """Get a skill by name."""
        if not self._loaded:
            self.load_all()
        skill = self._skills.get(name)
        if not skill:
            raise SkillNotFoundError(f"Skill '{name}' not found")
        return skill

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        if not self._loaded:
            self.load_all()
        return sorted(self._skills.keys())

    @property
    def skills(self) -> dict[str, Skill]:
        if not self._loaded:
            self.load_all()
        return self._skills

    def _parse_skill_file(self, path: Path) -> Skill | None:
        """Parse a single .md skill file."""
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Extract skill name from "# Skill: name" header
        name = None
        for line in lines:
            if line.strip().startswith("# Skill:") or line.strip().startswith("# "):
                name_part = line.strip().lstrip("# ").replace("Skill:", "").strip()
                name = name_part.lower().replace(" ", "-")
                break

        if not name:
            name = path.stem.lower()

        skill = Skill(name=name, file_path=path, raw_content=content)

        # Parse sections
        current_section = ""
        for line in lines:
            stripped = line.strip()

            if stripped.startswith("## Capabilities") or stripped.startswith("## capabilities"):
                current_section = "capabilities"
                continue
            elif stripped.startswith("## When To Use") or stripped.startswith("## When to Use"):
                current_section = "when_to_use"
                continue
            elif stripped.startswith("## Approach") or stripped.startswith("## approach"):
                current_section = "approach"
                continue
            elif stripped.startswith("## Constraints") or stripped.startswith("## constraints"):
                current_section = "constraints"
                continue
            elif stripped.startswith("## "):
                current_section = ""
                continue

            if not stripped or stripped.startswith("#"):
                continue

            # Clean list item prefix
            item = stripped.lstrip("- ").lstrip("0123456789. ")
            if not item:
                continue

            if current_section == "capabilities":
                skill.capabilities.append(item)
            elif current_section == "when_to_use":
                skill.when_to_use.append(item)
            elif current_section == "approach":
                skill.approach.append(item)
            elif current_section == "constraints":
                skill.constraints.append(item)

        return skill
