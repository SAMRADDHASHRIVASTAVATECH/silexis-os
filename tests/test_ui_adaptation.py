"""
End-to-end test for the UI Adaptation Engine.
Verifies: descriptor creation, widget inference, capability update, removal.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from core.module_state import registry, ModuleStage
from core.kafka_pipeline import pipeline
from core.database_manager import (
    handle_pipeline_message, remove_module,
    update_module_capabilities,
)
from core.ui_adaptation_engine import ui_engine
from core.event_bus import bus

added_events   = []
updated_events = []
removed_events = []

ui_engine.on_module_added(
    lambda mid, desc: added_events.append(
        (mid, desc["name"], desc["purpose"], len(desc["capabilities"]))
    )
)
ui_engine.on_module_updated(
    lambda mid, desc: updated_events.append((mid, desc["name"]))
)
ui_engine.on_module_removed(
    lambda mid: removed_events.append(mid)
)


async def main():
    print("=" * 60)
    print("  UI ADAPTATION ENGINE TEST")
    print("=" * 60)

    loop = asyncio.get_running_loop()
    bus.set_loop(loop)
    pipeline.initialize(loop)
    pipeline.set_consumer(handle_pipeline_message)
    asyncio.create_task(pipeline.start_consuming())

    try:
        from core.pipeline_orchestrator import process_module
        mod_path = Path("example_modules/nlp_processor")
        mid = await process_module(mod_path)
        rec = registry.get(mid)
        print(f"\n1. Module stage: {rec.stage.value}")

        # ── Verify descriptor created ──────────────────────────────────────
        assert len(added_events) == 1, f"Expected 1 add event, got {len(added_events)}"
        assert len(updated_events) >= 1, "Expected post-orchestration UI update"
        ev = added_events[0]
        print(f"2. UI descriptor: name={ev[1]}  purpose={ev[2]}  caps={ev[3]}")
        assert ev[2] == "nlp",  f"Expected nlp purpose, got {ev[2]}"
        assert ev[3] == 5,      f"Expected 5 caps, got {ev[3]}"

        desc = ui_engine.get_descriptor(mid)
        assert desc is not None
        assert len(desc["capabilities"]) == 5
        assert len(desc["workflows"]) > 0
        assert desc["dashboard_color"] == "#58a6ff"
        print(f"3. Descriptor: {len(desc['capabilities'])} caps, "
              f"{len(desc['workflows'])} workflows, "
              f"color={desc['dashboard_color']}")

        # ── Verify widget type inference ───────────────────────────────────
        widgets = {c["name"]: c["widget_type"] for c in desc["capabilities"]}
        print(f"4. Widget types: {widgets}")
        valid = {"text_input", "file_input", "slider", "toggle", "dropdown", "trigger"}
        assert all(w in valid for w in widgets.values()), f"Invalid widget: {widgets}"

        # ── Verify intent labels wired ─────────────────────────────────────
        intents = {c["name"]: c["intent_label"] for c in desc["capabilities"]}
        print(f"5. Intent labels: {intents}")
        assert all(intents.values()), "Some intent labels are empty"

        # ── Simulate capability update ─────────────────────────────────────
        new_caps = {
            "module_id":   mid,
            "module_name": "NLP Processor",
            "version":     "1.2.0",
            "purpose":     "nlp",
            "actions":     desc["capabilities"] + [{
                "name":        "translate",
                "description": "Translate text between languages",
                "inputs":      ["text: str", "target_lang: str"],
                "outputs":     ["translated: str"],
            }],
            "expansion_score": 0.9,
        }
        update_module_capabilities(mid, new_caps)

        assert len(updated_events) >= 2, f"Expected capability update event, got {len(updated_events)}"
        print(f"6. UI update event fired: {updated_events[-1]}")

        desc2 = ui_engine.get_descriptor(mid)
        cap_names = [c["name"] for c in desc2["capabilities"]]
        assert "translate" in cap_names, f"translate not in {cap_names}"
        print(f"7. New capability in descriptor: {cap_names}")

        # ── Verify new widget inferred for translate ───────────────────────
        translate_cap = next(c for c in desc2["capabilities"] if c["name"] == "translate")
        print(f"8. translate widget_type: {translate_cap['widget_type']}")
        assert translate_cap["widget_type"] in valid

        # ── Remove module ──────────────────────────────────────────────────
        registry.stop(mid)
        registry.remove(mid)
        remove_module(mid)

        assert mid in removed_events, f"{mid} not in removed_events"
        assert ui_engine.get_descriptor(mid) is None, "Descriptor not cleaned up"
        print("9. UI remove event fired, descriptor cleaned up")

        print("\n" + "=" * 60)
        print("  ALL UI ADAPTATION TESTS PASS")
        print("=" * 60)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
