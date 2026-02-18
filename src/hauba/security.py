"""Security module — input sanitization and prompt injection protection.

Protects against:
- Prompt injection via channel messages (WhatsApp, Telegram, Discord)
- Command injection in tool arguments
- Path traversal attacks
- Secrets leakage in outputs
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

import structlog

from hauba.exceptions import HaubaError

logger = structlog.get_logger()


class SecurityError(HaubaError):
    """Security violation detected."""


# --- Prompt Injection Detection ---

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+(instructions|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|endoftext)\|?>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|\[SYS\]", re.IGNORECASE),
    re.compile(r"```\s*system\b", re.IGNORECASE),
    re.compile(r"override\s+(safety|security|content)\s+(filter|policy|rules)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+(you\s+have\s+)?no\s+(restrictions|limitations)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(a|an)?\s*(unrestricted|jailbroken)", re.IGNORECASE),
]

# Dangerous shell metacharacters/sequences in command arguments
_COMMAND_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[;&|`$]"),                    # Shell metacharacters
    re.compile(r"\$\("),                       # Command substitution
    re.compile(r">\s*/"),                       # Redirect to absolute path
    re.compile(r"\brm\s+-rf\s+/"),             # rm -rf /
    re.compile(r"\bsudo\b"),                   # Privilege escalation
    re.compile(r"\bcurl\b.*\|\s*\b(sh|bash)\b"),  # curl | sh
    re.compile(r"\bwget\b.*\|\s*\b(sh|bash)\b"),  # wget | sh
    re.compile(r"\beval\b"),                   # eval
    re.compile(r"\bexec\b"),                   # exec
]


class InputSanitizer:
    """Sanitizes and validates user input from all channels."""

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict

    def check_prompt_injection(self, text: str) -> tuple[bool, str]:
        """Check for prompt injection patterns.

        Returns (is_safe, reason). If is_safe is False, reason explains why.
        """
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                reason = f"Potential prompt injection detected: '{match.group()}'"
                logger.warning("security.prompt_injection", text_preview=text[:100], reason=reason)
                return False, reason
        return True, ""

    def sanitize_for_llm(self, text: str, source: str = "unknown") -> str:
        """Sanitize text before sending to LLM.

        Wraps user input in clear delimiters so the LLM can distinguish
        it from system instructions.
        """
        is_safe, reason = self.check_prompt_injection(text)
        if not is_safe and self._strict:
            raise SecurityError(reason)

        # Strip any attempt to break out of user message framing
        cleaned = text.replace("<|", "").replace("|>", "")
        cleaned = cleaned.replace("[INST]", "").replace("[/INST]", "")
        cleaned = cleaned.replace("[SYS]", "")

        return f"[USER_INPUT source={source}]\n{cleaned}\n[/USER_INPUT]"

    def check_command_safety(self, command: str) -> tuple[bool, str]:
        """Check if a shell command is safe to execute.

        Returns (is_safe, reason).
        """
        for pattern in _COMMAND_INJECTION_PATTERNS:
            match = pattern.search(command)
            if match:
                reason = f"Dangerous command pattern: '{match.group()}'"
                logger.warning("security.command_injection", command_preview=command[:100])
                return False, reason
        return True, ""

    def validate_path(self, path_str: str, allowed_roots: list[Path] | None = None) -> Path:
        """Validate a file path against traversal attacks.

        Args:
            path_str: The path to validate.
            allowed_roots: If set, path must be under one of these directories.

        Returns:
            Resolved Path.

        Raises:
            SecurityError: If path is unsafe.
        """
        # Block null bytes
        if "\x00" in path_str:
            raise SecurityError("Null byte in file path")

        resolved = Path(path_str).resolve()

        # Check for traversal indicators in original string
        for part in PurePosixPath(path_str).parts + PureWindowsPath(path_str).parts:
            if part == "..":
                raise SecurityError(f"Path traversal detected in: {path_str}")

        if allowed_roots:
            if not any(self._is_under(resolved, root) for root in allowed_roots):
                raise SecurityError(
                    f"Path {resolved} is outside allowed directories"
                )

        return resolved

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        """Check if path is under root directory."""
        try:
            path.relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def redact_secrets(self, text: str) -> str:
        """Redact potential secrets from output text."""
        # API keys
        text = re.sub(r'sk-[A-Za-z0-9_-]{10,}', 'sk-***REDACTED***', text)
        text = re.sub(r'sk-proj-[A-Za-z0-9_-]{10,}', 'sk-proj-***REDACTED***', text)
        # Bearer tokens
        text = re.sub(r'Bearer\s+[A-Za-z0-9_.-]{20,}', 'Bearer ***REDACTED***', text)
        # Generic long hex/base64 tokens (40+ chars, likely secrets)
        text = re.sub(r'(?<![A-Za-z0-9])[A-Fa-f0-9]{40,}(?![A-Za-z0-9])', '***HASH_REDACTED***', text)
        return text
