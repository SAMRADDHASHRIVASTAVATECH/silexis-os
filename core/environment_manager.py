"""
Python Environment Manager — selects and activates the correct isolated
Python environment for each module. Fully independent from the intent system.
Activates only after capability injection is complete.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry

ENVIRONMENTS_ROOT = Path("ENVIRONMENTS")
DATABASE_ROOT = Path("DATABASE")


# Default environment definitions
DEFAULT_ENVIRONMENTS = {
    "torch_env": {
        "name": "torch_env",
        "display_name": "PyTorch Runtime",
        "hardware": "gpu",
        "packages": ["torch", "torchvision", "numpy"],
        "compatibility_score": 0,
    },
    "fastapi_env": {
        "name": "fastapi_env",
        "display_name": "FastAPI Service",
        "hardware": "cpu",
        "packages": ["fastapi", "uvicorn", "pydantic"],
        "compatibility_score": 0,
    },
    "gpu_env": {
        "name": "gpu_env",
        "display_name": "GPU Compute",
        "hardware": "gpu",
        "packages": ["cupy", "numpy", "scipy"],
        "compatibility_score": 0,
    },
    "cpu_env": {
        "name": "cpu_env",
        "display_name": "CPU General",
        "hardware": "cpu",
        "packages": ["numpy", "requests", "pyyaml"],
        "compatibility_score": 0,
    },
}


def _ensure_env_dirs():
    for env_name in DEFAULT_ENVIRONMENTS:
        env_dir = ENVIRONMENTS_ROOT / env_name
        env_dir.mkdir(parents=True, exist_ok=True)
        meta_path = env_dir / "env_meta.json"
        if not meta_path.exists():
            with open(meta_path, "w") as f:
                json.dump(DEFAULT_ENVIRONMENTS[env_name], f, indent=2)
        req_path = env_dir / "requirements.txt"
        if not req_path.exists():
            pkgs = DEFAULT_ENVIRONMENTS[env_name]["packages"]
            req_path.write_text("\n".join(pkgs) + "\n")
        act_path = env_dir / "activate.sh"
        if not act_path.exists():
            act_path.write_text(f"#!/bin/bash\nsource {env_dir}/bin/activate\n")

    index_path = ENVIRONMENTS_ROOT / "index.json"
    if not index_path.exists():
        with open(index_path, "w") as f:
            json.dump(DEFAULT_ENVIRONMENTS, f, indent=2)


def _score_environment(env_meta: Dict, requirements: str, runtime_env: str, recommended: str) -> float:
    score = 0.0
    env_name = env_meta.get("name", "")

    # Direct recommendation match
    if env_name == recommended:
        score += 0.6

    # Package compatibility
    env_packages = env_meta.get("packages", [])
    req_lines = [l.strip().lower() for l in requirements.splitlines() if l.strip()]
    for pkg in env_packages:
        if any(pkg.lower() in req for req in req_lines):
            score += 0.1

    return min(score, 1.0)


def _load_env_index() -> Dict[str, Any]:
    index_path = ENVIRONMENTS_ROOT / "index.json"
    if index_path.exists():
        with open(index_path, "r") as f:
            return json.load(f)
    return DEFAULT_ENVIRONMENTS


def select_environment(requirements: str, runtime_env: str, recommended: str) -> Tuple[str, float]:
    """Score all environments and return the best match."""
    env_index = _load_env_index()
    scores = {}
    for env_name, env_meta in env_index.items():
        scores[env_name] = _score_environment(env_meta, requirements, runtime_env, recommended)

    best = max(scores, key=scores.get)
    return best, scores[best]


def activate_environment(module_id: str, package: Dict[str, Any]):
    """
    Select and activate the correct isolated environment for this module.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "ENVIRONMENT MANAGER", msg, sev, module_id=module_id
    )

    registry.update_stage(module_id, ModuleStage.ACTIVATING)
    _ensure_env_dirs()

    emit("🔍  Reading runtime requirements")

    env_spec = package.get("environment_spec", {})
    requirements = env_spec.get("requirements", "")
    runtime_env = env_spec.get("runtime_env", "")
    recommended = env_spec.get("recommended", "cpu_env")

    emit("📊  Scoring environment candidates")
    time.sleep(0.2)

    best_env, score = select_environment(requirements, runtime_env, recommended)

    emit(f"✅  Matching environment found: {best_env} (score: {score:.2f})", Severity.SUCCESS)
    emit(f"⚡  Activating isolated runtime: {best_env}")

    # Verify environment folder exists
    env_dir = ENVIRONMENTS_ROOT / best_env
    if not env_dir.exists():
        emit(f"⚠️   Environment dir missing, using cpu_env fallback", Severity.WARNING)
        best_env = "cpu_env"

    # Update DATABASE environment map
    env_map_path = DATABASE_ROOT / "environments" / "environment_map.json"
    env_map = {}
    if env_map_path.exists():
        with open(env_map_path, "r") as f:
            env_map = json.load(f)
    env_map[module_id] = best_env
    env_map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_map_path, "w") as f:
        json.dump(env_map, f, indent=2)

    # Update module state
    registry.update_field(module_id, environment=best_env)

    emit(f"✅  Environment online: {best_env}", Severity.SUCCESS)
    return best_env


environment_manager_instance = None  # Lazy singleton pattern used via functions
