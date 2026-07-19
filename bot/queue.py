"""1 job per user anti-spam queue."""
import asyncio


class GenQueue:
    def __init__(self):
        self._busy: set[int] = set()
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: int) -> bool:
        async with self._lock:
            if user_id in self._busy:
                return False
            self._busy.add(user_id)
            return True

    async def release(self, user_id: int):
        async with self._lock:
            self._busy.discard(user_id)

    def is_busy(self, user_id: int) -> bool:
        return user_id in self._busy

    def busy_count(self) -> int:
        return len(self._busy)


QUEUE = GenQueue()
