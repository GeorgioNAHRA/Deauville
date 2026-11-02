from threading import RLock

from deauville.storage import JsonStorage


class FestivalService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage
        self._lock = RLock()

    def read(self, operation: str, *args):
        with self._lock:
            festival = self.storage.load()
            return getattr(festival, operation)(*args)

    def change(self, operation: str, *args):
        with self._lock:
            festival = self.storage.load()
            result = getattr(festival, operation)(*args)
            self.storage.save(festival)
            return result
