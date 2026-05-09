"""
Intent Manager — reads capability data from the database and builds
the operational knowledge structures the Intent Router needs.
Maintains a live capability knowledge base that refreshes whenever
WatchDog reports changes.
"""
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus

DATABASE_ROOT = Path("DATABASE")


class IntentManager:
    """
    Builds and maintains capability-to-action mappings.
    Notifies the Intent Router whenever mappings change.
    """

    _instance: Optional["IntentManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._knowledge_base: Dict[str, Any] = {}
            cls._instance._intent_table: Dict[str, Any] = {}
            cls._instance._router_callbacks: List[Callable] = []
            cls._instance._ambiguous: List[str] = []
        return cls._instance

    def add_router_callback(self, cb: Callable):
        self._router_callbacks.append(cb)

    def _notify_router(self):
        for cb in self._router_callbacks:
            try:
                cb(self._intent_table, self._knowledge_base)
            except Exception as e:
                bus.emit("INTENT MANAGER", f"❌  Router notification error: {e}", Severity.ERROR)

    def load_from_database(self, module_id: str):
        """Read capability and routing data for a module from DATABASE/."""
        emit = lambda msg, sev=Severity.INFO: bus.emit(
            "INTENT MANAGER", msg, sev, module_id=module_id
        )

        emit("📖  Intent Manager reading capabilities")

        cap_path = DATABASE_ROOT / "modules" / module_id / "capabilities.json"
        routing_path = DATABASE_ROOT / "modules" / module_id / "routing.json"

        if not cap_path.exists():
            emit(f"⚠️   No capabilities file found for {module_id}", Severity.WARNING)
            return

        with open(cap_path, "r") as f:
            cap_data = json.load(f)

        routing_data = {}
        if routing_path.exists():
            with open(routing_path, "r") as f:
                routing_data = json.load(f)

        emit("🗺️   Building capability mappings")

        # Build knowledge base entry
        self._knowledge_base[module_id] = {
            "capabilities": cap_data,
            "routing": routing_data,
            "loaded_at": time.time(),
        }

        # Build intent table entries
        intent_mappings = routing_data.get("intent_mappings", [])
        conflicts = []

        for mapping in intent_mappings:
            if not isinstance(mapping, dict):
                continue
            label = mapping.get("label", mapping.get("intent", ""))
            action = mapping.get("action", mapping.get("handler", ""))
            confidence = mapping.get("confidence", 0.85)

            if not label:
                continue

            if label in self._intent_table:
                # Conflict — keep higher confidence
                existing_conf = self._intent_table[label].get("confidence", 0)
                if confidence > existing_conf:
                    self._intent_table[label] = {
                        "action": action,
                        "module_id": module_id,
                        "confidence": confidence,
                    }
                    conflicts.append(label)
                else:
                    conflicts.append(label)
            else:
                self._intent_table[label] = {
                    "action": action,
                    "module_id": module_id,
                    "confidence": confidence,
                }

        if conflicts:
            self._ambiguous = list(set(self._ambiguous + conflicts))
            emit(f"⚠️   Ambiguous intents detected: {', '.join(conflicts)}", Severity.WARNING)

        emit("✅  Capability mappings built", Severity.SUCCESS)
        self._notify_router()

    def purge_module(self, module_id: str):
        """
        Remove all knowledge base and intent table entries for a module.
        Called when a module is removed.
        """
        self._knowledge_base.pop(module_id, None)
        to_delete = [
            label for label, mapping in self._intent_table.items()
            if mapping.get("module_id") == module_id
        ]
        for label in to_delete:
            del self._intent_table[label]
        if to_delete:
            bus.emit("INTENT MANAGER",
                     f"🗑️   Purged {len(to_delete)} intent mappings for {module_id}",
                     module_id=module_id)
        self._notify_router()

    def on_watchdog_change(self, event_type: str, path: Path, module_id: Optional[str]):
        """Called by WatchDog when DATABASE changes."""
        if module_id and "capabilities" in path.name:
            bus.emit("INTENT MANAGER", f"🔄  Refreshing mappings for {module_id}", module_id=module_id)
            self.load_from_database(module_id)

    def get_intent_table(self) -> Dict[str, Any]:
        return dict(self._intent_table)

    def get_knowledge_base(self) -> Dict[str, Any]:
        return dict(self._knowledge_base)

    def resolve(self, intent_label: str) -> Optional[Dict]:
        """Resolve an intent label to a module action."""
        return self._intent_table.get(intent_label)


intent_manager = IntentManager()

# Wire Intent Manager → Intent Router at import time
def _wire_router():
    from core.intent_router import intent_router
    intent_manager.add_router_callback(intent_router.receive_mappings)

# Deferred wiring to avoid circular import
import threading
threading.Timer(0.01, _wire_router).start()
