"""Hauba V3 function tools for the OpenAI Agents SDK.

These are custom tools that extend agent capabilities beyond the built-in
ShellTool and ApplyPatchTool. They use the @function_tool decorator from
the agents SDK for automatic schema generation.
"""

from __future__ import annotations

from typing import Any


def build_function_tools() -> list[Any]:
    """Build the list of custom function tools for Hauba agents.

    Returns a list of FunctionTool instances created via @function_tool decorator.
    These are imported lazily to avoid import errors if agents SDK isn't installed.
    """
    tools: list[Any] = []

    try:
        from agents import function_tool
    except ImportError:
        return tools

    @function_tool
    async def hauba_web_search(query: str, num_results: int = 5) -> str:
        """Search the web using DuckDuckGo. Returns titles, snippets, and URLs.

        Use this to research technologies, find documentation, look up APIs,
        and discover solutions before implementing.

        Args:
            query: The search query.
            num_results: Number of results to return (default 5).
        """
        try:
            from hauba.tools.web import WebSearchTool

            tool = WebSearchTool()
            result = await tool.execute(query=query, num_results=num_results)
            return result.output if result.success else f"Search failed: {result.error}"
        except Exception as exc:
            return f"Search error: {exc}"

    @function_tool
    async def hauba_web_fetch(url: str, extract_text: bool = True) -> str:
        """Fetch any URL and return its content as readable text.

        Supports HTML (converted to text), JSON, and plain text.
        Use this to read documentation, API responses, GitHub repos,
        and any web page content.

        Args:
            url: The URL to fetch.
            extract_text: Extract readable text from HTML (default True).
        """
        try:
            from hauba.tools.fetch import WebFetchTool

            tool = WebFetchTool()
            result = await tool.execute(url=url, extract_text=extract_text)
            return result.output if result.success else f"Fetch failed: {result.error}"
        except Exception as exc:
            return f"Fetch error: {exc}"

    @function_tool
    async def hauba_send_email(to: str, subject: str, body: str) -> str:
        """Send an email via Brevo API (free, 300/day).

        Use this to send notifications, reports, or task results.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body text.
        """
        try:
            from hauba.services.email import EmailService

            svc = EmailService()
            if not svc.configure():
                return (
                    "Email not configured. Set HAUBA_EMAIL_API_KEY (Brevo, free) "
                    "and HAUBA_EMAIL_FROM environment variables."
                )
            success = await svc.send(to=to, subject=subject, body=body)
            return "Email sent successfully." if success else "Failed to send email."
        except Exception as exc:
            return f"Email error: {exc}"

    tools.extend([hauba_web_search, hauba_web_fetch, hauba_send_email])
    return tools
