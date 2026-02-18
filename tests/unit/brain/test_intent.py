"""Tests for Intent Parser."""

from __future__ import annotations

from hauba.brain.intent import parse_intent
from hauba.core.types import ActionType


def test_build_intent() -> None:
    intent = parse_intent("Build me a Python web app with FastAPI")
    assert intent.action == ActionType.BUILD
    assert "python" in intent.technologies
    assert "fastapi" in intent.technologies
    assert intent.confidence > 0.5


def test_edit_intent() -> None:
    intent = parse_intent("Fix the bug in the login page")
    assert intent.action in (ActionType.EDIT, ActionType.DEBUG)


def test_deploy_intent() -> None:
    intent = parse_intent("Deploy the app to AWS")
    assert intent.action == ActionType.DEPLOY
    assert "aws" in intent.technologies


def test_research_intent() -> None:
    intent = parse_intent("Research the best database for our project")
    assert intent.action == ActionType.RESEARCH


def test_unknown_intent() -> None:
    intent = parse_intent("hello world")
    # "hello world" doesn't strongly match any action
    assert intent.confidence <= 0.5


def test_multiple_technologies() -> None:
    intent = parse_intent("Create a React app with TypeScript and Tailwind CSS")
    assert intent.action == ActionType.BUILD
    assert "react" in intent.technologies
    assert "typescript" in intent.technologies
    assert "tailwind" in intent.technologies
