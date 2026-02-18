"""Intent parser — converts natural language to structured intent."""

from __future__ import annotations

import re

import structlog
from pydantic import BaseModel, Field

from hauba.core.types import ActionType

logger = structlog.get_logger()

# Keyword patterns for action detection
_ACTION_PATTERNS: dict[ActionType, list[str]] = {
    ActionType.BUILD: [
        r"\b(build|create|make|generate|scaffold|setup|init|new|write)\b",
    ],
    ActionType.EDIT: [
        r"\b(edit|modify|change|update|fix|refactor|rename|move|replace)\b",
    ],
    ActionType.ANALYZE: [
        r"\b(analyze|review|inspect|check|audit|explain|understand|read)\b",
    ],
    ActionType.DEPLOY: [
        r"\b(deploy|publish|release|push|ship|launch|host)\b",
    ],
    ActionType.RESEARCH: [
        r"\b(research|find|search|look|investigate|explore|discover)\b",
    ],
    ActionType.DEBUG: [
        r"\b(debug|troubleshoot|diagnose|trace|profile|why|error|bug|broken)\b",
    ],
    ActionType.TEST: [
        r"\b(test|verify|validate|assert|check|ensure|spec)\b",
    ],
}


class Intent(BaseModel):
    """Parsed intent from user instruction."""

    raw_instruction: str
    action: ActionType = ActionType.UNKNOWN
    subject: str = ""
    details: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    technologies: list[str] = Field(default_factory=list)


# Common technology keywords
_TECH_KEYWORDS = [
    "python", "javascript", "typescript", "react", "vue", "angular", "node",
    "django", "flask", "fastapi", "express", "next", "svelte",
    "rust", "go", "java", "kotlin", "swift", "c\\+\\+",
    "docker", "kubernetes", "aws", "gcp", "azure",
    "postgres", "mysql", "sqlite", "mongodb", "redis",
    "html", "css", "tailwind", "bootstrap",
    "git", "github", "api", "rest", "graphql", "grpc",
    "stripe", "auth", "oauth", "jwt",
]


def parse_intent(instruction: str) -> Intent:
    """Parse a natural language instruction into a structured Intent."""
    text = instruction.lower().strip()

    # Detect action
    action = ActionType.UNKNOWN
    best_confidence = 0.0

    for act, patterns in _ACTION_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text)
            confidence = len(matches) * 0.3
            if confidence > best_confidence:
                best_confidence = confidence
                action = act

    # Cap confidence at 1.0
    confidence = min(best_confidence + 0.4, 1.0) if action != ActionType.UNKNOWN else 0.2

    # Extract technologies mentioned
    technologies = []
    for tech in _TECH_KEYWORDS:
        if re.search(rf"\b{tech}\b", text):
            technologies.append(tech.replace("\\+\\+", "++"))

    # Extract subject (first noun phrase after action verb, simplified)
    subject = instruction.strip()
    if len(subject) > 100:
        subject = subject[:100] + "..."

    intent = Intent(
        raw_instruction=instruction,
        action=action,
        subject=subject,
        confidence=confidence,
        technologies=technologies,
    )

    logger.info(
        "intent.parsed",
        action=action.value,
        confidence=f"{confidence:.2f}",
        technologies=technologies,
    )
    return intent
