"""
WatchDog System — continuously monitors the DATABASE folder and every
subfolder. Detects file system events and notifies downstream components.
Uses watchdog library for real OS-level file system monitoring.
"""
import json
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from core.event_bus import Severity, bus

DATABASE_ROOT = Path("DATABASE")


class DatabaseEventHandler(FileSystemEventHandler):
    """Handles all file system events inside DATABASE/."""

    def __init__(self, callbacks: Dict[str, List[Callable]]):
        super().__init__()
        self._callbacks = callbacks  # event_type -> [callback, ...]
        self._debounce: Dict[str, float] = {}

    def _debounced(self, path: str, window: float = 0.5) -> bool:
        """Return True if this event should be processed (debounce duplicate events)."""
        now = time.time()
        last = self._debounce.get(path, 0)
        if now - last < window:
            return False
        self._debounce[path] = now
        return True

    def _dispatch_event(self, event_type: str, event: FileSystemEvent):
        path = Path(event.src_path)
        if not self._debounced(str(path)):
            return

        # Determine affected module
        module_id = self._extract_module_id(path)

        bus.emit(
            "WATCHDOG",
            f"🔔  {event_type.upper()} detected: {path.name}",
            Severity.INFO,
            module_id=module_id,
            path=str(path),
            event_type=event_type,
        )

        for cb in self._callbacks.get(event_type, []):
            try:
                cb(event_type, path, module_id)
            except Exception as e:
                bus.emit("WATCHDOG", f"❌  Callback error: {e}", Severity.ERROR)

        # Also fire generic "any_change" callbacks
        for cb in self._callbacks.get("any_change", []):
            try:
                cb(event_type, path, module_id)
            except Exception as e:
                bus.emit("WATCHDOG", f"❌  Callback error: {e}", Severity.ERROR)

    def _extract_module_id(self, path: Path) -> Optional[str]:
        """Try to extract module_id from path like DATABASE/modules/{module_id}/..."""
        try:
            parts = path.parts
            if "modules" in parts:
                idx = list(parts).index("modules")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        except Exception:
            pass
        return None

    def on_created(self, event):
        if not event.is_directory:
            self._dispatch_event("created", event)

    def on_modified(self, event):
        if not event.is_directory:
            self._dispatch_event("modified", event)

    def on_deleted(self, event):
        if not event.is_directory:
            self._dispatch_event("deleted", event)

    def on_moved(self, event):
        if not event.is_directory:
            self._dispatch_event("moved", event)


class WatchDogSystem:
    """Manages the watchdog observer and event routing."""

    _instance: Optional["WatchDogSystem"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._observer: Optional[Observer] = None
            cls._instance._callbacks: Dict[str, List[Callable]] = {
                "created": [],
                "modified": [],
                "deleted": [],
                "moved": [],
                "any_change": [],
            }
            cls._instance._running = False
        return cls._instance

    def on(self, event_type: str, callback: Callable):
        """Register a callback for a specific event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def start(self):
        """Start monitoring DATABASE folder."""
        DATABASE_ROOT.mkdir(parents=True, exist_ok=True)

        handler = DatabaseEventHandler(self._callbacks)
        self._observer = Observer()
        self._observer.schedule(handler, str(DATABASE_ROOT), recursive=True)
        self._observer.start()
        self._running = True

        bus.emit("WATCHDOG", "👁️   WatchDog attached to DATABASE folder", Severity.SUCCESS)
        bus.emit("WATCHDOG", "🔔  Change detection active")
        bus.emit("WATCHDOG", "📡  Downstream notification enabled")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self._running = False
        bus.emit("WATCHDOG", "🛑  WatchDog stopped", Severity.WARNING)

    @property
    def is_running(self) -> bool:
        return self._running


watchdog = WatchDogSystem()
