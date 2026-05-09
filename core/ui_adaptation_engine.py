"""
UI Adaptation Engine — the intelligence layer that makes the GUI evolve
automatically whenever modules, capabilities, or tools change.

Responsibilities:
  1. Track every ONLINE module and its full capability/metadata profile
  2. Generate a UI descriptor for each module (what panels, controls,
     workflows, and interactions it should expose)
  3. Notify the GUI to build, update, or destroy panels in real time
  4. Keep all descriptors synchronized with DATABASE state

The engine is the single source of truth for "what the GUI should look like
right now given the current set of active modules."

UI Descriptor schema per module:
  {
    "module_id":   str,
    "name":        str,
    "purpose":     str,          # nlp / api_service / machine_learning / etc.
    "version":     str,
    "environment": str,
    "capabilities": [
      {
        "name":        str,
        "description": str,
        "inputs":      [str],
        "outputs":     [str],
        "widget_type": str,      # "text_input" | "file_input" | "slider" |
                                 # "toggle" | "dropdown" | "trigger"
        "intent_label": str,     # maps to intent router
      }
    ],
    "workflows": [str],          # suggested workflow names for this purpose
    "dashboard_color": str,      # accent color derived from purpose
    "tags": [str],
  }
"""
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry

DATABASE_ROOT = Path("DATABASE")

# ── Purpose → UI profile mapping ──────────────────────────────────────────

PURPOSE_PROFILES = {
    "nlp": {
        "color":     "#58a6ff",
        "icon":      "🔤",
        "workflows": ["Text Classification", "Sentiment Analysis",
                      "Entity Extraction", "Summarization", "Tokenization"],
    },
    "machine_learning": {
        "color":     "#bc8cff",
        "icon":      "🧠",
        "workflows": ["Model Inference", "Batch Prediction",
                      "Feature Extraction", "Embedding Generation"],
    },
    "api_service": {
        "color":     "#3fb950",
        "icon":      "🌐",
        "workflows": ["Endpoint Call", "Health Check",
                      "Request Builder", "Response Inspector"],
    },
    "data_processing": {
        "color":     "#e3b341",
        "icon":      "📊",
        "workflows": ["Data Transform", "Batch Process",
                      "Pipeline Run", "Schema Validate"],
    },
    "computer_vision": {
        "color":     "#f0883e",
        "icon":      "👁️",
        "workflows": ["Image Classify", "Object Detect",
                      "Feature Extract", "Batch Analyze"],
    },
    "database": {
        "color":     "#d29922",
        "icon":      "🗄️",
        "workflows": ["Query Execute", "Schema Inspect",
                      "Migration Run", "Connection Test"],
    },
    "automation": {
        "color":     "#a5d6ff",
        "icon":      "⚙️",
        "workflows": ["Task Schedule", "Workflow Trigger",
                      "Pipeline Execute", "Status Check"],
    },
    "monitoring": {
        "color":     "#f85149",
        "icon":      "📡",
        "workflows": ["Health Check", "Metric Collect",
                      "Alert Configure", "Log Stream"],
    },
    "communication": {
        "color":     "#79c0ff",
        "icon":      "📨",
        "workflows": ["Message Publish", "Topic Subscribe",
                      "Stream Monitor", "Event Replay"],
    },
    "utility": {
        "color":     "#8b949e",
        "icon":      "🔧",
        "workflows": ["Utility Run", "Format Convert",
                      "Validate Input", "Parse Data"],
    },
}

DEFAULT_PROFILE = {
    "color":     "#388bfd",
    "icon":      "📦",
    "workflows": ["Execute", "Configure", "Inspect", "Test"],
}

# ── Input type → widget type mapping ──────────────────────────────────────

def _infer_widget(input_spec: str, action_name: str) -> str:
    """Infer the best widget type from an input type string and action name."""
    spec = input_spec.lower()
    name = action_name.lower()

    if "file" in spec or "path" in spec or "image" in spec:
        return "file_input"
    if "bool" in spec or "flag" in spec or "enable" in name or "toggle" in name:
        return "toggle"
    if "int" in spec or "float" in spec or "num" in spec or "length" in spec or "size" in spec:
        return "slider"
    if "list" in spec or "choice" in spec or "option" in spec or "mode" in name:
        return "dropdown"
    if not input_spec or input_spec == "none":
        return "trigger"
    return "text_input"


# ── UI Adaptation Engine ───────────────────────────────────────────────────

class UIAdaptationEngine:
    """
    Singleton engine that maintains UI descriptors for all active modules
    and notifies the GUI whenever the descriptor set changes.
    """

    _instance: Optional["UIAdaptationEngine"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # module_id → UI descriptor dict
            cls._instance._descriptors: Dict[str, Dict[str, Any]] = {}
            # Callbacks fired when descriptors change
            cls._instance._add_callbacks:    List[Callable[[str, Dict], None]] = []
            cls._instance._update_callbacks: List[Callable[[str, Dict], None]] = []
            cls._instance._remove_callbacks: List[Callable[[str], None]] = []
        return cls._instance

    # ── Subscription API ──────────────────────────────────────────────────

    def on_module_added(self, fn: Callable[[str, Dict], None]):
        """Called when a new module descriptor is created (module goes ONLINE)."""
        self._add_callbacks.append(fn)

    def on_module_updated(self, fn: Callable[[str, Dict], None]):
        """Called when an existing module's descriptor changes (capability update)."""
        self._update_callbacks.append(fn)

    def on_module_removed(self, fn: Callable[[str], None]):
        """Called when a module descriptor is destroyed (module removed)."""
        self._remove_callbacks.append(fn)

    # ── Descriptor management ─────────────────────────────────────────────

    def build_descriptor(self, module_id: str) -> Optional[Dict[str, Any]]:
        """
        Build a full UI descriptor for a module by reading its DATABASE files.
        Returns None if the module data is not available.
        """
        cap_path  = DATABASE_ROOT / "modules" / module_id / "capabilities.json"
        pkg_path  = DATABASE_ROOT / "modules" / module_id / "extension.pkg"
        anal_path = DATABASE_ROOT / "modules" / module_id / "analyzer_output.json"

        if not cap_path.exists():
            return None

        try:
            cap_data  = json.loads(cap_path.read_text(encoding="utf-8"))
            pkg_data  = json.loads(pkg_path.read_text(encoding="utf-8")) if pkg_path.exists() else {}
            anal_data = json.loads(anal_path.read_text(encoding="utf-8")) if anal_path.exists() else {}
        except Exception:
            return None

        # Module identity
        name    = cap_data.get("module_name", module_id)
        version = cap_data.get("version", "1.0.0")
        purpose = cap_data.get("purpose", anal_data.get("purpose", "utility"))

        # Environment from registry
        rec = registry.get(module_id)
        environment = rec.environment if rec else "unknown"

        # Tags from extension package metadata
        env_spec = pkg_data.get("environment_spec", {})
        tags = []
        if purpose:
            tags.append(purpose)
        if environment:
            tags.append(environment)

        # Purpose profile
        profile = PURPOSE_PROFILES.get(purpose, DEFAULT_PROFILE)

        # Build capability descriptors with widget inference
        raw_actions = cap_data.get("actions", [])
        capabilities = []

        # Load intent mappings to find intent labels per action
        routing_path = DATABASE_ROOT / "modules" / module_id / "routing.json"
        intent_map: Dict[str, str] = {}  # action_name → intent_label
        if routing_path.exists():
            try:
                routing = json.loads(routing_path.read_text(encoding="utf-8"))
                for mapping in routing.get("intent_mappings", []):
                    if isinstance(mapping, dict):
                        label  = mapping.get("label", "")
                        action = mapping.get("action", "")
                        if label and action:
                            intent_map[action] = label
            except Exception:
                pass

        for action in raw_actions:
            action_name = action.get("name", "")
            inputs      = action.get("inputs", [])
            outputs     = action.get("outputs", [])
            description = action.get("description", "")

            # Infer widget from first input type
            first_input = inputs[0] if inputs else ""
            widget_type = _infer_widget(first_input, action_name)

            capabilities.append({
                "name":         action_name,
                "description":  description,
                "inputs":       inputs,
                "outputs":      outputs,
                "widget_type":  widget_type,
                "intent_label": intent_map.get(action_name, action_name),
            })

        descriptor = {
            "module_id":       module_id,
            "name":            name,
            "version":         version,
            "purpose":         purpose,
            "environment":     environment,
            "capabilities":    capabilities,
            "workflows":       profile["workflows"],
            "dashboard_color": profile["color"],
            "dashboard_icon":  profile["icon"],
            "tags":            tags,
            "built_at":        time.time(),
        }

        # Enrich with ecosystem placement if available
        try:
            from core.ecosystem_registry import ecosystem, SLOT_ICONS
            slots = ecosystem.get_slots_for_module(module_id)
            if slots:
                descriptor["slots"]      = [s.value for s in slots]
                descriptor["slot_icons"] = [SLOT_ICONS.get(s, "?") for s in slots]
                synergies = ecosystem.get_synergies_for_module(module_id)
                descriptor["synergies"]  = [s.description for s in synergies]
                descriptor["connections"] = []
                node = ecosystem.get_node(module_id)
                if node:
                    descriptor["connections"] = node.connections
        except Exception:
            pass

        return descriptor

    def register_module(self, module_id: str):
        """
        Build and register a descriptor for a newly ONLINE module.
        Fires on_module_added callbacks.
        """
        descriptor = self.build_descriptor(module_id)
        if not descriptor:
            bus.emit("UI ADAPTATION",
                     f"⚠️   Could not build descriptor for {module_id}",
                     Severity.WARNING, module_id=module_id)
            return

        is_update = module_id in self._descriptors
        self._descriptors[module_id] = descriptor

        name    = descriptor["name"]
        purpose = descriptor["purpose"]
        n_caps  = len(descriptor["capabilities"])

        if is_update:
            bus.emit("UI ADAPTATION",
                     f"🔄  UI descriptor updated: {name} [{purpose}] {n_caps} caps",
                     Severity.SUCCESS, module_id=module_id)
            for fn in list(self._update_callbacks):
                try:
                    fn(module_id, descriptor)
                except Exception:
                    pass
        else:
            bus.emit("UI ADAPTATION",
                     f"✨  New UI descriptor: {name} [{purpose}] {n_caps} caps → building dashboard",
                     Severity.SUCCESS, module_id=module_id)
            for fn in list(self._add_callbacks):
                try:
                    fn(module_id, descriptor)
                except Exception:
                    pass

    def unregister_module(self, module_id: str):
        """
        Remove a module's descriptor and fire on_module_removed callbacks.
        """
        if module_id not in self._descriptors:
            return

        name = self._descriptors[module_id].get("name", module_id)
        del self._descriptors[module_id]

        bus.emit("UI ADAPTATION",
                 f"🗑️   UI descriptor removed: {name}",
                 module_id=module_id)

        for fn in list(self._remove_callbacks):
            try:
                fn(module_id)
            except Exception:
                pass

    def get_descriptor(self, module_id: str) -> Optional[Dict[str, Any]]:
        return self._descriptors.get(module_id)

    def all_descriptors(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._descriptors)

    def refresh_all(self):
        """
        Re-build descriptors for all currently ONLINE modules.
        Called on startup to sync with any persisted DATABASE state.
        """
        index_path = DATABASE_ROOT / "index.json"
        if not index_path.exists():
            return
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return

        for module_id in index:
            rec = registry.get(module_id)
            if rec and rec.stage == ModuleStage.ONLINE:
                self.register_module(module_id)


ui_engine = UIAdaptationEngine()
