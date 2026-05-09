"""
Module Extractor — reads all files from the uploaded folder and produces
a normalized internal representation for the deep learning analyzer.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry


REQUIRED_FILES = [
    "module_manifest.json",
    "module_config.yaml",
    "module_metadata.json",
    "requirements.txt",
    "capabilities.json",
    "intents.json",
    "routes.json",
]

REQUIRED_DIRS = ["src", "templates", "assets", "environments", "logs", "cache", "exports"]


def _read_json(path: Path) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}


def _read_yaml(path: Path) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        return {"_error": str(e)}


def _read_text(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _walk_directory(root: Path) -> Dict[str, Any]:
    """Recursively walk directory and collect file contents."""
    result = {}
    for item in sorted(root.iterdir()):
        if item.is_dir():
            result[item.name + "/"] = _walk_directory(item)
        else:
            ext = item.suffix.lower()
            if ext in (".json",):
                result[item.name] = _read_json(item)
            elif ext in (".yaml", ".yml"):
                result[item.name] = _read_yaml(item)
            else:
                content = _read_text(item)
                result[item.name] = content[:4096] if len(content) > 4096 else content
    return result


def validate_structure(module_path: Path) -> tuple[bool, list]:
    """Validate that the module folder matches the universal template."""
    missing = []
    for f in REQUIRED_FILES:
        if not (module_path / f).exists():
            missing.append(f)
    for d in REQUIRED_DIRS:
        if not (module_path / d).is_dir():
            missing.append(d + "/")
    return len(missing) == 0, missing


def extract(module_id: str, module_path: Path) -> Dict[str, Any]:
    """
    Full extraction pipeline for a module folder.
    Returns a normalized representation dict.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "MODULE EXTRACTOR", msg, sev, module_id=module_id
    )

    registry.update_stage(module_id, ModuleStage.SCANNING)
    emit("📁  Reading directory structure")

    # Validate structure
    valid, missing = validate_structure(module_path)
    if not valid:
        emit(f"⚠️   Missing files/dirs: {', '.join(missing)}", Severity.WARNING)

    emit("📄  Parsing manifest files")
    manifest = _read_json(module_path / "module_manifest.json") if (module_path / "module_manifest.json").exists() else {}

    emit("⚙️   Reading configuration")
    config = _read_yaml(module_path / "module_config.yaml") if (module_path / "module_config.yaml").exists() else {}

    emit("📋  Reading metadata")
    metadata = _read_json(module_path / "module_metadata.json") if (module_path / "module_metadata.json").exists() else {}

    emit("🗺️   Mapping capability definitions")
    capabilities = _read_json(module_path / "capabilities.json") if (module_path / "capabilities.json").exists() else {}

    emit("🔗  Mapping intent definitions")
    intents = _read_json(module_path / "intents.json") if (module_path / "intents.json").exists() else {}

    emit("🛣️   Mapping route definitions")
    routes = _read_json(module_path / "routes.json") if (module_path / "routes.json").exists() else {}

    emit("🔗  Mapping dependency graph")
    dependencies = _read_json(module_path / "dependencies.json") if (module_path / "dependencies.json").exists() else {}

    emit("📦  Reading requirements")
    requirements = _read_text(module_path / "requirements.txt") if (module_path / "requirements.txt").exists() else ""

    emit("🌐  Reading runtime environment spec")
    runtime_env = _read_text(module_path / "runtime.env") if (module_path / "runtime.env").exists() else ""

    emit("📂  Walking full directory tree")
    full_tree = _walk_directory(module_path)

    # Read src files
    src_files = {}
    src_path = module_path / "src"
    if src_path.exists():
        for py_file in src_path.glob("*.py"):
            src_files[py_file.name] = _read_text(py_file)

    # Read environment definitions
    env_defs = {}
    env_path = module_path / "environments"
    if env_path.exists():
        for env_file in env_path.iterdir():
            env_defs[env_file.name] = _read_text(env_file)

    emit("✅  Extraction complete", Severity.SUCCESS)

    return {
        "module_id": module_id,
        "source_path": str(module_path),
        "manifest": manifest,
        "config": config,
        "metadata": metadata,
        "capabilities": capabilities,
        "intents": intents,
        "routes": routes,
        "dependencies": dependencies,
        "requirements": requirements,
        "runtime_env": runtime_env,
        "src_files": src_files,
        "env_defs": env_defs,
        "full_tree": full_tree,
        "structure_valid": valid,
        "missing_items": missing,
    }
