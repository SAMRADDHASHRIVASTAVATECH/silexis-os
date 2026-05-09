"""
Ecosystem Registry — the living world state of the platform.

Inspired by game engine inventory/world systems:
  • SLOTS      — typed equipment slots each module occupies (like gear slots)
  • SYNERGIES  — cross-module connections that unlock combined behaviors
  • GRAPH      — the full dependency and communication graph
  • CONFLICTS  — detected incompatibilities between modules
  • CATEGORIES — the taxonomy that drives auto-placement

Every module that enters the system is automatically:
  1. Categorized by purpose + capability signature
  2. Placed into the correct slot(s)
  3. Connected to compatible modules via synergy links
  4. Checked for conflicts with existing occupants
  5. Registered in the ecosystem graph

The registry is the single source of truth for "how the ecosystem
is organized right now" — it drives both the orchestration engine
and the adaptive GUI.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ── Slot taxonomy (game inventory slots) ──────────────────────────────────

class SlotType(str, Enum):
    # Processing slots
    TEXT_PROCESSOR    = "text_processor"
    IMAGE_PROCESSOR   = "image_processor"
    DATA_PROCESSOR    = "data_processor"
    AUDIO_PROCESSOR   = "audio_processor"

    # Intelligence slots
    CLASSIFIER        = "classifier"
    GENERATOR         = "generator"
    EMBEDDER          = "embedder"
    REASONER          = "reasoner"

    # Service slots
    API_GATEWAY       = "api_gateway"
    DATA_STORE        = "data_store"
    MESSAGE_BROKER    = "message_broker"
    SCHEDULER         = "scheduler"

    # Infrastructure slots
    MONITOR           = "monitor"
    LOGGER            = "logger"
    AUTHENTICATOR     = "authenticator"
    CACHE             = "cache"

    # Utility slots
    FORMATTER         = "formatter"
    VALIDATOR         = "validator"
    TRANSFORMER       = "transformer"
    UTILITY           = "utility"


SLOT_ICONS = {
    SlotType.TEXT_PROCESSOR:  "🔤",
    SlotType.IMAGE_PROCESSOR: "🖼️",
    SlotType.DATA_PROCESSOR:  "📊",
    SlotType.AUDIO_PROCESSOR: "🎵",
    SlotType.CLASSIFIER:      "🏷️",
    SlotType.GENERATOR:       "✨",
    SlotType.EMBEDDER:        "🔢",
    SlotType.REASONER:        "🧠",
    SlotType.API_GATEWAY:     "🌐",
    SlotType.DATA_STORE:      "🗄️",
    SlotType.MESSAGE_BROKER:  "📨",
    SlotType.SCHEDULER:       "⏰",
    SlotType.MONITOR:         "📡",
    SlotType.LOGGER:          "📋",
    SlotType.AUTHENTICATOR:   "🔐",
    SlotType.CACHE:           "⚡",
    SlotType.FORMATTER:       "📝",
    SlotType.VALIDATOR:       "✅",
    SlotType.TRANSFORMER:     "🔄",
    SlotType.UTILITY:         "🔧",
}

# Purpose + capability keywords → slot assignments
SLOT_ASSIGNMENT_RULES: List[Tuple[List[str], SlotType]] = [
    # Text/NLP
    (["classify", "sentiment", "text", "nlp", "language", "tokenize"], SlotType.TEXT_PROCESSOR),
    (["classify", "categorize", "label", "detect"],                     SlotType.CLASSIFIER),
    (["summarize", "generate", "translate", "write"],                   SlotType.GENERATOR),
    (["embed", "encode", "vector", "embedding"],                        SlotType.EMBEDDER),
    # Vision
    (["image", "vision", "detect", "pixel", "cv"],                      SlotType.IMAGE_PROCESSOR),
    # Data
    (["dataframe", "csv", "etl", "transform", "batch", "pipeline"],     SlotType.DATA_PROCESSOR),
    (["transform", "convert", "reshape", "normalize"],                  SlotType.TRANSFORMER),
    (["validate", "schema", "check", "verify"],                         SlotType.VALIDATOR),
    (["format", "parse", "serialize", "encode"],                        SlotType.FORMATTER),
    # Services
    (["api", "endpoint", "rest", "http", "route", "fastapi"],           SlotType.API_GATEWAY),
    (["sql", "postgres", "mongo", "redis", "query", "store"],           SlotType.DATA_STORE),
    (["kafka", "rabbitmq", "pubsub", "stream", "event", "message"],     SlotType.MESSAGE_BROKER),
    (["schedule", "cron", "task", "trigger", "automate"],               SlotType.SCHEDULER),
    # Infrastructure
    (["monitor", "metric", "health", "alert", "trace"],                 SlotType.MONITOR),
    (["log", "audit", "record", "history"],                             SlotType.LOGGER),
    (["auth", "token", "permission", "access", "security"],             SlotType.AUTHENTICATOR),
    (["cache", "memory", "buffer", "store", "fast"],                    SlotType.CACHE),
    # ML
    (["model", "train", "predict", "inference", "torch", "tensorflow"], SlotType.REASONER),
]

# Synergy rules: if module A has slot X and module B has slot Y → synergy
SYNERGY_RULES: List[Tuple[SlotType, SlotType, str, str]] = [
    (SlotType.TEXT_PROCESSOR, SlotType.CLASSIFIER,
     "nlp_pipeline", "Text → Classification pipeline"),
    (SlotType.TEXT_PROCESSOR, SlotType.GENERATOR,
     "text_augmentation", "Text processing + generation"),
    (SlotType.TEXT_PROCESSOR, SlotType.EMBEDDER,
     "semantic_search", "Text → Embedding pipeline"),
    (SlotType.DATA_PROCESSOR, SlotType.CLASSIFIER,
     "data_classification", "Data processing + classification"),
    (SlotType.DATA_PROCESSOR, SlotType.DATA_STORE,
     "etl_pipeline", "ETL → Storage pipeline"),
    (SlotType.API_GATEWAY, SlotType.DATA_STORE,
     "api_persistence", "API + Database backend"),
    (SlotType.API_GATEWAY, SlotType.CLASSIFIER,
     "smart_api", "API with intelligent classification"),
    (SlotType.MONITOR, SlotType.LOGGER,
     "observability", "Full observability stack"),
    (SlotType.MONITOR, SlotType.MESSAGE_BROKER,
     "event_monitoring", "Event-driven monitoring"),
    (SlotType.REASONER, SlotType.API_GATEWAY,
     "ml_service", "ML model served via API"),
    (SlotType.REASONER, SlotType.DATA_PROCESSOR,
     "ml_pipeline", "ML with data preprocessing"),
    (SlotType.IMAGE_PROCESSOR, SlotType.CLASSIFIER,
     "vision_pipeline", "Vision + Classification pipeline"),
    (SlotType.SCHEDULER, SlotType.DATA_PROCESSOR,
     "batch_automation", "Scheduled batch processing"),
    (SlotType.CACHE, SlotType.API_GATEWAY,
     "cached_api", "Cached API responses"),
    (SlotType.AUTHENTICATOR, SlotType.API_GATEWAY,
     "secure_api", "Authenticated API gateway"),
]


@dataclass
class EcosystemSlot:
    slot_type:  SlotType
    module_id:  str
    module_name: str
    purpose:    str
    assigned_at: float = field(default_factory=time.time)
    confidence: float = 1.0


@dataclass
class Synergy:
    synergy_id:   str
    module_a:     str
    module_b:     str
    slot_a:       SlotType
    slot_b:       SlotType
    name:         str
    description:  str
    strength:     float = 1.0
    discovered_at: float = field(default_factory=time.time)


@dataclass
class EcosystemNode:
    module_id:   str
    module_name: str
    purpose:     str
    slots:       List[SlotType]
    capabilities: List[str]
    environment: str
    connections: List[str]   # module_ids this node connects to
    added_at:    float = field(default_factory=time.time)


class EcosystemRegistry:
    """
    The living world state. Tracks slots, synergies, the ecosystem graph,
    and fires callbacks whenever the world changes.
    """

    _instance: Optional["EcosystemRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # slot_type → list of EcosystemSlot (multiple modules can share a slot type)
            cls._instance._slots: Dict[SlotType, List[EcosystemSlot]] = {
                st: [] for st in SlotType
            }
            # synergy_id → Synergy
            cls._instance._synergies: Dict[str, Synergy] = {}
            # module_id → EcosystemNode
            cls._instance._nodes: Dict[str, EcosystemNode] = {}
            # Change callbacks
            cls._instance._change_callbacks: List[Callable] = []
        return cls._instance

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_change(self, fn: Callable):
        self._change_callbacks.append(fn)

    def _notify(self):
        for fn in list(self._change_callbacks):
            try:
                fn()
            except Exception:
                pass

    # ── Slot assignment ───────────────────────────────────────────────────

    def assign_slots(self, module_id: str, module_name: str,
                     purpose: str, capabilities: List[str]) -> List[SlotType]:
        """
        Auto-assign a module to its correct slot(s) based on purpose
        and capability keywords. Returns the list of assigned slots.
        """
        corpus = f"{purpose} {' '.join(capabilities)}".lower()
        assigned: List[SlotType] = []
        scores: Dict[SlotType, int] = {}

        for keywords, slot_type in SLOT_ASSIGNMENT_RULES:
            score = sum(1 for kw in keywords if kw in corpus)
            if score > 0:
                scores[slot_type] = scores.get(slot_type, 0) + score

        if scores:
            # Take top 3 slots by score
            top_slots = sorted(scores, key=scores.get, reverse=True)[:3]
            for slot_type in top_slots:
                if scores[slot_type] > 0:
                    slot = EcosystemSlot(
                        slot_type=slot_type,
                        module_id=module_id,
                        module_name=module_name,
                        purpose=purpose,
                        confidence=min(scores[slot_type] / 5.0, 1.0),
                    )
                    self._slots[slot_type].append(slot)
                    assigned.append(slot_type)
        else:
            # Fallback to utility slot
            slot = EcosystemSlot(
                slot_type=SlotType.UTILITY,
                module_id=module_id,
                module_name=module_name,
                purpose=purpose,
                confidence=0.5,
            )
            self._slots[SlotType.UTILITY].append(slot)
            assigned.append(SlotType.UTILITY)

        return assigned

    def release_slots(self, module_id: str):
        """Remove a module from all slots."""
        for slot_type in SlotType:
            self._slots[slot_type] = [
                s for s in self._slots[slot_type]
                if s.module_id != module_id
            ]

    # ── Node management ───────────────────────────────────────────────────

    def add_node(self, module_id: str, module_name: str, purpose: str,
                 slots: List[SlotType], capabilities: List[str],
                 environment: str) -> EcosystemNode:
        node = EcosystemNode(
            module_id=module_id,
            module_name=module_name,
            purpose=purpose,
            slots=slots,
            capabilities=capabilities,
            environment=environment,
            connections=[],
        )
        self._nodes[module_id] = node
        return node

    def remove_node(self, module_id: str):
        self._nodes.pop(module_id, None)
        # Remove from other nodes' connections
        for node in self._nodes.values():
            node.connections = [c for c in node.connections if c != module_id]

    # ── Synergy detection ─────────────────────────────────────────────────

    def detect_synergies(self, new_module_id: str) -> List[Synergy]:
        """
        Check the new module against all existing modules for synergies.
        Returns list of newly discovered synergies.
        """
        new_node = self._nodes.get(new_module_id)
        if not new_node:
            return []

        new_slots = set(new_node.slots)
        discovered = []

        for existing_id, existing_node in self._nodes.items():
            if existing_id == new_module_id:
                continue

            existing_slots = set(existing_node.slots)

            for slot_a, slot_b, syn_id, syn_desc in SYNERGY_RULES:
                # Check both directions
                if ((slot_a in new_slots and slot_b in existing_slots) or
                        (slot_b in new_slots and slot_a in existing_slots)):

                    full_id = f"{min(new_module_id, existing_id)}_{max(new_module_id, existing_id)}_{syn_id}"
                    if full_id not in self._synergies:
                        synergy = Synergy(
                            synergy_id=full_id,
                            module_a=new_module_id,
                            module_b=existing_id,
                            slot_a=slot_a,
                            slot_b=slot_b,
                            name=syn_id,
                            description=syn_desc,
                            strength=0.8,
                        )
                        self._synergies[full_id] = synergy
                        discovered.append(synergy)

                        # Wire connections in graph
                        if existing_id not in new_node.connections:
                            new_node.connections.append(existing_id)
                        if new_module_id not in existing_node.connections:
                            existing_node.connections.append(new_module_id)

        return discovered

    def remove_synergies(self, module_id: str) -> List[str]:
        """Remove all synergies involving a module. Returns removed IDs."""
        to_remove = [
            sid for sid, syn in self._synergies.items()
            if syn.module_a == module_id or syn.module_b == module_id
        ]
        for sid in to_remove:
            del self._synergies[sid]
        return to_remove

    # ── Queries ───────────────────────────────────────────────────────────

    def get_slots_for_module(self, module_id: str) -> List[SlotType]:
        result = []
        for slot_type, slots in self._slots.items():
            for s in slots:
                if s.module_id == module_id:
                    result.append(slot_type)
        return result

    def get_modules_in_slot(self, slot_type: SlotType) -> List[EcosystemSlot]:
        return list(self._slots[slot_type])

    def get_occupied_slots(self) -> Dict[SlotType, List[EcosystemSlot]]:
        return {st: slots for st, slots in self._slots.items() if slots}

    def get_synergies_for_module(self, module_id: str) -> List[Synergy]:
        return [s for s in self._synergies.values()
                if s.module_a == module_id or s.module_b == module_id]

    def get_all_synergies(self) -> List[Synergy]:
        return list(self._synergies.values())

    def get_node(self, module_id: str) -> Optional[EcosystemNode]:
        return self._nodes.get(module_id)

    def get_all_nodes(self) -> Dict[str, EcosystemNode]:
        return dict(self._nodes)

    def get_ecosystem_stats(self) -> Dict[str, Any]:
        occupied = self.get_occupied_slots()
        return {
            "total_modules":    len(self._nodes),
            "occupied_slots":   len(occupied),
            "total_slots":      len(SlotType),
            "total_synergies":  len(self._synergies),
            "total_connections": sum(len(n.connections) for n in self._nodes.values()) // 2,
            "slot_coverage":    f"{len(occupied)}/{len(SlotType)}",
        }


ecosystem = EcosystemRegistry()
