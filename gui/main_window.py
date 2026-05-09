"""
Central System Interface — the sole visual layer of the entire system.

Layout
──────
  Title bar
  ──────────────────────────────────────────────────────────────
  MODULE MANAGEMENT  (drop zone left | module list right)
  ──────────────────────────────────────────────────────────────
  ADAPTIVE DASHBOARD  (auto-generated per-module panels)
  ──────────────────────────────────────────────────────────────
  [MODULE STATUS] [CAPABILITY STATUS] [INTENT ROUTING]
  [ENVIRONMENT  ] [DATABASE MONITOR ] [WATCHDOG      ]
  ──────────────────────────────────────────────────────────────
  LIVE EVENT LOG

The Adaptive Dashboard section grows and evolves automatically as modules
are loaded, updated, or removed — no manual redesign ever needed.
"""
import asyncio
import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Optional

from core.event_bus import Severity, SystemEvent, bus
from core.kafka_pipeline import pipeline
from core.module_state import ModuleStage, registry
from core.orchestration_engine import orchestration_engine
from core.ui_adaptation_engine import ui_engine
from core.watchdog_system import watchdog
from gui.panels.adaptive_dashboard import AdaptiveDashboard
from gui.panels.capability_status import CapabilityStatusPanel
from gui.panels.database_monitor import DatabaseMonitorPanel
from gui.panels.ecosystem_panel import EcosystemPanel
from gui.panels.environment_panel import EnvironmentPanel
from gui.panels.event_log import EventLogPanel
from gui.panels.intent_routing import IntentRoutingPanel
from gui.panels.module_management import ModuleManagementPanel
from gui.panels.module_status import ModuleStatusPanel
from gui.panels.watchdog_panel import WatchDogPanel
from gui.styles import (
    ACCENT_BLUE, BG_DARK, BG_HEADER, BG_PANEL, BORDER,
    FONT_MONO_S, FONT_TITLE, PAD, TEXT_SUCCESS, TEXT_WARNING,
)


class MainWindow:
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None
        self._event_queue: queue.Queue = queue.Queue()

    # ── Bootstrap ─────────────────────────────────────────────────────────

    def run(self):
        self._start_async_loop()
        self._build_window()
        self._wire_event_bus()
        self._init_kafka_pipeline()
        self._wire_watchdog()
        self._wire_ui_engine()
        self._start_kafka_consumer()
        self._update_kafka_status()
        self._schedule_panel_refresh()
        # Sync with any persisted DATABASE state on startup
        self._root.after(800, self._sync_on_startup)
        self._drain_event_queue()
        self._root.mainloop()
        self._shutdown()

    # ── Async Loop ────────────────────────────────────────────────────────

    def _start_async_loop(self):
        self._loop = asyncio.new_event_loop()
        bus.set_loop(self._loop)
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever, daemon=True
        )
        self._loop_thread.start()

    def _init_kafka_pipeline(self):
        """After the GUI subscribes to the bus so startup Kafka messages appear in the log."""
        pipeline.initialize(self._loop)

    def _start_kafka_consumer(self):
        from core.database_manager import handle_pipeline_message
        pipeline.set_consumer(handle_pipeline_message)
        asyncio.run_coroutine_threadsafe(pipeline.start_consuming(), self._loop)

    def _update_kafka_status(self):
        connected = pipeline._use_real_kafka
        self._root.after(0, self._mgmt_panel.set_kafka_status, connected)

    # ── Window Construction ───────────────────────────────────────────────

    def _build_window(self):
        try:
            from tkinterdnd2 import TkinterDnD
            self._root = TkinterDnD.Tk()
        except Exception:
            self._root = tk.Tk()

        self._root.title("CENTRAL SYSTEM INTERFACE")
        self._root.configure(bg=BG_DARK)
        self._root.geometry("1440x1020")
        self._root.minsize(1100, 800)

        self._build_title_bar()
        self._build_management_section()
        tk.Frame(self._root, bg=BORDER, height=1).pack(fill=tk.X, padx=PAD)
        self._build_adaptive_dashboard()
        tk.Frame(self._root, bg=BORDER, height=1).pack(fill=tk.X, padx=PAD)
        self._build_panel_grid()
        self._build_event_log()

    def _build_title_bar(self):
        bar = tk.Frame(self._root, bg=BG_HEADER, height=40)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="◈  CENTRAL SYSTEM INTERFACE",
                 font=FONT_TITLE, bg=BG_HEADER, fg=ACCENT_BLUE
                 ).pack(side=tk.LEFT, padx=PAD * 2, pady=PAD)

        self._status_label = tk.Label(bar, text="● SYSTEM READY",
                                       font=FONT_MONO_S, bg=BG_HEADER, fg=TEXT_SUCCESS)
        self._status_label.pack(side=tk.RIGHT, padx=PAD * 2)

        tk.Frame(self._root, bg=BORDER, height=1).pack(fill=tk.X)

    def _build_management_section(self):
        mgmt_frame = tk.Frame(self._root, bg=BG_PANEL,
                               highlightthickness=1, highlightbackground=BORDER,
                               height=175)
        mgmt_frame.pack(fill=tk.X, padx=PAD, pady=(PAD, 0))
        mgmt_frame.pack_propagate(False)

        self._mgmt_panel = ModuleManagementPanel(
            mgmt_frame,
            on_module_dropped=self._on_module_dropped,
            on_stop=self._on_module_stop,
            on_remove=self._on_module_remove,
        )
        self._mgmt_panel.pack(fill=tk.BOTH, expand=True)

    def _build_adaptive_dashboard(self):
        """
        The adaptive dashboard section — auto-populated with module panels.
        Height is dynamic: expands as modules are added.
        """
        dash_frame = tk.Frame(self._root, bg=BG_PANEL,
                               highlightthickness=1, highlightbackground=BORDER,
                               height=280)
        dash_frame.pack(fill=tk.X, padx=PAD, pady=(PAD, 0))
        dash_frame.pack_propagate(False)

        self._adaptive_dashboard = AdaptiveDashboard(
            dash_frame,
            on_dispatch=self._on_capability_dispatch,
        )
        self._adaptive_dashboard.pack(fill=tk.BOTH, expand=True)

    def _build_panel_grid(self):
        grid = tk.Frame(self._root, bg=BG_DARK)
        grid.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=PAD)

        # Row 0: 3 columns
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="col")
        # Row 1: 4 columns (ecosystem gets extra space)
        grid.rowconfigure(0, weight=1, uniform="row")
        grid.rowconfigure(1, weight=1, uniform="row")

        def pf(row, col, colspan=1):
            f = tk.Frame(grid, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER)
            f.grid(row=row, column=col, columnspan=colspan,
                   sticky="nsew", padx=3, pady=3)
            return f

        # Row 0: Module Status | Capability Status | Intent Routing
        self._module_status = ModuleStatusPanel(pf(0, 0))
        self._module_status.pack(fill=tk.BOTH, expand=True)

        self._capability_status = CapabilityStatusPanel(pf(0, 1))
        self._capability_status.pack(fill=tk.BOTH, expand=True)

        self._intent_routing = IntentRoutingPanel(pf(0, 2))
        self._intent_routing.pack(fill=tk.BOTH, expand=True)

        # Row 1: Environment | Database Monitor | Watchdog | Ecosystem (spans 1)
        # Use a 4-column sub-grid for row 1
        row1 = tk.Frame(grid, bg=BG_DARK)
        row1.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=0, pady=0)
        for c in range(4):
            row1.columnconfigure(c, weight=1, uniform="r1col")
        row1.rowconfigure(0, weight=1)

        def pf1(col, colspan=1):
            f = tk.Frame(row1, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER)
            f.grid(row=0, column=col, columnspan=colspan,
                   sticky="nsew", padx=3, pady=3)
            return f

        self._environment_panel = EnvironmentPanel(pf1(0))
        self._environment_panel.pack(fill=tk.BOTH, expand=True)

        self._database_monitor = DatabaseMonitorPanel(pf1(1))
        self._database_monitor.pack(fill=tk.BOTH, expand=True)

        self._watchdog_panel = WatchDogPanel(pf1(2))
        self._watchdog_panel.pack(fill=tk.BOTH, expand=True)

        self._ecosystem_panel = EcosystemPanel(pf1(3))
        self._ecosystem_panel.pack(fill=tk.BOTH, expand=True)

    def _build_event_log(self):
        tk.Frame(self._root, bg=BORDER, height=1).pack(fill=tk.X, padx=PAD)
        log_frame = tk.Frame(self._root, bg=BG_PANEL,
                              highlightthickness=1, highlightbackground=BORDER,
                              height=160)
        log_frame.pack(fill=tk.X, padx=PAD, pady=(0, PAD))
        log_frame.pack_propagate(False)
        self._event_log = EventLogPanel(log_frame)
        self._event_log.pack(fill=tk.BOTH, expand=True)

    # ── Event Bus ─────────────────────────────────────────────────────────

    def _wire_event_bus(self):
        bus.subscribe(self._on_bus_event)

    def _on_bus_event(self, event: SystemEvent):
        """Thread-safe handoff: Tk updates must run on the main thread."""
        self._event_queue.put(event)

    def _drain_event_queue(self):
        try:
            while True:
                ev = self._event_queue.get_nowait()
                self._event_log.append(ev)
        except queue.Empty:
            pass
        if self._root is not None:
            self._root.after(32, self._drain_event_queue)

    # ── WatchDog ──────────────────────────────────────────────────────────

    def _wire_watchdog(self):
        from core.capability_expansion import expansion_system, add_capability_listener
        from core.database_manager import add_remove_listener
        from core.intent_manager import intent_manager

        def on_change(event_type, path, module_id):
            intent_manager.on_watchdog_change(event_type, path, module_id)
            expansion_system.on_watchdog_change(event_type, path, module_id)
            self._root.after(0, self._watchdog_panel.add_event,
                              event_type, path, module_id or "")
            self._root.after(0, self._database_monitor.record_change,
                              event_type, path, module_id or "")

        watchdog.on("any_change", on_change)
        watchdog.start()

        # Immediate refresh when capabilities change
        def on_capability_change():
            self._root.after(0, self._capability_status.refresh)
            self._root.after(0, self._intent_routing.refresh)

        add_capability_listener(on_capability_change)

        # Immediate refresh when a module is removed
        def on_module_removed(module_id: str):
            self._root.after(0, self._capability_status.refresh)
            self._root.after(0, self._intent_routing.refresh)
            self._root.after(0, self._environment_panel.refresh)
            self._root.after(0, self._database_monitor.refresh)

        add_remove_listener(on_module_removed)

    # ── UI Adaptation Engine wiring ───────────────────────────────────────

    def _wire_ui_engine(self):
        """
        Connect UIAdaptationEngine + OrchestrationEngine callbacks to GUI.
        All calls are marshalled to the Tk main thread via after().
        """
        def on_added(module_id: str, descriptor: dict):
            self._root.after(0, self._adaptive_dashboard.add_module,
                              module_id, descriptor)

        def on_updated(module_id: str, descriptor: dict):
            self._root.after(0, self._adaptive_dashboard.update_module,
                              module_id, descriptor)

        def on_removed(module_id: str):
            self._root.after(0, self._adaptive_dashboard.remove_module, module_id)

        ui_engine.on_module_added(on_added)
        ui_engine.on_module_updated(on_updated)
        ui_engine.on_module_removed(on_removed)

        # Orchestration engine: synergy discovery → refresh ecosystem panel
        def on_synergy(synergies):
            self._root.after(0, self._ecosystem_panel.refresh)
            # Also re-register modules involved to update their descriptors
            for syn in synergies:
                for mid in (syn.module_a, syn.module_b):
                    self._root.after(50, ui_engine.register_module, mid)

        def on_rebalance():
            self._root.after(0, self._ecosystem_panel.refresh)

        orchestration_engine.on_synergy(on_synergy)
        orchestration_engine.on_rebalance(on_rebalance)

    def _sync_on_startup(self):
        """
        On startup, rebuild UI descriptors for any modules already in DATABASE.
        This handles the case where the app is restarted with existing data.
        """
        ui_engine.refresh_all()

    # ── Panel Refresh ─────────────────────────────────────────────────────

    def _schedule_panel_refresh(self):
        self._refresh_panels()
        self._root.after(500, self._schedule_panel_refresh)

    def _refresh_panels(self):
        try:
            self._capability_status.refresh()
            self._intent_routing.refresh()
            self._environment_panel.refresh()
            self._database_monitor.refresh()
        except Exception as e:
            bus.emit("CENTRAL SYSTEM",
                     f"⚠️  Panel refresh error: {e}",
                     Severity.WARNING)
    # ── Module Lifecycle Handlers ─────────────────────────────────────────

    def _on_module_dropped(self, path: Path):
        from core.pipeline_orchestrator import process_module

        async def run():
            module_id = await process_module(path)
            rec = registry.get(module_id)
            if rec:
                if rec.stage == ModuleStage.ONLINE:
                    self._root.after(0, self._mgmt_panel.set_status,
                                      f"🟢  ONLINE: {rec.name}", TEXT_SUCCESS)
                else:
                    self._root.after(0, self._mgmt_panel.set_status,
                                      f"🔴  {rec.stage.value}: {rec.name}", "#f85149")

        asyncio.run_coroutine_threadsafe(run(), self._loop)

    def _on_module_stop(self, module_id: str):
        rec = registry.get(module_id)
        if rec:
            registry.stop(module_id)
            # Remove from adaptive dashboard immediately
            self._root.after(0, self._adaptive_dashboard.remove_module, module_id)
            # Unregister from UI engine
            ui_engine.unregister_module(module_id)
            bus.emit("CENTRAL SYSTEM",
                      f"⏹️  Module stopped: {rec.name}",
                      module_id=module_id)

    def _on_module_remove(self, module_id: str):
        from core.database_manager import remove_module

        rec = registry.get(module_id)
        name = rec.name if rec else module_id

        # Remove from in-memory registry
        registry.remove(module_id)

        # Full DATABASE cascade removal
        # (also calls ui_engine.unregister_module → fires on_removed → removes dashboard panel)
        remove_module(module_id)

        bus.emit("CENTRAL SYSTEM",
                  f"✕  Module fully removed: {name}",
                  module_id=module_id)

    def _on_capability_dispatch(self, module_id: str, intent_label: str, payload: Any):
        """
        Called when user clicks Run on a capability control.
        Dispatches through the intent router.
        """
        from core.intent_router import intent_router
        result = intent_router.dispatch(intent_label, payload)
        bus.emit("CENTRAL SYSTEM",
                  f"📤  Dispatched '{intent_label}' → {result.get('action', '?')}",
                  module_id=module_id)

    # ── Shutdown ──────────────────────────────────────────────────────────

    def _shutdown(self):
        watchdog.stop()
        pipeline.stop()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)
