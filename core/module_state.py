"""
Module state definitions and the central state registry.
Supports multiple concurrent modules.
Duplicate guard: same source path cannot be loaded twice simultaneously.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class ModuleStage(str, Enum):
    WAITING    = "WAITING"
    SCANNING   = "SCANNING"
    ANALYZING  = "ANALYZING"
    CONVERTING = "CONVERTING"
    STORING    = "STORING"
    ROUTING    = "ROUTING"
    EXPANDING  = "EXPANDING"
    ACTIVATING = "ACTIVATING"
    ONLINE     = "ONLINE"
    FAILED     = "FAILED"
    STOPPED    = "STOPPED"


STAGE_ICONS = {
    ModuleStage.WAITING:    "⬜",
    ModuleStage.SCANNING:   "🟡",
    ModuleStage.ANALYZING:  "🔵",
    ModuleStage.CONVERTING: "🟠",
    ModuleStage.STORING:    "🟣",
    ModuleStage.ROUTING:    "🔄",
    ModuleStage.EXPANDING:  "🟤",
    ModuleStage.ACTIVATING: "⚡",
    ModuleStage.ONLINE:     "🟢",
    ModuleStage.FAILED:     "🔴",
    ModuleStage.STOPPED:    "⏹️",
}

# Stages that are considered "active" (pipeline in progress or running)
ACTIVE_STAGES = {
    ModuleStage.WAITING,
    ModuleStage.SCANNING,
    ModuleStage.ANALYZING,
    ModuleStage.CONVERTING,
    ModuleStage.STORING,
    ModuleStage.ROUTING,
    ModuleStage.EXPANDING,
    ModuleStage.ACTIVATING,
    ModuleStage.ONLINE,
}


@dataclass
class ModuleRecord:
    module_id:    str
    name:         str
    source_path:  str
    stage:        ModuleStage = ModuleStage.WAITING
    capabilities: List[str]   = field(default_factory=list)
    routes:       List[str]   = field(default_factory=list)
    environment:  Optional[str] = None
    error:        Optional[str] = None
    analyzer_output: dict     = field(default_factory=dict)

    @property
    def stage_icon(self) -> str:
        return STAGE_ICONS.get(self.stage, "❓")

    @property
    def is_active(self) -> bool:
        return self.stage in ACTIVE_STAGES


class ModuleRegistry:
    """
    Multi-module registry.
    Multiple modules can run concurrently.
    Duplicate guard: rejects a new drop if the same source_path is already
    active (WAITING → ONLINE). Stopped/Failed modules can be re-loaded.
    """

    _instance: Optional["ModuleRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._modules: Dict[str, ModuleRecord] = {}
            cls._instance._listeners: List[Callable] = []
        return cls._instance

    # ── Duplicate guard ───────────────────────────────────────────────────

    def is_duplicate(self, source_path: str) -> bool:
        """
        True if a module from this exact path is already active.
        FAILED and STOPPED modules do NOT block re-loading.
        """
        for rec in self._modules.values():
            if rec.source_path == source_path and rec.is_active:
                return True
        return False

    # ── CRUD ──────────────────────────────────────────────────────────────

    def register(self, record: ModuleRecord):
        self._modules[record.module_id] = record
        self._notify()

    def update_stage(self, module_id: str, stage: ModuleStage, error: str = None):
        if module_id in self._modules:
            self._modules[module_id].stage = stage
            if error:
                self._modules[module_id].error = error
            self._notify()

    def update_field(self, module_id: str, **kwargs):
        if module_id in self._modules:
            for k, v in kwargs.items():
                setattr(self._modules[module_id], k, v)
            self._notify()

    def remove(self, module_id: str):
        """Remove a module record entirely (used by management panel)."""
        self._modules.pop(module_id, None)
        self._notify()

    def stop(self, module_id: str):
        """Mark a module as STOPPED."""
        self.update_stage(module_id, ModuleStage.STOPPED)

    def get(self, module_id: str) -> Optional[ModuleRecord]:
        return self._modules.get(module_id)

    def all(self) -> List[ModuleRecord]:
        return list(self._modules.values())

    def active(self) -> List[ModuleRecord]:
        """Return only modules in active stages."""
        return [r for r in self._modules.values() if r.is_active]

    def add_listener(self, fn: Callable):
        self._listeners.append(fn)

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass


registry = ModuleRegistry()
