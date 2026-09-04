"""
Shared rate limiter (slowapi) used across the app.

A single :class:`Limiter` instance is created here so both ``main.py`` and the
individual channel routers can reference the same limiter for per-route limits,
while a global default limit protects every endpoint.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from . import config

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[config.RATE_LIMIT_WEBHOOK],
)
