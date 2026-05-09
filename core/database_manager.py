"""
Database Manager — writes and removes extension packages in DATABASE/.
File-based registry: transparent, inspectable, WatchDog-monitorable.

All shared-file writes use per-file threading.Lock to prevent concurrent
corruption when multiple modules process simultaneously.
"""
import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry

DATABASE_ROOT = Path("DATABASE")

# Per-file locks — prevents concurrent JSON corruption
_file_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()

# Listeners notified after any remove operation (GUI panels subscribe)
_remove_listeners: List[Callable[[str], None]] = []


def add_remove_listener(fn: Callable[[str], None]):
    """Register a callback that fires after a module is fully removed."""
    _remove_listeners.append(fn)


def _get_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_lock:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


def _ensure_dirs():
    for d in [
        DATABASE_ROOT / "modules",
        DATABASE_ROOT / "capabilities",
        DATABASE_ROOT / "routes",
        DATABASE_ROOT / "environments",
    ]:
        d.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(path)
    with lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


def _read_json(path: Path) -> Dict:
    if path.exists():
        lock = _get_lock(path)
        with lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
    return {}


def _update_json(path: Path, updater: Callable[[Dict], None]):
    """Atomic read-modify-write with file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(path)
    with lock:
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        updater(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


# ── Store ──────────────────────────────────────────────────────────────────

def store_module(module_id: str, package: Dict[str, Any]) -> Path:
    """
    Write the extension package and all derived files to DATABASE/.
    Returns the module folder path.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "DATABASE MANAGER", msg, sev, module_id=module_id
    )

    registry.update_stage(module_id, ModuleStage.STORING)
    _ensure_dirs()

    module_dir = DATABASE_ROOT / "modules" / module_id
    module_dir.mkdir(parents=True, exist_ok=True)

    emit("💾  Database Manager writing files")

    # Per-module files (no lock contention — unique paths)
    _write_json(module_dir / "extension.pkg", package)
    emit("📦  extension.pkg written")

    cap_entry = package.get("capability_registry_entry", {})
    _write_json(module_dir / "capabilities.json", cap_entry)
    emit("🗂️   capabilities.json written")

    _write_json(module_dir / "routing.json", package.get("routing_definition", {}))
    emit("🛣️   routing.json written")

    state = {
        "module_id": module_id,
        "stage": "STORING",
        "stored_at": time.time(),
        **package.get("state_descriptor", {}),
    }
    _write_json(module_dir / "state.json", state)
    emit("📋  state.json written")

    _write_json(module_dir / "analyzer_output.json", package.get("analyzer_output_summary", {}))
    emit("🧠  analyzer_output.json written")

    # Shared registry files — atomic read-modify-write
    _update_json(
        DATABASE_ROOT / "capabilities" / "global_registry.json",
        lambda d: d.update({module_id: cap_entry}),
    )
    emit("🌐  Global capability registry updated")

    _update_json(
        DATABASE_ROOT / "routes" / "routing_table.json",
        lambda d: d.update({module_id: package.get("routing_definition", {})}),
    )
    emit("🔗  Routing table updated")

    _update_json(
        DATABASE_ROOT / "environments" / "environment_map.json",
        lambda d: d.update({
            module_id: package.get("environment_spec", {}).get("recommended", "cpu_env")
        }),
    )
    emit("🖥️   Environment map updated")

    _update_json(
        DATABASE_ROOT / "index.json",
        lambda d: d.update({module_id: {
            "name":       cap_entry.get("module_name", module_id),
            "version":    cap_entry.get("version", "1.0.0"),
            "purpose":    cap_entry.get("purpose", "unknown"),
            "stored_at":  time.time(),
            "module_dir": str(module_dir),
        }}),
    )
    emit("📋  Master index updated")

    emit("✅  Storage complete", Severity.SUCCESS)
    bus.emit("DATABASE MANAGER",
             f"📁  DATABASE folder updated for {module_id}",
             Severity.SUCCESS, module_id=module_id)

    return module_dir


# ── Remove ─────────────────────────────────────────────────────────────────

def remove_module(module_id: str):
    """
    Fully purge a module from every part of the DATABASE:
      • DATABASE/modules/{id}/          — entire folder deleted
      • DATABASE/index.json             — entry removed
      • DATABASE/capabilities/global_registry.json  — entry removed
      • DATABASE/routes/routing_table.json          — entry removed
      • DATABASE/environments/environment_map.json  — entry removed

    Also purges the module from in-memory intent/routing/expansion state
    and notifies all registered remove listeners (GUI panels).
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "DATABASE MANAGER", msg, sev, module_id=module_id
    )

    emit(f"🗑️   Removing module {module_id} from DATABASE")

    # 1. Delete per-module folder
    module_dir = DATABASE_ROOT / "modules" / module_id
    if module_dir.exists():
        shutil.rmtree(module_dir, ignore_errors=True)
        emit("🗑️   modules/{id}/ folder deleted")

    # 2. Remove from index.json
    _update_json(
        DATABASE_ROOT / "index.json",
        lambda d: d.pop(module_id, None) or d,
    )
    emit("📋  Removed from index.json")

    # 3. Remove from global capability registry
    _update_json(
        DATABASE_ROOT / "capabilities" / "global_registry.json",
        lambda d: d.pop(module_id, None) or d,
    )
    emit("🌐  Removed from global_registry.json")

    # 4. Remove from routing table
    _update_json(
        DATABASE_ROOT / "routes" / "routing_table.json",
        lambda d: d.pop(module_id, None) or d,
    )
    emit("🔗  Removed from routing_table.json")

    # 5. Remove from environment map
    _update_json(
        DATABASE_ROOT / "environments" / "environment_map.json",
        lambda d: d.pop(module_id, None) or d,
    )
    emit("🖥️   Removed from environment_map.json")

    # 6. Purge from in-memory intent/routing/expansion state
    _purge_in_memory(module_id)
    emit("🧠  In-memory state purged")

    emit("✅  Module fully removed from DATABASE", Severity.SUCCESS)

    # 7. Notify GUI listeners
    for fn in list(_remove_listeners):
        try:
            fn(module_id)
        except Exception:
            pass

    # 8. Notify UI Adaptation Engine
    try:
        from core.ui_adaptation_engine import ui_engine
        ui_engine.unregister_module(module_id)
    except Exception:
        pass

    # 9. Remove from Orchestration Engine / Ecosystem
    try:
        from core.orchestration_engine import orchestration_engine
        orchestration_engine.remove_module(module_id)
    except Exception:
        pass


def _purge_in_memory(module_id: str):
    """Remove all in-memory traces of a module from intent/routing/expansion."""
    try:
        from core.intent_manager import intent_manager
        intent_manager.purge_module(module_id)
    except Exception:
        pass

    try:
        from core.intent_router import intent_router
        intent_router.purge_module(module_id)
    except Exception:
        pass

    try:
        from core.capability_expansion import expansion_system
        expansion_system._known_capabilities = {
            k for k in expansion_system._known_capabilities
            if not k.startswith(f"{module_id}::")
        }
    except Exception:
        pass


# ── Update capabilities for an existing module ─────────────────────────────

def update_module_capabilities(module_id: str, new_capabilities: Dict[str, Any]):
    """
    Called when a module's capabilities.json is changed externally.
    Updates:
      • DATABASE/modules/{id}/capabilities.json
      • DATABASE/capabilities/global_registry.json
      • In-memory intent manager + router + expansion system
    Fires remove listeners so GUI panels refresh immediately.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "DATABASE MANAGER", msg, sev, module_id=module_id
    )

    emit("🔄  Updating capabilities for module")

    # Write updated capabilities to module folder
    cap_path = DATABASE_ROOT / "modules" / module_id / "capabilities.json"
    if cap_path.parent.exists():
        _write_json(cap_path, new_capabilities)
        emit("🗂️   capabilities.json updated")

    # Update global registry
    _update_json(
        DATABASE_ROOT / "capabilities" / "global_registry.json",
        lambda d: d.update({module_id: new_capabilities}),
    )
    emit("🌐  Global registry updated with new capabilities")

    # Re-run expansion to inject net-new capabilities into in-memory state
    try:
        from core.capability_expansion import expansion_system
        package = {"capability_registry_entry": new_capabilities}
        expansion_system.expand(module_id, package)
    except Exception as e:
        emit(f"⚠️   Expansion error: {e}", Severity.WARNING)

    # Reload intent mappings
    try:
        from core.intent_manager import intent_manager
        intent_manager.load_from_database(module_id)
    except Exception as e:
        emit(f"⚠️   Intent reload error: {e}", Severity.WARNING)

    emit("✅  Capability update propagated to all systems", Severity.SUCCESS)

    # Notify GUI
    for fn in list(_remove_listeners):
        try:
            fn(module_id)
        except Exception:
            pass

    # Notify UI Adaptation Engine — rebuild descriptor with new capabilities
    try:
        from core.ui_adaptation_engine import ui_engine
        ui_engine.register_module(module_id)  # register_module handles update vs add
    except Exception:
        pass


# ── Kafka consumer callback ────────────────────────────────────────────────

async def handle_pipeline_message(message: Dict[str, Any]):
    """Consumer callback — skip if already stored by the orchestrator."""
    module_id = message.get("module_id", "unknown")
    state_path = DATABASE_ROOT / "modules" / module_id / "state.json"
    if state_path.exists():
        return  # Already stored — skip duplicate write
    payload = message.get("payload", {})
    store_module(module_id, payload)
