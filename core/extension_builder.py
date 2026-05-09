"""
Custom Extension Builder — converts the extracted module + analyzer output
into a single standardized runtime extension package (a JSON artifact).
This package becomes the single source of truth for the module inside the system.
"""
import json
import time
from pathlib import Path
from typing import Any, Dict

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry


def build_extension(module_id: str, extracted: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a standardized extension package dict.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "CUSTOM EXTENSION BUILDER", msg, sev, module_id=module_id
    )

    registry.update_stage(module_id, ModuleStage.CONVERTING)
    emit("🔨  Building custom runtime extension")
    time.sleep(0.2)

    manifest = extracted.get("manifest", {})
    config = extracted.get("config", {})
    metadata = extracted.get("metadata", {})

    emit("📦  Compiling standardized package")

    # Normalize capability registry entry
    capability_registry_entry = {
        "module_id": module_id,
        "module_name": manifest.get("name", metadata.get("name", module_id)),
        "version": manifest.get("version", "1.0.0"),
        "purpose": analysis["classified_purpose"],
        "actions": analysis["callable_actions"],
        "expansion_score": analysis["expansion_potential_score"],
    }

    # Compile routing definition
    routing_definition = {
        "module_id": module_id,
        "intent_mappings": analysis["intent_mappings"],
        "task_relationships": analysis["task_relationships"],
        "communication_patterns": analysis["communication_patterns"],
        "routes": extracted.get("routes", {}),
    }

    # Intent mapping table
    intent_mapping_table = {}
    for intent in analysis["intent_mappings"]:
        if isinstance(intent, dict):
            label = intent.get("label", intent.get("intent", ""))
            action = intent.get("action", intent.get("handler", ""))
            if label:
                intent_mapping_table[label] = {
                    "action": action,
                    "module_id": module_id,
                    "confidence": intent.get("confidence", 0.85),
                }

    # Environment specification reference
    env_spec = {
        "recommended": analysis["recommended_environment"],
        "requirements": extracted.get("requirements", ""),
        "runtime_env": extracted.get("runtime_env", ""),
        "env_definitions": list(extracted.get("env_defs", {}).keys()),
    }

    # Dependency resolution record
    dep_record = extracted.get("dependencies", {})

    # Module state descriptor
    state_descriptor = {
        "module_id": module_id,
        "stage": "CONVERTING",
        "created_at": time.time(),
        "entry_points": manifest.get("entry_points", ["src/main.py"]),
        "runtime_type": manifest.get("runtime_type", analysis["recommended_environment"]),
    }

    emit("🔗  Embedding routing definitions")

    package = {
        "schema_version": "1.0.0",
        "module_id": module_id,
        "built_at": time.time(),
        "capability_registry_entry": capability_registry_entry,
        "routing_definition": routing_definition,
        "intent_mapping_table": intent_mapping_table,
        "environment_spec": env_spec,
        "dependency_record": dep_record,
        "state_descriptor": state_descriptor,
        "analyzer_output_summary": {
            "purpose": analysis["classified_purpose"],
            "confidence": analysis["purpose_confidence"],
            "action_count": len(analysis["callable_actions"]),
            "expansion_score": analysis["expansion_potential_score"],
            "recommended_env": analysis["recommended_environment"],
        },
        "entry_point_pointers": manifest.get("entry_points", ["src/main.py"]),
    }

    emit("✅  Extension package ready", Severity.SUCCESS)
    return package
