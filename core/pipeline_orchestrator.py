"""
Pipeline Orchestrator — coordinates the full module lifecycle from
upload detection through to ONLINE status. Runs each stage in sequence,
updating the GUI and event log at every step.
"""
import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from core.analyzer import analyze
from core.capability_expansion import expansion_system
from core.database_manager import store_module
from core.environment_manager import activate_environment
from core.event_bus import Severity, bus
from core.extension_builder import build_extension
from core.extractor import extract
from core.intent_manager import intent_manager
from core.intent_router import intent_router
from core.kafka_pipeline import pipeline
from core.module_state import ModuleRecord, ModuleStage, registry


async def process_module(module_path: Path) -> str:
    """
    Full lifecycle pipeline for a dropped module folder.
    Returns the assigned module_id.
    """
    # ── Stage 1: Upload / Validation ──────────────────────────────────────
    bus.emit("CENTRAL SYSTEM", "📂  Folder detected")
    bus.emit("CENTRAL SYSTEM", "🔍  Validating folder structure")

    module_id = str(uuid.uuid4())[:8].upper()
    bus.emit("CENTRAL SYSTEM", f"🆔  Module ID assigned: {module_id}")

    # Read name from manifest if available
    manifest_path = module_path / "module_manifest.json"
    module_name = module_path.name
    if manifest_path.exists():
        import json
        try:
            with open(manifest_path) as f:
                mf = json.load(f)
            module_name = mf.get("name", module_name)
        except Exception:
            pass

    record = ModuleRecord(
        module_id=module_id,
        name=module_name,
        source_path=str(module_path),
        stage=ModuleStage.WAITING,
    )
    registry.register(record)

    bus.emit("CENTRAL SYSTEM", f"📋  Reading manifest: {module_name}", module_id=module_id)
    bus.emit("CENTRAL SYSTEM", "✅  Upload accepted", Severity.SUCCESS, module_id=module_id)

    await asyncio.sleep(0.1)

    try:
        # ── Stage 2: Extraction ───────────────────────────────────────────
        loop = asyncio.get_running_loop()
        extracted = await loop.run_in_executor(
            None, extract, module_id, module_path
        )
        await asyncio.sleep(0.1)

        # ── Stage 3: Analysis ─────────────────────────────────────────────
        analysis = await loop.run_in_executor(
            None, analyze, module_id, extracted
        )
        await asyncio.sleep(0.1)

        # ── Stage 4: Conversion ───────────────────────────────────────────
        package = await loop.run_in_executor(
            None, build_extension, module_id, extracted, analysis
        )
        await asyncio.sleep(0.1)

        # ── Stage 5: Transfer + Storage ───────────────────────────────────
        registry.update_stage(module_id, ModuleStage.STORING)
        # Store directly (synchronous, so next stages can proceed immediately)
        await loop.run_in_executor(
            None, store_module, module_id, package
        )
        # Also produce to Kafka pipeline (for monitoring/audit trail)
        await pipeline.produce(module_id, "module.store", package)
        await asyncio.sleep(0.2)  # Give WatchDog time to detect

        # ── Stage 6: Routing ──────────────────────────────────────────────
        registry.update_stage(module_id, ModuleStage.ROUTING)
        await loop.run_in_executor(
            None, intent_manager.load_from_database, module_id
        )
        # Wire manager → router if not already done
        if intent_router.receive_mappings not in intent_manager._router_callbacks:
            intent_manager.add_router_callback(intent_router.receive_mappings)
        # Push current mappings to router
        intent_router.receive_mappings(
            intent_manager.get_intent_table(),
            intent_manager.get_knowledge_base()
        )
        intent_router.establish_routes(module_id)
        await asyncio.sleep(0.1)

        # ── Stage 7: Capability Expansion ─────────────────────────────────
        await loop.run_in_executor(
            None, expansion_system.expand, module_id, package
        )
        await asyncio.sleep(0.1)

        # ── Stage 8: Environment Activation ───────────────────────────────
        env_name = await loop.run_in_executor(
            None, activate_environment, module_id, package
        )
        await asyncio.sleep(0.1)

        # ── Stage 9: ONLINE ───────────────────────────────────────────────
        registry.update_stage(module_id, ModuleStage.ONLINE)
        cap_count = len(registry.get(module_id).capabilities)
        route_count = len(intent_router.get_active_routes())

        bus.emit(
            "CENTRAL SYSTEM",
            f"🟢  MODULE ONLINE — {module_name} | Caps: {cap_count} | Routes: {route_count} | Env: {env_name}",
            Severity.SUCCESS,
            module_id=module_id,
        )

        # ── Stage 10: UI Adaptation + Ecosystem Orchestration ────────────
        try:
            from core.ui_adaptation_engine import ui_engine
            from core.orchestration_engine import orchestration_engine

            # Initial descriptor (capabilities, routing) before ecosystem placement
            ui_engine.register_module(module_id)
            descriptor = ui_engine.get_descriptor(module_id)
            if descriptor:
                orchestration_engine.intake_module(module_id, descriptor)
                # Re-build so slots, synergies, and graph data match ecosystem state
                ui_engine.register_module(module_id)

        except Exception as e:
            bus.emit("CENTRAL SYSTEM",
                     f"⚠️   Orchestration error: {e}",
                     Severity.WARNING, module_id=module_id)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        registry.update_stage(module_id, ModuleStage.FAILED, error=str(e))
        bus.emit("CENTRAL SYSTEM", f"🔴  FAILED: {e}", Severity.ERROR, module_id=module_id)
        bus.emit("CENTRAL SYSTEM", tb[:300], Severity.ERROR, module_id=module_id)

    return module_id
