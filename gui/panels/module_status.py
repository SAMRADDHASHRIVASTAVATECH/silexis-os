"""
Module Status Panel — shows lifecycle stage of every loaded module.
"""
import tkinter as tk
from tkinter import ttk
from typing import List

from core.module_state import ModuleRecord, ModuleStage, registry
from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, BORDER, FONT_HEADER, FONT_MONO,
    FONT_MONO_S, FONT_SMALL, PAD, PAD_S, STAGE_COLORS, TEXT_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY,
)


class ModuleStatusPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._build()
        registry.add_listener(self._refresh)

    def _build(self):
        header = tk.Label(self, text="MODULE STATUS", font=FONT_HEADER,
                          bg=BG_PANEL, fg=ACCENT_BLUE)
        header.pack(anchor="w", padx=PAD, pady=(PAD, PAD_S))

        # Scrollable list
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

        self._empty_label = tk.Label(
            self._inner, text="No modules loaded",
            font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED
        )
        self._empty_label.pack(pady=10)

    def _refresh(self):
        for widget in self._inner.winfo_children():
            widget.destroy()

        modules = registry.all()
        if not modules:
            tk.Label(self._inner, text="No modules loaded",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)
            return

        for mod in modules:
            self._render_module_row(mod)

    def _render_module_row(self, mod: ModuleRecord):
        stage_color = STAGE_COLORS.get(mod.stage.value, TEXT_SECONDARY)

        row = tk.Frame(self._inner, bg=BG_PANEL_ALT,
                       highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill=tk.X, pady=2, padx=2)

        # Icon + stage
        icon_label = tk.Label(row, text=mod.stage_icon, font=("Segoe UI Emoji", 12),
                               bg=BG_PANEL_ALT)
        icon_label.pack(side=tk.LEFT, padx=(PAD, 2), pady=PAD_S)

        info_frame = tk.Frame(row, bg=BG_PANEL_ALT)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=PAD_S)

        name_label = tk.Label(info_frame, text=mod.name, font=FONT_MONO,
                               bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, anchor="w")
        name_label.pack(anchor="w")

        detail = f"ID: {mod.module_id}  |  {mod.stage.value}"
        if mod.environment:
            detail += f"  |  env: {mod.environment}"
        detail_label = tk.Label(info_frame, text=detail, font=FONT_MONO_S,
                                 bg=BG_PANEL_ALT, fg=stage_color, anchor="w")
        detail_label.pack(anchor="w")

        if mod.error:
            err_label = tk.Label(info_frame, text=f"⚠ {mod.error[:60]}",
                                  font=FONT_MONO_S, bg=BG_PANEL_ALT,
                                  fg=STAGE_COLORS["FAILED"], anchor="w")
            err_label.pack(anchor="w")

        if mod.capabilities:
            cap_text = f"Caps: {len(mod.capabilities)}"
            tk.Label(row, text=cap_text, font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD)
