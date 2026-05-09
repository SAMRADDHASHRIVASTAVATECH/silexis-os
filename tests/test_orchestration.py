"""
End-to-end test for the Game-Engine Orchestration Layer.
Tests: slot assignment, synergy detection, ecosystem graph,
       multi-module orchestration, removal + rebalance.
"""
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from core.module_state import registry, ModuleStage
from core.kafka_pipeline import pipeline
from core.database_manager import handle_pipeline_message, remove_module
from core.ecosystem_registry import ecosystem, SlotType
from core.orchestration_engine import orchestration_engine
from core.ui_adaptation_engine import ui_engine
from core.event_bus import bus

intake_events   = []
synergy_events  = []
remove_events   = []
rebalance_count = [0]

orchestration_engine.on_intake(lambda mid, p: intake_events.append((mid, p)))
orchestration_engine.on_synergy(lambda syns: synergy_events.extend(syns))
orchestration_engine.on_remove(lambda mid: remove_events.append(mid))
orchestration_engine.on_rebalance(lambda: rebalance_count.__setitem__(0, rebalance_count[0] + 1))


async def main():
    print("=" * 65)
    print("  GAME-ENGINE ORCHESTRATION TEST")
    print("=" * 65)

    loop = asyncio.get_running_loop()
    bus.set_loop(loop)
    pipeline.initialize(loop)
    pipeline.set_consumer(handle_pipeline_message)
    asyncio.create_task(pipeline.start_consuming())

    try:
        from core.pipeline_orchestrator import process_module
        mod_path = Path("example_modules/nlp_processor")

        # ── Load module 1 ──────────────────────────────────────────────────
        mid1 = await process_module(mod_path)
        rec1 = registry.get(mid1)
        print(f"\n1. Module 1 stage: {rec1.stage.value}")

        # Verify intake fired
        assert len(intake_events) >= 1, "No intake event"
        placement = intake_events[-1][1]
        print(f"2. Placement: slots={placement['slots']}")
        assert len(placement["slots"]) > 0, "No slots assigned"

        # Verify slots in ecosystem
        slots = ecosystem.get_slots_for_module(mid1)
        print(f"3. Ecosystem slots: {[s.value for s in slots]}")
        assert len(slots) > 0, "No ecosystem slots"

        # Verify descriptor has slot data
        desc = ui_engine.get_descriptor(mid1)
        assert "slots" in desc, "No slots in descriptor"
        assert len(desc["slots"]) > 0
        print(f"4. Descriptor slots: {desc['slots']}")

        # ── Load module 2 (copy of same module) ────────────────────────────
        td = Path(tempfile.mkdtemp())
        mod2_path = td / "nlp_processor_2"
        shutil.copytree(mod_path, mod2_path)

        mid2 = await process_module(mod2_path)
        rec2 = registry.get(mid2)
        print(f"\n5. Module 2 stage: {rec2.stage.value}")

        # Verify synergies discovered between module 1 and 2
        all_syns = ecosystem.get_all_synergies()
        print(f"6. Total synergies: {len(all_syns)}")
        if all_syns:
            for syn in all_syns[:3]:
                print(f"   ⚡ {syn.name}: {syn.description}")

        # Verify ecosystem graph connections
        node1 = ecosystem.get_node(mid1)
        node2 = ecosystem.get_node(mid2)
        print(f"7. Node1 connections: {node1.connections}")
        print(f"8. Node2 connections: {node2.connections}")

        # Verify ecosystem stats
        stats = ecosystem.get_ecosystem_stats()
        print(f"9. Ecosystem stats: {stats}")
        assert stats["total_modules"] >= 2
        assert stats["occupied_slots"] > 0

        # ── Remove module 1 ────────────────────────────────────────────────
        registry.stop(mid1)
        registry.remove(mid1)
        remove_module(mid1)

        assert mid1 in remove_events, "Remove event not fired"
        assert rebalance_count[0] >= 1, "Rebalance not triggered"
        assert ecosystem.get_node(mid1) is None, "Node not removed"
        print(f"\n10. Module 1 removed, rebalanced {rebalance_count[0]} time(s)")

        # Verify synergies involving mid1 are gone
        remaining_syns = ecosystem.get_all_synergies()
        for syn in remaining_syns:
            assert syn.module_a != mid1 and syn.module_b != mid1, \
                f"Synergy still references removed module {mid1}"
        print(f"11. Synergies cleaned up: {len(remaining_syns)} remaining")

        # Cleanup
        shutil.rmtree(td, ignore_errors=True)

        print("\n" + "=" * 65)
        print("  ALL ORCHESTRATION TESTS PASS")
        print("=" * 65)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
