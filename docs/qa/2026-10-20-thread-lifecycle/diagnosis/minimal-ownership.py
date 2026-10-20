"""Offline diagnostic: exact worker teardown wiring with/without QThread parent."""
import argparse
import json
import sys
import time

from PySide6 import __version__
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, QTimer, Signal, Slot, Qt
from shiboken6 import Shiboken

parser = argparse.ArgumentParser()
parser.add_argument("--parented", action="store_true")
parser.add_argument("--loop", choices=["events", "exec"], default="events")
parser.add_argument("--cycles", type=int, default=200)
parser.add_argument("--release", choices=["immediate", "wait", "keep", "poll", "destroyed"], default="immediate")
parser.add_argument("--cleanup-delay-ms", type=int, default=0)
args = parser.parse_args()
app = QCoreApplication([])


class Worker(QObject):
    finished = Signal(object)

    @Slot()
    def run(self):
        self.finished.emit({"fixture": True})


class Controller(QObject):
    def __init__(self):
        super().__init__()
        self.cache_thread = None
        self.cache_worker = None
        self.completed = 0
        self.received = 0
        self.destroyed_threads = 0
        self.destroyed_workers = 0
        self.affinity_failures = 0
        self.python_owned_thread = []
        self.retained = []
        self.poll_retries = 0

    def start(self):
        self.cache_thread = QThread(self) if args.parented else QThread()
        self.cache_worker = Worker()
        self.cache_worker.moveToThread(self.cache_thread)
        self.cache_thread.started.connect(self.cache_worker.run)
        self.cache_worker.finished.connect(self.cache_finished)
        self.cache_worker.finished.connect(self.cache_thread.quit)
        self.cache_thread.finished.connect(self.cache_worker.deleteLater)
        if args.release != "poll":
            self.cache_thread.finished.connect(self.cache_thread.deleteLater)
        if args.release == "destroyed":
            self.cache_thread.destroyed.connect(self.cache_thread_done)
        else:
            self.cache_thread.finished.connect(self.cache_thread_done)
        self.cache_thread.destroyed.connect(self.thread_destroyed)
        self.cache_worker.destroyed.connect(self.worker_destroyed)
        if args.cleanup_delay_ms:
            self.cache_worker.destroyed.connect(lambda: time.sleep(args.cleanup_delay_ms / 1000), Qt.ConnectionType.DirectConnection)
        self.python_owned_thread.append(Shiboken.ownedByPython(self.cache_thread))
        self.cache_thread.start()

    @Slot(object)
    def cache_finished(self, data):
        assert data == {"fixture": True}
        self.received += 1

    # Deliberately mirrors GolfHub's undecorated bound method.
    def cache_thread_done(self):
        self.affinity_failures += int(QThread.currentThread() != self.thread())
        if args.release == "wait":
            assert self.cache_thread.wait(1000), "Finished thread did not complete native cleanup in one second"
        elif args.release == "keep":
            self.retained.append((self.cache_thread, self.cache_worker))
        elif args.release == "poll":
            if not self.cache_thread.wait(0):
                self.poll_retries += 1
                QTimer.singleShot(1, self.cache_thread_done)
                return
            self.cache_thread.deleteLater()
        self.cache_thread = None
        self.cache_worker = None
        self.completed += 1
        if self.completed < args.cycles:
            self.start()

    @Slot()
    def thread_destroyed(self):
        self.destroyed_threads += 1

    @Slot()
    def worker_destroyed(self):
        self.destroyed_workers += 1


control = Controller()
control.start()
deadline = time.monotonic() + 15


def all_done():
    return control.completed == args.cycles and control.destroyed_threads == args.cycles and control.destroyed_workers == args.cycles


if args.loop == "events":
    while not all_done() and time.monotonic() < deadline:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
else:
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: app.quit() if all_done() or time.monotonic() >= deadline else None)
    timer.start()
    app.exec()

result = {
    "pyside6": __version__, "parented": args.parented, "loop": args.loop, "release": args.release,
    "requested": args.cycles, "completed": control.completed, "received": control.received,
    "destroyed_threads": control.destroyed_threads, "destroyed_workers": control.destroyed_workers,
    "affinity_failures": control.affinity_failures,
    "thread_python_ownership_values": sorted(set(control.python_owned_thread)),
    "poll_retries": control.poll_retries, "cleanup_delay_ms": args.cleanup_delay_ms,
    "all_completed_and_destroyed": all_done(),
}
print(json.dumps(result), flush=True)
assert all_done(), result
assert control.received == args.cycles and not control.affinity_failures, result
control.retained.clear()
control.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
