"""Hauba API — HTTP service for the Hauba AI Engineer.

BYOK model: Users bring their own LLM API key. Hauba owner pays nothing.
Deployed on Railway (or any platform).
"""

from hauba.api.server import create_app

__all__ = ["create_app"]
