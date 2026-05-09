"""
Headless pipeline test — runs the full module lifecycle without the GUI.
Verifies every stage completes and the module reaches ONLINE status.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from core.event_bus import bus, Severity
from core.module_state import registry, ModuleStage
from core.kafka_pipeline import pipeline
from core.database_manager import handle_pipeline_message


def print_event(event):
    icon = {"INFO": "  ", "SUCCESS": "✅", "WARNING": "⚠️ ", "ERROR": "❌"}
    print(f"[{event.formatted_time}] {icon.get(event.severity.value,'  ')} "
          f"{event.component:<24} {event.description}")


async def main():
    print("=" * 70)
    print("  HEADLESS PIPELINE TEST")
    print("=" * 70)

    # Wire event bus to console
    bus.subscribe(print_event)

    # Initialize pipeline
    loop = asyncio.get_running_loop()
    bus.set_loop(loop)
    pipeline.initialize(loop)
    pipeline.set_consumer(handle_pipeline_message)
    asyncio.create_task(pipeline.start_consuming())

    try:
        # Run the full pipeline on the example module
        from core.pipeline_orchestrator import process_module
        module_path = Path("example_modules/nlp_processor")

        print(f"\n  Dropping module: {module_path}\n")
        module_id = await process_module(module_path)

        # Check final state
        rec = registry.get(module_id)
        print("\n" + "=" * 70)
        print("  FINAL STATE")
        print("=" * 70)
        print(f"  Module ID:    {rec.module_id}")
        print(f"  Name:         {rec.name}")
        print(f"  Stage:        {rec.stage_icon} {rec.stage.value}")
        print(f"  Capabilities: {len(rec.capabilities)}")
        print(f"  Environment:  {rec.environment}")
        if rec.error:
            print(f"  Error:        {rec.error}")
        print("=" * 70)

        assert rec.stage == ModuleStage.ONLINE, f"Expected ONLINE, got {rec.stage.value}"
        print("\n  OK  ALL STAGES PASSED — MODULE IS ONLINE\n")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
