"""
Ecosystem Panel — the live self-organizing world map.

Shows:
  • All occupied slots with their assigned modules (game inventory view)
  • Active synergy links between modules
  • Ecosystem health stats
  • Connection graph (text-based)

Updates instantly whenever the ecosystem changes.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from core.ecosystem_registry import (
    SlotType, SLOT_ICONS, ecosystem
)
from gui.styles import (
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_PURPLE,
    BG_PANEL, BG_PANEL_ALT, BG_HEADER, BORDER,
    FONT_HEADER, FONT_MONO, FONT_MONO_S, FONT_SMALL,
    PAD, PAD_S,
    TEXT_ERROR, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_SUCCESS, TEXT_WARNING, TEXT_INFO,
)

# Slot category groupings for display
SLOT_GROUPS = {
    "🔬 Processing": [
        SlotType.TEXT_PROCESSOR, SlotType.IMAGE_PROCESSOR,
        SlotType.DATA_PROCESSOR, SlotType.AUDIO_PROCESSOR,
    ],
    "🧠 Intelligence": [
        SlotType.CLASSIFIER, SlotType.GENERATOR,
        SlotType.EMBEDDER, SlotType.REASONER,
    ],
    "🌐 Services": [
        SlotType.API_GATEWAY, SlotType.DATA_STORE,
        SlotType.MESSAGE_BROKER, SlotType.SCHEDULER,
    ],
    "🏗️ Infrastructure": [
        SlotType.MONITOR, SlotType.LOGGER,
        SlotType.AUTHENTICATOR, SlotType.CACHE,
    ],
    "🔧 Utilities": [
        SlotType.FORMATTER, SlotType.VALIDATOR,
        SlotType.TRANSFORMER, SlotType.UTILITY,
    ],
}


class EcosystemPanel(tk.Frame):
    """
    Live ecosystem world map — shows slots, synergies, and connections.
    Rebuilds whenever the ecosystem changes.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._last_hash = ""
        self._build()
        # Subscribe to ecosystem changes
        ecosystem.on_change(self._on_ecosystem_change)

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG_PANEL)
        hdr.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_S))
        tk.Label(hdr, text="🌍  ECOSYSTEM", font=FONT_HEADER,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(side=tk.LEFT)
        self._stats_var = tk.StringVar(value="")
        tk.Label(hdr, textvariable=self._stats_var, font=FONT_MONO_S,
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(side=tk.RIGHT)

        # Notebook: Slots | Synergies | Graph
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))

        style = ttk.Style()
        style.configure("Eco.TNotebook", background=BG_PANEL, borderwidth=0)
        style.configure("Eco.TNotebook.Tab",
                        background=BG_PANEL_ALT, foreground=TEXT_MUTED,
                        padding=[PAD, 2], font=("Consolas", 8))
        style.map("Eco.TNotebook.Tab",
                  background=[("selected", BG_PANEL)],
                  foreground=[("selected", TEXT_PRIMARY)])
        self._nb.configure(style="Eco.TNotebook")

        # Tab 1: Slots
        self._slots_frame = tk.Frame(self._nb, bg=BG_PANEL)
        self._nb.add(self._slots_frame, text="⬡ Slots")
        self._slots_canvas = self._make_scrollable(self._slots_frame)

        # Tab 2: Synergies
        self._syn_frame = tk.Frame(self._nb, bg=BG_PANEL)
        self._nb.add(self._syn_frame, text="⚡ Synergies")
        self._syn_canvas = self._make_scrollable(self._syn_frame)

        # Tab 3: Graph
        self._graph_frame = tk.Frame(self._nb, bg=BG_PANEL)
        self._nb.add(self._graph_frame, text="🕸 Graph")
        self._graph_canvas = self._make_scrollable(self._graph_frame)

        self._render_empty()

    def _make_scrollable(self, parent: tk.Frame) -> tk.Frame:
        """Create a scrollable inner frame inside parent. Returns the inner frame."""
        container = tk.Frame(parent, bg=BG_PANEL)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(container, bg=BG_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_PANEL)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return inner

    def _render_empty(self):
        tk.Label(self._slots_canvas, text="No modules in ecosystem",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)
        tk.Label(self._syn_canvas, text="No synergies detected",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)
        tk.Label(self._graph_canvas, text="Graph empty",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)

    def _on_ecosystem_change(self):
        """Called by ecosystem registry when state changes."""
        self.refresh()

    def refresh(self):
        """Rebuild all three tabs from current ecosystem state."""
        stats = ecosystem.get_ecosystem_stats()
        self._stats_var.set(
            f"{stats['total_modules']} modules · "
            f"{stats['slot_coverage']} slots · "
            f"{stats['total_synergies']} synergies"
        )
        self._render_slots()
        self._render_synergies()
        self._render_graph()

    # ── Slots tab ─────────────────────────────────────────────────────────

    def _render_slots(self):
        for w in self._slots_canvas.winfo_children():
            w.destroy()

        occupied = ecosystem.get_occupied_slots()
        if not occupied:
            tk.Label(self._slots_canvas, text="No slots occupied",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)
            return

        for group_name, slot_types in SLOT_GROUPS.items():
            group_slots = {st: occupied[st] for st in slot_types if st in occupied}
            if not group_slots:
                continue

            # Group header
            tk.Label(self._slots_canvas, text=group_name,
                     font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY,
                     anchor="w").pack(anchor="w", padx=PAD, pady=(PAD_S, 0))

            for slot_type, slots in group_slots.items():
                icon = SLOT_ICONS.get(slot_type, "?")
                for slot in slots:
                    row = tk.Frame(self._slots_canvas, bg=BG_PANEL_ALT,
                                   highlightthickness=1, highlightbackground=BORDER)
                    row.pack(fill=tk.X, padx=PAD * 2, pady=1)

                    # Slot icon + type
                    tk.Label(row, text=f"  {icon}", font=("Segoe UI Emoji", 10),
                             bg=BG_PANEL_ALT).pack(side=tk.LEFT, padx=(PAD_S, 2))
                    tk.Label(row, text=slot_type.value, font=FONT_MONO_S,
                             bg=BG_PANEL_ALT, fg=TEXT_MUTED,
                             width=18, anchor="w").pack(side=tk.LEFT)

                    # Module name
                    tk.Label(row, text=slot.module_name[:20], font=FONT_MONO_S,
                             bg=BG_PANEL_ALT, fg=TEXT_SUCCESS,
                             anchor="w").pack(side=tk.LEFT, padx=PAD_S)

                    # Confidence
                    conf_color = TEXT_SUCCESS if slot.confidence > 0.7 else TEXT_WARNING
                    tk.Label(row, text=f"{slot.confidence:.0%}",
                             font=FONT_MONO_S, bg=BG_PANEL_ALT,
                             fg=conf_color).pack(side=tk.RIGHT, padx=PAD)

    # ── Synergies tab ─────────────────────────────────────────────────────

    def _render_synergies(self):
        for w in self._syn_canvas.winfo_children():
            w.destroy()

        synergies = ecosystem.get_all_synergies()
        if not synergies:
            tk.Label(self._syn_canvas,
                     text="No synergies yet.\nLoad multiple modules to discover connections.",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED,
                     justify=tk.LEFT).pack(pady=PAD, padx=PAD)
            return

        tk.Label(self._syn_canvas,
                 text=f"Active Synergies ({len(synergies)})",
                 font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(
            anchor="w", padx=PAD, pady=(PAD_S, 0))

        for syn in synergies:
            node_a = ecosystem.get_node(syn.module_a)
            node_b = ecosystem.get_node(syn.module_b)
            name_a = node_a.module_name if node_a else syn.module_a[:8]
            name_b = node_b.module_name if node_b else syn.module_b[:8]

            card = tk.Frame(self._syn_canvas, bg=BG_PANEL_ALT,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(fill=tk.X, padx=PAD, pady=2)

            # Synergy name
            tk.Label(card, text=f"  ⚡ {syn.name}", font=FONT_MONO,
                     bg=BG_PANEL_ALT, fg=ACCENT_ORANGE,
                     anchor="w").pack(anchor="w", padx=PAD_S, pady=(PAD_S, 0))

            # Description
            tk.Label(card, text=f"  {syn.description}",
                     font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w", padx=PAD_S)

            # Connection
            conn_row = tk.Frame(card, bg=BG_PANEL_ALT)
            conn_row.pack(fill=tk.X, padx=PAD_S, pady=(0, PAD_S))
            tk.Label(conn_row, text=f"  {name_a[:16]}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_SUCCESS).pack(side=tk.LEFT)
            tk.Label(conn_row, text=" ↔ ", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=ACCENT_ORANGE).pack(side=tk.LEFT)
            tk.Label(conn_row, text=f"{name_b[:16]}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_SUCCESS).pack(side=tk.LEFT)
            tk.Label(conn_row, text=f"strength: {syn.strength:.0%}",
                     font=FONT_MONO_S, bg=BG_PANEL_ALT,
                     fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD)

    # ── Graph tab ─────────────────────────────────────────────────────────

    def _render_graph(self):
        for w in self._graph_canvas.winfo_children():
            w.destroy()

        nodes = ecosystem.get_all_nodes()
        if not nodes:
            tk.Label(self._graph_canvas, text="Graph empty",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)
            return

        tk.Label(self._graph_canvas,
                 text=f"Ecosystem Graph ({len(nodes)} nodes)",
                 font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(
            anchor="w", padx=PAD, pady=(PAD_S, 0))

        for module_id, node in nodes.items():
            node_frame = tk.Frame(self._graph_canvas, bg=BG_PANEL_ALT,
                                   highlightthickness=1, highlightbackground=BORDER)
            node_frame.pack(fill=tk.X, padx=PAD, pady=2)

            # Node header
            hdr_row = tk.Frame(node_frame, bg=BG_PANEL_ALT)
            hdr_row.pack(fill=tk.X, padx=PAD_S, pady=(PAD_S, 0))

            slot_icons = " ".join(SLOT_ICONS.get(s, "?") for s in node.slots[:3])
            tk.Label(hdr_row, text=f"{slot_icons}  {node.module_name[:20]}",
                     font=FONT_MONO, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(hdr_row, text=f"[{module_id}]",
                     font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.RIGHT)

            # Connections
            if node.connections:
                conn_frame = tk.Frame(node_frame, bg=BG_PANEL_ALT)
                conn_frame.pack(fill=tk.X, padx=PAD_S * 3, pady=(0, PAD_S))
                for conn_id in node.connections:
                    conn_node = ecosystem.get_node(conn_id)
                    conn_name = conn_node.module_name if conn_node else conn_id[:8]
                    tk.Label(conn_frame, text=f"  └─ {conn_name}",
                             font=FONT_MONO_S, bg=BG_PANEL_ALT,
                             fg=TEXT_INFO, anchor="w").pack(anchor="w")
            else:
                tk.Label(node_frame, text="  └─ (no connections yet)",
                         font=FONT_MONO_S, bg=BG_PANEL_ALT,
                         fg=TEXT_MUTED, anchor="w").pack(anchor="w", padx=PAD_S, pady=(0, PAD_S))
