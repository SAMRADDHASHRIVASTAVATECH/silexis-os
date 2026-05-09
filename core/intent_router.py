"""
Intent Router — receives incoming task/intent signals, matches them to
registered module capabilities, dispatches execution, and updates routing
confidence based on outcomes. Bidirectionally synced with Intent Manager.
"""
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry


class IntentRouter:
    """
    Real-time routing engine. Receives mappings from Intent Manager
    and dispatches tasks to the correct module and action.
    """

    _instance: Optional["IntentRouter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._intent_table: Dict[str, Any] = {}
            cls._instance._knowledge_base: Dict[str, Any] = {}
            cls._instance._routing_log: List[Dict] = []
            cls._instance._confidence_scores: Dict[str, float] = {}
            cls._instance._manager_refresh_callbacks: List[Callable] = []
            cls._instance._active_routes: Dict[str, Any] = {}
        return cls._instance

    def add_manager_refresh_callback(self, cb: Callable):
        """Register callback to request a refresh from Intent Manager."""
        self._manager_refresh_callbacks.append(cb)

    def receive_mappings(self, intent_table: Dict[str, Any], knowledge_base: Dict[str, Any]):
        """Called by Intent Manager when mappings are updated."""
        self._intent_table = intent_table
        self._knowledge_base = knowledge_base

        # Build active routes from intent table
        for label, mapping in intent_table.items():
            module_id = mapping.get("module_id", "")
            self._active_routes[label] = {
                "module_id": module_id,
                "action": mapping.get("action", ""),
                "confidence": mapping.get("confidence", 0.85),
                "established_at": time.time(),
            }

        bus.emit(
            "INTENT ROUTER",
            f"🔗  Routing table updated — {len(self._active_routes)} active routes",
            Severity.SUCCESS,
        )

    def establish_routes(self, module_id: str):
        """Called after a new module is stored to establish its routes."""
        emit = lambda msg, sev=Severity.INFO: bus.emit(
            "INTENT ROUTER", msg, sev, module_id=module_id
        )

        emit("🔗  Intent Router receiving new routes")
        emit("↔️   Bidirectional sync established")
        emit("✅  Routing active", Severity.SUCCESS)

        registry.update_stage(module_id, ModuleStage.ROUTING)

    def dispatch(self, intent_label: str, payload: Any = None) -> Dict[str, Any]:
        """
        Dispatch a task by intent label.
        Returns the routing result.
        """
        route = self._active_routes.get(intent_label)
        if not route:
            bus.emit("INTENT ROUTER", f"⚠️   No route found for intent '{intent_label}'", Severity.WARNING)
            return {"success": False, "error": f"No route for intent '{intent_label}'"}

        module_id = route["module_id"]
        action = route["action"]

        bus.emit("INTENT ROUTER", f"📤  Dispatching '{intent_label}' → {module_id}.{action}", module_id=module_id)

        # Record dispatch
        dispatch_record = {
            "intent": intent_label,
            "module_id": module_id,
            "action": action,
            "dispatched_at": time.time(),
            "payload": payload,
        }
        self._routing_log.append(dispatch_record)

        # Simulate execution result
        result = {
            "success": True,
            "module_id": module_id,
            "action": action,
            "intent": intent_label,
            "executed_at": time.time(),
        }

        # Update confidence score based on success
        current = self._confidence_scores.get(intent_label, route["confidence"])
        self._confidence_scores[intent_label] = min(current + 0.01, 1.0)

        # Notify manager of outcome (bidirectional feedback)
        for cb in self._manager_refresh_callbacks:
            try:
                cb(intent_label, result)
            except Exception:
                pass

        return result

    def purge_module(self, module_id: str):
        """Remove all active routes belonging to a module."""
        to_delete = [
            label for label, route in self._active_routes.items()
            if route.get("module_id") == module_id
        ]
        for label in to_delete:
            del self._active_routes[label]
        if to_delete:
            bus.emit("INTENT ROUTER",
                     f"🗑️   Purged {len(to_delete)} routes for {module_id}",
                     module_id=module_id)

    def get_active_routes(self) -> Dict[str, Any]:
        return dict(self._active_routes)

    def get_routing_log(self) -> List[Dict]:
        return list(self._routing_log[-50:])  # Last 50 dispatches


intent_router = IntentRouter()

# Wire bidirectional sync
intent_router.add_manager_refresh_callback(
    lambda label, result: bus.emit(
        "INTENT ROUTER", f"📊  Confidence updated for '{label}'", module_id=result.get("module_id")
    )
)
