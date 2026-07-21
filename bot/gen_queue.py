"""Global + per-user generation queue with position + ETA."""
from __future__ import annotations
import asyncio
import time
from collections import deque
from typing import Awaitable, Callable, Deque, Dict, Optional, Tuple

WaitCallback = Callable[[int, int], Awaitable[None]]  # (position, eta_sec)


class GenQueue:
    """FIFO global queue + per-user anti-spam.

    - One job per user (join returns False if already waiting/running).
    - max_concurrent parallel jobs globally.
    - position: 0 running, 1+ waiting, -1 unknown.
    - ETA from rolling average job duration.
    """

    def __init__(self, max_concurrent: int = 3, default_eta_sec: float = 45.0):
        self._max_concurrent = max(1, int(max_concurrent))
        self._default_eta = float(default_eta_sec)
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)
        self._waiting: Deque[Tuple[int, float]] = deque()
        self._running: Dict[int, float] = {}
        self._user_state: Dict[int, str] = {}
        self._durations: Deque[float] = deque(maxlen=40)
        self._avg_sec = self._default_eta

    def _recalc_avg(self):
        if self._durations:
            self._avg_sec = sum(self._durations) / len(self._durations)
        else:
            self._avg_sec = self._default_eta

    def busy_count(self) -> int:
        return len(self._running) + len(self._waiting)

    def is_busy(self, user_id: int) -> bool:
        return user_id in self._user_state

    def position_of(self, user_id: int) -> int:
        if user_id in self._running:
            return 0
        for i, (uid, _) in enumerate(self._waiting):
            if uid == user_id:
                return i + 1
        return -1

    def eta_sec(self, user_id: int) -> int:
        pos = self.position_of(user_id)
        if pos < 0:
            return 0
        if pos == 0:
            return max(5, int(self._avg_sec * 0.45))
        free = max(1, self._max_concurrent)
        waves = (pos + free - 1) // free
        return max(8, int(waves * self._avg_sec))

    def snapshot(self, user_id: int) -> dict:
        pos = self.position_of(user_id)
        return {
            "position": pos,
            "eta_sec": self.eta_sec(user_id) if pos >= 0 else 0,
            "busy_total": self.busy_count(),
            "running": len(self._running),
            "waiting": len(self._waiting),
            "avg_sec": int(self._avg_sec),
        }

    def _try_promote(self, user_id: int) -> bool:
        if (
            len(self._running) < self._max_concurrent
            and self._waiting
            and self._waiting[0][0] == user_id
        ):
            self._waiting.popleft()
            self._running[user_id] = time.monotonic()
            self._user_state[user_id] = "running"
            return True
        return False

    def _remove_waiting(self, user_id: int):
        self._waiting = deque((u, t) for u, t in self._waiting if u != user_id)

    async def acquire(
        self,
        user_id: int,
        timeout: float = 600.0,
        on_wait: Optional[WaitCallback] = None,
    ) -> bool:
        """Join queue. False if user already queued/running.

        Blocks until a concurrent slot is free. Calls on_wait(pos, eta) ~every 2s while waiting.
        """
        async with self._cond:
            if user_id in self._user_state:
                return False
            self._waiting.append((user_id, time.monotonic()))
            self._user_state[user_id] = "waiting"
            deadline = time.monotonic() + timeout
            last_notify = 0.0
            try:
                while True:
                    if self._try_promote(user_id):
                        return True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._remove_waiting(user_id)
                        self._user_state.pop(user_id, None)
                        self._cond.notify_all()
                        return False
                    now = time.monotonic()
                    if on_wait and (now - last_notify) >= 1.5:
                        pos = self.position_of(user_id)
                        eta = self.eta_sec(user_id)
                        last_notify = now
                        # release lock while awaiting callback
                        self._cond.release()
                        try:
                            await on_wait(pos, eta)
                        except Exception:
                            pass
                        finally:
                            await self._cond.acquire()
                        # re-check after callback
                        if user_id not in self._user_state:
                            return False
                        if self._try_promote(user_id):
                            return True
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=min(2.0, remaining))
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                self._remove_waiting(user_id)
                self._running.pop(user_id, None)
                self._user_state.pop(user_id, None)
                self._cond.notify_all()
                raise

    async def release(self, user_id: int):
        async with self._cond:
            start = self._running.pop(user_id, None)
            self._user_state.pop(user_id, None)
            self._remove_waiting(user_id)
            if start is not None:
                self._durations.append(max(1.0, time.monotonic() - start))
                self._recalc_avg()
            self._cond.notify_all()


QUEUE = GenQueue(max_concurrent=3, default_eta_sec=45.0)
