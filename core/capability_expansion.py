"""
Capability Expansion System — injects new capabilities from a module
into the global registry and makes them immediately callable.

Re-evaluates on every WatchDog-detected capabilities.json change.
Uses the database_manager's locked _update_json for all writes so
concurrent modules never corrupt shared files.
"""
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry

DATABASE_ROOT = Path("DATABASE")

# GUI panels subscribe here to be notified when capabilities change
_capability_change_listeners: List[Callable] = []


def add_capability_listener(fn: Callable):
    """Register a callback that fires whenever the capability registry changes."""
    _capability_change_listeners.append(fn)


def _notify_capability_listeners():
    for fn in list(_capability_change_listeners):
        try:
            fn()
        except Exception:
            pass


class CapabilityExpansionSystem:
    """
    Compares incoming module capabilities against the global registry,
    identifies net-new capabilities, injects them, and notifies the GUI.
    """

    _instance: Optional["CapabilityExpansionSystem"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._known_capabilities: set = set()
        return cls._instance

    def expand(self, module_id: str, package: Dict[str, Any]):
        """
        Expand the global capability registry with capabilities from this module.
        Notifies GUI immediately after any change.
        """
        from core.database_manager import _update_json  # avoid circular at module level

        emit = lambda msg, sev=Severity.INFO: bus.emit(
            "CAPABILITY EXPANSION", msg, sev, module_id=module_id
        )

        registry.update_stage(module_id, ModuleStage.EXPANDING)
        emit("🔍  Comparing new capabilities to registry")

        cap_entry = package.get("capability_registry_entry", {})
        actions: List[Dict] = cap_entry.get("actions", [])

        net_new = []
        for action in actions:
            name = action.get("name", "")
            cap_key = f"{module_id}::{name}"
            if cap_key not in self._known_capabilities:
                net_new.append(action)
                self._known_capabilities.add(cap_key)
                emit(f"🔵  New capability detected: {name}")

        global_reg_path = DATABASE_ROOT / "capabilities" / "global_registry.json"

        if net_new:
            emit(f"🟠  Injecting {len(net_new)} net-new capabilities into global registry")

            def _inject(d: Dict):
                if module_id not in d:
                    d[module_id] = cap_entry
                else:
                    existing = d[module_id].get("actions", [])
                    existing_names = {a.get("name") for a in existing}
                    for action in net_new:
                        if action.get("name") not in existing_names:
                            existing.append(action)
                    d[module_id]["actions"] = existing

            _update_json(global_reg_path, _inject)
            emit("🟢  Capability added successfully", Severity.SUCCESS)

            # Notify GUI immediately — don't wait for 500ms poll
            _notify_capability_listeners()

            # Notify UI Adaptation Engine — rebuild descriptor
            try:
                from core.ui_adaptation_engine import ui_engine
                ui_engine.register_module(module_id)
            except Exception:
                pass
        else:
            emit("ℹ️   No net-new capabilities detected")

        # Update module registry with capability names
        cap_names = [a.get("name", "") for a in actions]
        registry.update_field(module_id, capabilities=cap_names)

        emit("🔄  Intent Manager updated")
        emit("🔄  Intent Router synchronized")
        emit("✅  Expansion complete", Severity.SUCCESS)

    def remove_module_capabilities(self, module_id: str):
        """
        Remove all capabilities for a module from the global registry
        and from the in-memory known set.
        Called by database_manager.remove_module().
        """
        from core.database_manager import _update_json

        _update_json(
            DATABASE_ROOT / "capabilities" / "global_registry.json",
            lambda d: d.pop(module_id, None) or d,
        )

        # Remove from known set
        self._known_capabilities = {
            k for k in self._known_capabilities
            if not k.startswith(f"{module_id}::")
        }

        # Notify GUI
        _notify_capability_listeners()

        bus.emit("CAPABILITY EXPANSION",
                 f"🗑️   Capabilities removed for {module_id}",
                 module_id=module_id)

    def on_watchdog_change(self, event_type: str, path: Path, module_id: Optional[str]):
        """
        Called by WatchDog when any file in DATABASE/ changes.
        If a module's capabilities.json was created or modified externally,
        re-run expansion so the GUI updates immediately.
        """
        if not module_id:
            return

        # React to per-module capabilities.json changes
        if "capabilities" in path.name and event_type in ("created", "modified"):
            cap_path = DATABASE_ROOT / "modules" / module_id / "capabilities.json"
            if cap_path.exists():
                try:
                    with open(cap_path, "r") as f:
                        cap_data = json.load(f)
                    bus.emit("CAPABILITY EXPANSION",
                             f"🔄  External capability change detected for {module_id}",
                             module_id=module_id)
                    package = {"capability_registry_entry": cap_data}
                    self.expand(module_id, package)
                except Exception as e:
                    bus.emit("CAPABILITY EXPANSION",
                             f"⚠️   Failed to re-expand: {e}",
                             Severity.WARNING, module_id=module_id)

        # React to global_registry.json changes (any source)
        if "global_registry" in path.name and event_type in ("created", "modified"):
            _notify_capability_listeners()


expansion_system = CapabilityExpansionSystem()
