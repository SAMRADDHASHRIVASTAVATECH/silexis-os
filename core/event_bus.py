"""
Central Event Bus — all components emit events here.
The GUI subscribes to receive live updates.
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class Severity(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class SystemEvent:
    timestamp: float
    component: str
    description: str
    severity: Severity = Severity.INFO
    module_id: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def formatted_time(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S.%f")[:-3]


class EventBus:
    """Singleton event bus shared across all components."""

    _instance: Optional["EventBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: List[Callable] = []
            cls._instance._loop: Optional[asyncio.AbstractEventLoop] = None
        return cls._instance

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def subscribe(self, callback: Callable):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        self._subscribers = [s for s in self._subscribers if s != callback]

    def emit(
        self,
        component: str,
        description: str,
        severity: Severity = Severity.INFO,
        module_id: Optional[str] = None,
        **extra,
    ):
        event = SystemEvent(
            timestamp=time.time(),
            component=component,
            description=description,
            severity=severity,
            module_id=module_id,
            extra=extra,
        )
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:
                pass
        return event


# Global singleton
bus = EventBus()
