"""Thread-safe run feedback and explicit decisions from the run owner."""
import logging
import queue
import threading


class RunStopped(RuntimeError):
    pass


class RecipientNotFound(RuntimeError):
    pass


class RunControl:
    def __init__(self, notify=None):
        self.notify = notify
        self.cancelled = threading.Event()
        self.decisions = queue.Queue()
        self.pending = None
        self.completed = 0
        self.total = 0

    def emit(self, kind, message):
        logging.getLogger(__name__).info("%s: %s", kind, message)
        if self.notify:
            self.notify(kind, message, self.completed, self.total)

    def check(self):
        if self.cancelled.is_set():
            raise RunStopped("Run gestopt; reeds bevestigde voortgang staat in de log")

    def request(self, kind, message):
        self.pending = kind
        self.emit("paused", message)

    def decide(self, kind, value):
        if self.pending != kind:
            return False
        self.decisions.put((kind, value))
        return True

    def poll(self):
        self.check()
        try:
            kind, value = self.decisions.get_nowait()
            if kind == self.pending:
                self.pending = None
                return value
        except queue.Empty:
            pass
        return None

    def resume(self, message):
        self.pending = None
        # Discard stale decisions before another snap can be sent.
        while not self.decisions.empty():
            try:
                self.decisions.get_nowait()
            except queue.Empty:
                break
        self.emit("resumed", message)
