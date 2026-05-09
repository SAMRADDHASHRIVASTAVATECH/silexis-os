"""
Orchestration Engine — the game-engine brain of the platform.

This is the central intelligence that makes the system self-organizing.
It operates like a game engine's world manager:

  INTAKE      — receives a new module, reads its full profile
  CLASSIFY    — determines its type, purpose, and slot assignments
  PLACE       — inserts it into the correct ecosystem slots
  CONNECT     — discovers synergies with existing modules
  CONFIGURE   — sets up communication routes and workflows
  BROADCAST   — notifies all systems of the new world state
  ADAPT       — triggers UI adaptation for the new configuration

When a module is removed:
  DISCONNECT  — severs all synergy links
  VACATE      — releases its slots
  REBALANCE   — checks if remaining modules need re-routing
  BROADCAST   — notifies all systems of the updated world state

The engine runs continuously, maintaining ecosystem health and
reorganizing the platform as it evolves.
"""
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.ecosystem_registry import (
    EcosystemRegistry, SlotType, Synergy, SLOT_ICONS, ecosystem
)
from core.event_bus import Severity, bus
from core.module_state import registry as module_registry

DATABASE_ROOT = Path("DATABASE")


class OrchestrationEngine:
    """
    The self-organizing intelligence layer.
    Coordinates the full lifecycle of every module in the ecosystem.
    """

    _instance: Optional["OrchestrationEngine"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._intake_callbacks:  List[Callable[[str, Dict], None]] = []
            cls._instance._synergy_callbacks: List[Callable[[List[Synergy]], None]] = []
            cls._instance._remove_callbacks:  List[Callable[[str], None]] = []
            cls._instance._rebalance_callbacks: List[Callable[[], None]] = []
        return cls._instance

    # ── Subscription API ──────────────────────────────────────────────────

    def on_intake(self, fn: Callable[[str, Dict], None]):
        """Fired when a module is fully placed into the ecosystem."""
        self._intake_callbacks.append(fn)

    def on_synergy(self, fn: Callable[[List[Synergy]], None]):
        """Fired when new synergies are discovered."""
        self._synergy_callbacks.append(fn)

    def on_remove(self, fn: Callable[[str], None]):
        """Fired when a module is removed from the ecosystem."""
        self._remove_callbacks.append(fn)

    def on_rebalance(self, fn: Callable[[], None]):
        """Fired when the ecosystem rebalances after a change."""
        self._rebalance_callbacks.append(fn)

    # ── INTAKE ────────────────────────────────────────────────────────────

    def intake_module(self, module_id: str, descriptor: Dict[str, Any]):
        """
        Full intake pipeline for a newly ONLINE module.
        Places it into the ecosystem and discovers synergies.
        """
        name         = descriptor.get("name", module_id)
        purpose      = descriptor.get("purpose", "utility")
        capabilities = [c["name"] for c in descriptor.get("capabilities", [])]
        environment  = descriptor.get("environment", "cpu_env")

        bus.emit("ORCHESTRATION",
                 f"🎮  Intake: {name} [{purpose}] — placing into ecosystem",
                 Severity.INFO, module_id=module_id)

        # ── CLASSIFY + PLACE ──────────────────────────────────────────────
        slots = ecosystem.assign_slots(module_id, name, purpose, capabilities)
        slot_names = [SLOT_ICONS.get(s, "?") + " " + s.value for s in slots]
        bus.emit("ORCHESTRATION",
                 f"🎯  Slots assigned: {', '.join(slot_names)}",
                 module_id=module_id)

        # ── ADD TO GRAPH ──────────────────────────────────────────────────
        node = ecosystem.add_node(
            module_id=module_id,
            module_name=name,
            purpose=purpose,
            slots=slots,
            capabilities=capabilities,
            environment=environment,
        )

        # ── CONNECT — discover synergies ──────────────────────────────────
        synergies = ecosystem.detect_synergies(module_id)
        if synergies:
            for syn in synergies:
                other_name = ecosystem.get_node(
                    syn.module_b if syn.module_a == module_id else syn.module_a
                )
                other = other_name.module_name if other_name else "?"
                bus.emit("ORCHESTRATION",
                         f"⚡  Synergy discovered: {syn.description} "
                         f"({name} ↔ {other})",
                         Severity.SUCCESS, module_id=module_id)
            for fn in list(self._synergy_callbacks):
                try:
                    fn(synergies)
                except Exception:
                    pass
        else:
            bus.emit("ORCHESTRATION",
                     f"ℹ️   No synergies yet — ecosystem has {len(ecosystem.get_all_nodes())} modules",
                     module_id=module_id)

        # ── CONFIGURE — update routing based on ecosystem state ───────────
        self._configure_routes(module_id, slots, synergies)

        # ── BUILD PLACEMENT REPORT ────────────────────────────────────────
        placement = {
            "module_id":   module_id,
            "name":        name,
            "purpose":     purpose,
            "slots":       [s.value for s in slots],
            "slot_icons":  [SLOT_ICONS.get(s, "?") for s in slots],
            "synergies":   [{"id": s.synergy_id, "name": s.name,
                             "description": s.description,
                             "partner": s.module_b if s.module_a == module_id else s.module_a}
                            for s in synergies],
            "connections": node.connections,
            "stats":       ecosystem.get_ecosystem_stats(),
        }

        # ── BROADCAST ─────────────────────────────────────────────────────
        stats = ecosystem.get_ecosystem_stats()
        bus.emit("ORCHESTRATION",
                 f"🌍  Ecosystem: {stats['total_modules']} modules · "
                 f"{stats['occupied_slots']} slots · "
                 f"{stats['total_synergies']} synergies",
                 Severity.SUCCESS, module_id=module_id)

        for fn in list(self._intake_callbacks):
            try:
                fn(module_id, placement)
            except Exception:
                pass

        ecosystem._notify()
        return placement

    # ── REMOVE ────────────────────────────────────────────────────────────

    def remove_module(self, module_id: str):
        """
        Remove a module from the ecosystem:
        disconnect synergies, vacate slots, rebalance.
        """
        node = ecosystem.get_node(module_id)
        name = node.module_name if node else module_id

        bus.emit("ORCHESTRATION",
                 f"🗑️   Removing {name} from ecosystem",
                 module_id=module_id)

        # DISCONNECT
        removed_synergies = ecosystem.remove_synergies(module_id)
        if removed_synergies:
            bus.emit("ORCHESTRATION",
                     f"🔌  Disconnected {len(removed_synergies)} synergy links",
                     module_id=module_id)

        # VACATE
        ecosystem.release_slots(module_id)
        ecosystem.remove_node(module_id)

        # REBALANCE
        self._rebalance()

        stats = ecosystem.get_ecosystem_stats()
        bus.emit("ORCHESTRATION",
                 f"🌍  Ecosystem rebalanced: {stats['total_modules']} modules · "
                 f"{stats['occupied_slots']} slots · "
                 f"{stats['total_synergies']} synergies",
                 module_id=module_id)

        for fn in list(self._remove_callbacks):
            try:
                fn(module_id)
            except Exception:
                pass

        ecosystem._notify()

    # ── CONFIGURE ─────────────────────────────────────────────────────────

    def _configure_routes(self, module_id: str, slots: List[SlotType],
                           synergies: List[Synergy]):
        """
        Update routing configuration based on ecosystem placement.
        Synergy links become preferred routing paths.
        """
        if not synergies:
            return

        try:
            from core.intent_router import intent_router
            from core.database_manager import _update_json

            # Write synergy routing hints to DATABASE
            synergy_routes = {}
            for syn in synergies:
                partner_id = syn.module_b if syn.module_a == module_id else syn.module_a
                synergy_routes[syn.name] = {
                    "module_a":    syn.module_a,
                    "module_b":    syn.module_b,
                    "description": syn.description,
                    "strength":    syn.strength,
                }

            _update_json(
                DATABASE_ROOT / "routes" / "synergy_routes.json",
                lambda d: d.update({module_id: synergy_routes}),
            )
        except Exception:
            pass

    # ── REBALANCE ─────────────────────────────────────────────────────────

    def _rebalance(self):
        """
        After a module is removed, check if remaining modules need
        re-routing or re-categorization.
        """
        for fn in list(self._rebalance_callbacks):
            try:
                fn()
            except Exception:
                pass

    # ── QUERY ─────────────────────────────────────────────────────────────

    def get_placement(self, module_id: str) -> Optional[Dict[str, Any]]:
        node = ecosystem.get_node(module_id)
        if not node:
            return None
        synergies = ecosystem.get_synergies_for_module(module_id)
        return {
            "module_id":   module_id,
            "name":        node.module_name,
            "slots":       [s.value for s in node.slots],
            "slot_icons":  [SLOT_ICONS.get(s, "?") for s in node.slots],
            "synergies":   [s.description for s in synergies],
            "connections": node.connections,
        }


orchestration_engine = OrchestrationEngine()
