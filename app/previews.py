"""Small, bounded in-memory cache for derived preview images, never source files."""
from collections import OrderedDict
from threading import Lock


class PreviewCache:
    def __init__(self, max_bytes=32*1024**2, max_entries=64):
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self._items = OrderedDict()
        self._bytes = 0
        self._lock = Lock()

    def get(self, key, build):
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        # Painting one image must not block reads of other cached previews.
        value = build()
        if len(value) > self.max_bytes:
            return value
        with self._lock:
            previous = self._items.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous)
            self._items[key] = value
            self._bytes += len(value)
            while self._bytes > self.max_bytes or len(self._items) > self.max_entries:
                _, evicted = self._items.popitem(last=False)
                self._bytes -= len(evicted)
        return value

    def clear(self):
        with self._lock:
            self._items.clear()
            self._bytes = 0


def file_signature(path):
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size
