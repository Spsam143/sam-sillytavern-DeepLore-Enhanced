import threading
import json

class RingBuffer:
    def __init__(self, capacity=500):
        self.capacity = max(1, int(capacity))
        self.items = []
        self.lock = threading.Lock()

    def push(self, item):
        with self.lock:
            try:
                self.items.append(item)
                if len(self.items) > self.capacity:
                    # Remove from the beginning
                    self.items = self.items[-self.capacity:]
            except Exception:
                pass # Never throw

    def drain(self):
        with self.lock:
            return list(self.items)

    def flush(self):
        with self.lock:
            snapshot = list(self.items)
            self.items = []
            return snapshot

    def __len__(self):
        with self.lock:
            return len(self.items)

    def clear(self):
        with self.lock:
            self.items = []

def make_json_replacer():
    seen = set()

    def replacer(obj):
        if hasattr(obj, '__dict__') or isinstance(obj, dict):
            obj_id = id(obj)
            if obj_id in seen:
                return '[circular]'
            seen.add(obj_id)

        if callable(obj):
            return f"[fn {getattr(obj, '__name__', 'anon')}]"

        if isinstance(obj, type) and not isinstance(obj, Exception):
            return str(obj)

        return obj
    return replacer

class CustomEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen = set()

    def default(self, obj):
        if hasattr(obj, '__dict__') or isinstance(obj, dict):
            obj_id = id(obj)
            if obj_id in self.seen:
                return '[circular]'
            self.seen.add(obj_id)

        if callable(obj):
            return f"[fn {getattr(obj, '__name__', 'anon')}]"

        if isinstance(obj, Exception):
            return f"{obj.__class__.__name__}: {str(obj)}"

        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

def safe_stringify(args, max_len=2000):
    try:
        parts = []
        for a in args:
            if a is None:
                parts.append('null')
                continue
            t = type(a)
            if t is str:
                parts.append(a)
                continue
            if t in (int, float, bool):
                parts.append(str(a))
                continue
            if isinstance(a, Exception):
                parts.append(f"{a.__class__.__name__}: {str(a)}")
                continue

            try:
                parts.append(json.dumps(a, cls=CustomEncoder))
            except Exception:
                parts.append('[unserializable]')

        out = parts[0] if len(parts) == 1 else ' | '.join(parts)
        if len(out) > max_len:
            out = out[:max_len] + f"…[+{len(out) - max_len} chars]"
        return out
    except Exception:
        return '[stringify failed]'
