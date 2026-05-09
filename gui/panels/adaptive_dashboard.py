"""
Adaptive Dashboard — the live panel that hosts all DynamicModulePanels.

Behavior:
  • When a module goes ONLINE → a new DynamicModulePanel is created and
    added as a tab (or stacked card if only one module is active).
  • When a module's capabilities change → its panel rebuilds in place.
  • When a module is removed → its panel is destroyed immediately.
  • The dashboard is always visible and always reflects the exact current
    set of ONLINE modules with their full capability controls.

Layout:
  If 0 modules: shows a "waiting" placeholder.
  If 1 module:  fills the full dashboard area with that module's panel.
  If 2+ modules: uses a Notebook (tabbed) layout, one tab per module.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, Optional

from core.event_bus import Severity, bus
from gui.panels.dynamic_module_panel import DynamicModulePanel
from gui.styles import (
    ACCENT_BLUE, BG_DARK, BG_PANEL, BG_PANEL_ALT, BORDER,
    FONT_HEADER, FONT_MONO, FONT_MONO_S, PAD, PAD_S,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SUCCESS,
)


class AdaptiveDashboard(tk.Frame):
    """
    Container that dynamically creates, updates, and destroys
    DynamicModulePanel instances as modules come and go.
    """

    def __init__(self, parent,
                 on_dispatch: Callable[[str, str, Any], None],
                 **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._on_dispatch = on_dispatch
        self._panels: Dict[str, DynamicModulePanel] = {}   # module_id → panel
        self._notebook: Optional[ttk.Notebook] = None
        self._tab_ids: Dict[str, str] = {}                 # module_id → tab id
        self._build_empty()
        self._apply_notebook_style()

    # ── Style ─────────────────────────────────────────────────────────────

    def _apply_notebook_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Adaptive.TNotebook",
                        background=BG_PANEL,
                        borderwidth=0,
                        tabmargins=[0, 0, 0, 0])
        style.configure("Adaptive.TNotebook.Tab",
                        background=BG_PANEL_ALT,
                        foreground=TEXT_MUTED,
                        padding=[PAD, PAD_S],
                        font=("Consolas", 8))
        style.map("Adaptive.TNotebook.Tab",
                  background=[("selected", BG_PANEL)],
                  foreground=[("selected", TEXT_PRIMARY)])

    # ── Empty state ───────────────────────────────────────────────────────

    def _build_empty(self):
        self._placeholder = tk.Frame(self, bg=BG_PANEL)
        self._placeholder.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            self._placeholder,
            text="MODULE DASHBOARDS",
            font=FONT_HEADER, bg=BG_PANEL, fg=ACCENT_BLUE,
        ).pack(anchor="w", padx=PAD, pady=(PAD, PAD_S))
        tk.Label(
            self._placeholder,
            text="Drop a module to see its dashboard here.\n"
                 "Each ONLINE module gets its own live control panel\n"
                 "with interactive capability controls, workflows, and dispatch.",
            font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=PAD * 2, pady=PAD)

    def _hide_placeholder(self):
        if self._placeholder and self._placeholder.winfo_exists():
            self._placeholder.pack_forget()

    def _show_placeholder(self):
        if self._placeholder and self._placeholder.winfo_exists():
            self._placeholder.pack(fill=tk.BOTH, expand=True)

    # ── Notebook management ───────────────────────────────────────────────

    def _ensure_notebook(self):
        if self._notebook is None or not self._notebook.winfo_exists():
            self._notebook = ttk.Notebook(self, style="Adaptive.TNotebook")
            self._notebook.pack(fill=tk.BOTH, expand=True)

    def _destroy_notebook(self):
        if self._notebook and self._notebook.winfo_exists():
            self._notebook.destroy()
        self._notebook = None
        self._tab_ids.clear()

    # ── Public API — called by UIAdaptationEngine callbacks ───────────────

    def add_module(self, module_id: str, descriptor: Dict[str, Any]):
        """Create a new panel for a module that just went ONLINE."""
        if module_id in self._panels:
            # Already exists — update instead
            self.update_module(module_id, descriptor)
            return

        self._hide_placeholder()
        self._ensure_notebook()

        # Build the panel
        panel = DynamicModulePanel(
            self._notebook,
            descriptor=descriptor,
            on_dispatch=self._on_dispatch,
        )
        self._panels[module_id] = panel

        # Add as notebook tab
        icon  = descriptor.get("dashboard_icon", "📦")
        name  = descriptor.get("name", module_id)
        label = f"{icon} {name[:16]}"
        self._notebook.add(panel, text=label)
        self._tab_ids[module_id] = label

        # Select the new tab
        idx = list(self._panels.keys()).index(module_id)
        self._notebook.select(idx)

        bus.emit("UI ADAPTATION",
                 f"✨  Dashboard panel created: {name}",
                 Severity.SUCCESS, module_id=module_id)

    def update_module(self, module_id: str, descriptor: Dict[str, Any]):
        """Rebuild an existing panel with updated descriptor."""
        if module_id not in self._panels:
            self.add_module(module_id, descriptor)
            return

        panel = self._panels[module_id]
        panel.update_descriptor(descriptor)

        bus.emit("UI ADAPTATION",
                 f"🔄  Dashboard panel updated: {descriptor.get('name', module_id)}",
                 module_id=module_id)

    def remove_module(self, module_id: str):
        """Destroy the panel for a removed module."""
        if module_id not in self._panels:
            return

        panel = self._panels.pop(module_id)

        # Remove from notebook
        if self._notebook and self._notebook.winfo_exists():
            try:
                idx = list(self._tab_ids.keys()).index(module_id)
                self._notebook.forget(idx)
            except (ValueError, tk.TclError):
                pass

        self._tab_ids.pop(module_id, None)

        if panel.winfo_exists():
            panel.destroy()

        # If no panels left, destroy notebook and show placeholder
        if not self._panels:
            self._destroy_notebook()
            self._show_placeholder()

        bus.emit("UI ADAPTATION",
                 f"🗑️   Dashboard panel removed: {module_id}",
                 module_id=module_id)

    def get_panel(self, module_id: str) -> Optional[DynamicModulePanel]:
        return self._panels.get(module_id)

    def panel_count(self) -> int:
        return len(self._panels)
