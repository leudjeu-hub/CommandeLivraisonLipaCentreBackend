"""Throttles, in memory (one Render instance, so no shared store is needed).

- Logins: after ``MAX_FAILURES`` wrong passwords for the same e-mail within ``WINDOW_SECONDS``,
  further logins for that e-mail are refused (429) until the oldest failure leaves the window. A
  correct password resets the count.
- Sign-ups: at most ``MAX_REGISTRATIONS`` new accounts per ``REGISTER_WINDOW_SECONDS`` for the
  whole site (customers do not need an account; the shop expects a handful a day), so a script
  cannot fill the database with accounts.

Keyed by e-mail or site-wide rather than by IP: behind Render's proxy every client shares the
proxy's address, and X-Forwarded-For can be forged.
"""

import time
from collections import deque

MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60
MAX_REGISTRATIONS = 30
REGISTER_WINDOW_SECONDS = 60 * 60
# Beyond this many tracked e-mails, stale ones are dropped so memory stays bounded.
MAX_KEYS = 10_000


class Throttle:
    """At most ``limit`` recorded events per key within ``window`` seconds."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key, deque())
        while failures and now - failures[0] > self.window:
            failures.popleft()
        return failures

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key, time.monotonic())) >= self.limit

    def record_failure(self, key: str) -> None:
        """Record one event (a failed login, a new account) for this key."""
        now = time.monotonic()
        if len(self._failures) >= MAX_KEYS:
            self._failures = {k: f for k, f in self._failures.items() if self._recent(k, now)}
        failures = self._recent(key, now)
        failures.append(now)
        self._failures[key] = failures

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._failures.clear()
        else:
            self._failures.pop(key, None)


login_throttle = Throttle(MAX_FAILURES, WINDOW_SECONDS)
register_throttle = Throttle(MAX_REGISTRATIONS, REGISTER_WINDOW_SECONDS)
# The single key of register_throttle (the limit is site-wide)
ALL = "*"
