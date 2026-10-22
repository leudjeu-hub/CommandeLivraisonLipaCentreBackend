"""Failed-login throttle, in memory (one Render instance, so no shared store is needed).

After ``MAX_FAILURES`` wrong passwords for the same e-mail within ``WINDOW_SECONDS``, further
logins for that e-mail are refused (429) until the oldest failure leaves the window. A correct
password resets the count. Keyed by e-mail rather than IP: behind Render's proxy every client
shares the proxy's address.
"""

import time
from collections import deque

MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60
# Beyond this many tracked e-mails, stale ones are dropped so memory stays bounded.
MAX_KEYS = 10_000


class LoginThrottle:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key, deque())
        while failures and now - failures[0] > WINDOW_SECONDS:
            failures.popleft()
        return failures

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key, time.monotonic())) >= MAX_FAILURES

    def record_failure(self, key: str) -> None:
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


login_throttle = LoginThrottle()
