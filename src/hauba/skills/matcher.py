"""Skill Matcher — Match task requirements to available skills."""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from hauba.skills.loader import Skill, SkillLoader

logger = structlog.get_logger()


@dataclass
class SkillMatch:
    """A skill matched to a task with a relevance score."""

    skill: Skill
    score: float  # 0.0 - 1.0
    matched_keywords: list[str]


class SkillMatcher:
    """Matches task descriptions to the best available skills.

    Uses keyword overlap and semantic matching to find relevant skills.
    """

    def __init__(self, loader: SkillLoader) -> None:
        self._loader = loader

    def match(self, task_description: str, top_k: int = 3) -> list[SkillMatch]:
        """Find the best matching skills for a task description.

        Returns up to top_k matches sorted by relevance score (descending).
        """
        skills = self._loader.skills
        if not skills:
            return []

        # Extract keywords from task
        task_words = set(w.lower() for w in re.findall(r"\w+", task_description) if len(w) > 3)

        matches: list[SkillMatch] = []
        for skill in skills.values():
            skill_words = skill.keywords
            if not skill_words:
                continue

            # Keyword overlap score
            overlap = task_words & skill_words
            if not overlap:
                continue

            score = len(overlap) / max(len(task_words), 1)
            # Boost score for "when_to_use" matches
            for trigger in skill.when_to_use:
                trigger_words = set(w.lower() for w in re.findall(r"\w+", trigger) if len(w) > 3)
                trigger_overlap = task_words & trigger_words
                if trigger_overlap:
                    score += 0.2 * (len(trigger_overlap) / max(len(trigger_words), 1))

            score = min(1.0, score)
            matches.append(
                SkillMatch(
                    skill=skill,
                    score=score,
                    matched_keywords=sorted(overlap),
                )
            )

        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)

        if matches:
            logger.info(
                "skills.matched",
                task=task_description[:50],
                top_match=matches[0].skill.name,
                score=round(matches[0].score, 2),
            )

        return matches[:top_k]

    def best_match(self, task_description: str) -> SkillMatch | None:
        """Return the single best skill match, or None if no match."""
        matches = self.match(task_description, top_k=1)
        return matches[0] if matches else None

    def compose_skills(self, skill_names: list[str]) -> str:
        """Compose multiple skills into a combined instruction set.

        Merges capabilities, approach steps, and constraints from all skills.
        """
        parts = ["# Combined Skills\n"]

        for name in skill_names:
            try:
                skill = self._loader.get(name)
            except Exception:
                continue

            parts.append(f"\n## {skill.name}\n")
            if skill.capabilities:
                parts.append("\n### Capabilities\n")
                for cap in skill.capabilities:
                    parts.append(f"- {cap}\n")
            if skill.approach:
                parts.append("\n### Approach\n")
                for i, step in enumerate(skill.approach, 1):
                    parts.append(f"{i}. {step}\n")
            if skill.constraints:
                parts.append("\n### Constraints\n")
                for c in skill.constraints:
                    parts.append(f"- {c}\n")

        return "".join(parts)
