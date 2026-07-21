"""In-memory provider health for smart failover (skip 502/timeout temporarily)."""
from __future__ import annotations
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional


class ProviderHealth:
    """Tracks recent success/fail per provider; supports temporary skip after hard errors."""

    def __init__(self, window: int = 40, skip_sec: float = 180.0, fail_streak_skip: int = 2):
        self.window = window
        self.skip_sec = skip_sec
        self.fail_streak_skip = fail_streak_skip
        self._events: Dict[str, Deque[tuple]] = defaultdict(lambda: deque(maxlen=window))  # (ts, ok)
        self._skip_until: Dict[str, float] = {}
        self._fail_streak: Dict[str, int] = defaultdict(int)

    def record_success(self, provider_id: str):
        if not provider_id:
            return
        now = time.time()
        self._events[provider_id].append((now, True))
        self._fail_streak[provider_id] = 0
        # clear skip on success
        self._skip_until.pop(provider_id, None)

    def record_failure(self, provider_id: str, hard: bool = False, status_code: Optional[int] = None):
        if not provider_id:
            return
        now = time.time()
        self._events[provider_id].append((now, False))
        self._fail_streak[provider_id] += 1
        # hard errors: 502/503/504/timeout → skip immediately
        if hard or (status_code and status_code in (502, 503, 504, 429)):
            self._skip_until[provider_id] = now + self.skip_sec
        elif self._fail_streak[provider_id] >= self.fail_streak_skip:
            self._skip_until[provider_id] = now + self.skip_sec

    def is_skipped(self, provider_id: str) -> bool:
        until = self._skip_until.get(provider_id)
        if not until:
            return False
        if time.time() >= until:
            self._skip_until.pop(provider_id, None)
            return False
        return True

    def success_rate(self, provider_id: str, lookback_sec: float = 3600.0) -> float:
        now = time.time()
        ev = [ok for ts, ok in self._events.get(provider_id, []) if now - ts <= lookback_sec]
        if not ev:
            return 1.0  # unknown = assume healthy
        return sum(1 for ok in ev if ok) / len(ev)

    def sort_provider_ids(self, provider_ids: List[str]) -> List[str]:
        """Prefer non-skipped + higher success rate; stable among equals."""
        def key(pid: str):
            skipped = 1 if self.is_skipped(pid) else 0
            rate = self.success_rate(pid)
            return (skipped, -rate)

        return sorted(provider_ids, key=key)

    def status_snapshot(self) -> dict:
        now = time.time()
        out = {}
        ids = set(self._events.keys()) | set(self._skip_until.keys())
        for pid in ids:
            until = self._skip_until.get(pid)
            out[pid] = {
                "success_rate_1h": round(self.success_rate(pid), 3),
                "fail_streak": self._fail_streak.get(pid, 0),
                "skipped": bool(until and until > now),
                "skip_remaining_sec": max(0, int((until or 0) - now)),
            }
        return out


HEALTH = ProviderHealth()
