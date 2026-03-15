"""Context manager with auto-compaction for Hauba V4.

Manages conversation history and automatically compacts (summarizes)
older messages when approaching context window limits. This keeps
long-running sessions working smoothly without hitting token limits.

Inspired by OpenClaw/Pi's auto-compaction pattern:
- Track message history with token estimates
- When approaching limit, summarize older messages
- Preserve recent messages and all tool results from current turn
- Maintain key decisions and file paths through compaction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from hauba.engine.llm import LLMClient, LLMMessage

logger = structlog.get_logger()

# Rough token estimate: ~4 chars per token
CHARS_PER_TOKEN = 4


@dataclass
class ContextManager:
    """Manages conversation context with auto-compaction.

    Tracks all messages, estimates token usage, and automatically
    summarizes older messages when approaching the context window limit.

    Attributes:
        system_prompt: The system prompt (always included).
        max_context_tokens: Maximum tokens before compaction triggers.
        compaction_threshold: Fraction of max before triggering (0.75 = 75%).
    """

    system_prompt: str = ""
    max_context_tokens: int = 120_000
    compaction_threshold: float = 0.75
    _messages: list[LLMMessage] = field(default_factory=list)
    _compaction_count: int = 0

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self._messages.append(LLMMessage(role="user", content=content))

    def add_assistant_message(
        self,
        text: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add an assistant message (with optional tool calls)."""
        self._messages.append(
            LLMMessage(
                role="assistant",
                content=text or "",
                tool_calls=tool_calls,
            )
        )

    def add_tool_result(
        self,
        tool_use_id: str,
        content: str,
        is_error: bool = False,
    ) -> None:
        """Add a tool result to the conversation."""
        prefix = "[ERROR] " if is_error else ""
        self._messages.append(
            LLMMessage(
                role="tool",
                content=f"{prefix}{content}",
                tool_call_id=tool_use_id,
            )
        )

    def get_messages(self) -> list[LLMMessage]:
        """Get all messages for the next LLM call."""
        return list(self._messages)

    def estimate_tokens(self) -> int:
        """Estimate total token count of current context."""
        total = len(self.system_prompt) // CHARS_PER_TOKEN

        for msg in self._messages:
            content = msg.content
            if isinstance(content, str):
                total += len(content) // CHARS_PER_TOKEN
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += len(str(block)) // CHARS_PER_TOKEN
                    else:
                        total += len(str(block)) // CHARS_PER_TOKEN

            # Tool calls add tokens too
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total += len(str(tc)) // CHARS_PER_TOKEN

        return total

    def should_compact(self) -> bool:
        """Check if context should be compacted."""
        estimated = self.estimate_tokens()
        threshold = int(self.max_context_tokens * self.compaction_threshold)
        return estimated > threshold

    async def compact(self, llm: LLMClient) -> None:
        """Compact older messages by summarizing them.

        Strategy:
        1. Keep the last N messages intact (recent context)
        2. Summarize everything before that into a single message
        3. Replace old messages with the summary

        This preserves recent tool calls and results while condensing
        older conversation history.
        """
        if len(self._messages) < 6:
            # Not enough messages to compact
            return

        self._compaction_count += 1

        # Keep the last 4 messages intact (recent context)
        # Summarize everything before that
        keep_count = min(4, len(self._messages))
        old_messages = self._messages[:-keep_count]
        recent_messages = self._messages[-keep_count:]

        # Build text to summarize
        summary_text = self._messages_to_text(old_messages)

        try:
            summary = await llm.summarize(summary_text, max_tokens=1000)

            # Replace old messages with summary
            self._messages = [
                LLMMessage(
                    role="user",
                    content=(
                        f"[Context summary — compaction #{self._compaction_count}]\n\n"
                        f"{summary}\n\n"
                        "[End of summary. Continue with the task.]"
                    ),
                ),
                *recent_messages,
            ]

            logger.info(
                "context.compacted",
                old_messages=len(old_messages),
                kept=keep_count,
                compaction=self._compaction_count,
            )
        except Exception as e:
            logger.warning("context.compaction_failed", error=str(e))
            # Fallback: just trim oldest messages
            self._messages = self._messages[-(keep_count + 2) :]

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._compaction_count = 0

    @property
    def message_count(self) -> int:
        """Number of messages in context."""
        return len(self._messages)

    def _messages_to_text(self, messages: list[LLMMessage]) -> str:
        """Convert messages to plain text for summarization."""
        parts: list[str] = []
        for msg in messages:
            role = msg.role.upper()
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if msg.tool_calls:
                tool_names = [tc.get("name", "?") for tc in msg.tool_calls]
                parts.append(f"[{role}] Called tools: {', '.join(tool_names)}")
            elif msg.role == "tool":
                # Truncate long tool outputs for summarization
                truncated = content[:2000] if len(content) > 2000 else content
                parts.append(f"[TOOL RESULT] {truncated}")
            else:
                parts.append(f"[{role}] {content}")
        return "\n\n".join(parts)
