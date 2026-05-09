"""
Environment Panel — shows which environments are active and assigned.
"""
import json
import tkinter as tk
from pathlib import Path

from core.module_state import registry
from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, BORDER, FONT_HEADER, FONT_MONO,
    FONT_MONO_S, PAD, PAD_S, STAGE_COLORS, TEXT_MUTED, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_SUCCESS,
)

DATABASE_ROOT = Path("DATABASE")
ENVIRONMENTS_ROOT = Path("ENVIRONMENTS")


class EnvironmentPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._build()

    def _build(self):
        header = tk.Label(self, text="ENVIRONMENT", font=FONT_HEADER,
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

        tk.Label(self._inner, text="No environments active",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)

    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()

        env_map_path = DATABASE_ROOT / "environments" / "environment_map.json"
        env_map = {}
        if env_map_path.exists():
            try:
                with open(env_map_path) as f:
                    env_map = json.load(f)
            except Exception:
                pass

        modules = registry.all()
        active = {m.module_id: m for m in modules if m.environment}

        if not active and not env_map:
            tk.Label(self._inner, text="No environments active",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)
            return

        # Show available environments
        env_index_path = ENVIRONMENTS_ROOT / "index.json"
        env_index = {}
        if env_index_path.exists():
            try:
                with open(env_index_path) as f:
                    env_index = json.load(f)
            except Exception:
                pass

        tk.Label(self._inner, text="Available Environments",
                 font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(2, 0))

        for env_name, env_meta in env_index.items():
            is_active = env_name in env_map.values()
            color = TEXT_SUCCESS if is_active else TEXT_MUTED
            status = "⚡ ACTIVE" if is_active else "○ idle"
            row = tk.Frame(self._inner, bg=BG_PANEL_ALT)
            row.pack(fill=tk.X, pady=1, padx=2)
            tk.Label(row, text=f"  {env_name}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=color, anchor="w", width=18).pack(side=tk.LEFT)
            hw = env_meta.get("hardware", "cpu")
            tk.Label(row, text=f"[{hw}]", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.LEFT)
            tk.Label(row, text=status, font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=color).pack(side=tk.RIGHT, padx=PAD)

        if active:
            tk.Label(self._inner, text="Module Assignments",
                     font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(6, 0))
            for mod_id, mod in active.items():
                row = tk.Frame(self._inner, bg=BG_PANEL_ALT)
                row.pack(fill=tk.X, pady=1, padx=2)
                tk.Label(row, text=f"  {mod.name[:18]}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, anchor="w", width=20).pack(side=tk.LEFT)
                tk.Label(row, text=f"→ {mod.environment}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=TEXT_SUCCESS).pack(side=tk.LEFT)
