"""
Intent Routing Panel — shows active routing links and recent dispatches.
"""
import tkinter as tk
from typing import Dict

from core.intent_router import intent_router
from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, BORDER, FONT_HEADER, FONT_MONO,
    FONT_MONO_S, PAD, PAD_S, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_SUCCESS, TEXT_INFO,
)


class IntentRoutingPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._build()

    def _build(self):
        header = tk.Label(self, text="INTENT ROUTING", font=FONT_HEADER,
                          bg=BG_PANEL, fg=ACCENT_BLUE)
        header.pack(anchor="w", padx=PAD, pady=(PAD, PAD_S))

        container = tk.Frame(self, bg=BG_PANEL)
        container.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))

        self._canvas = tk.Canvas(container, bg=BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                  command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=BG_PANEL)
        self._inner.bind("<Configure>",
                          lambda e: self._canvas.configure(
                              scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self._inner, text="No routes established",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)

    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()

        routes = intent_router.get_active_routes()
        log = intent_router.get_routing_log()

        if not routes:
            tk.Label(self._inner, text="No routes established",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)
            return

        tk.Label(self._inner, text=f"Active Routes ({len(routes)})",
                 font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(2, 0))

        for intent, route in list(routes.items())[:20]:
            row = tk.Frame(self._inner, bg=BG_PANEL_ALT)
            row.pack(fill=tk.X, pady=1, padx=2)
            tk.Label(row, text=f"  ↔ {intent}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_INFO, anchor="w", width=22).pack(side=tk.LEFT)
            tk.Label(row, text=f"→ {route['module_id']}.{route['action']}",
                     font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_SUCCESS,
                     anchor="w").pack(side=tk.LEFT)
            conf = route.get("confidence", 0)
            tk.Label(row, text=f"{conf:.0%}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD)

        if log:
            tk.Label(self._inner, text=f"Recent Dispatches ({len(log)})",
                     font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(6, 0))
            for entry in log[-5:]:
                tk.Label(self._inner,
                         text=f"  ▸ {entry['intent']} → {entry['module_id']}",
                         font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED,
                         anchor="w").pack(anchor="w")
