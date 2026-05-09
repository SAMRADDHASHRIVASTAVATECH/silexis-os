"""
Database Monitor Panel — shows DATABASE folder contents and recent changes.
"""
import json
import tkinter as tk
from pathlib import Path
from typing import List, Tuple

from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, BORDER, FONT_HEADER, FONT_MONO,
    FONT_MONO_S, PAD, PAD_S, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_SUCCESS, TEXT_WARNING,
)

DATABASE_ROOT = Path("DATABASE")


class DatabaseMonitorPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._recent_changes: List[Tuple[str, str, str]] = []  # (type, path, module_id)
        self._build()

    def _build(self):
        header = tk.Label(self, text="DATABASE MONITOR", font=FONT_HEADER,
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

        tk.Label(self._inner, text="DATABASE folder empty",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)

    def record_change(self, event_type: str, path: Path, module_id: str):
        """Called by WatchDog to record a change."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._recent_changes.append((event_type, str(path.name), module_id or "", ts))
        if len(self._recent_changes) > 30:
            self._recent_changes = self._recent_changes[-30:]

    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()

        # Show index summary
        index_path = DATABASE_ROOT / "index.json"
        if index_path.exists():
            try:
                with open(index_path) as f:
                    index = json.load(f)
                tk.Label(self._inner,
                         text=f"Registered Modules ({len(index)})",
                         font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(2, 0))
                for mod_id, info in index.items():
                    row = tk.Frame(self._inner, bg=BG_PANEL_ALT)
                    row.pack(fill=tk.X, pady=1, padx=2)
                    tk.Label(row, text=f"  📦 {info.get('name', mod_id)[:20]}",
                             font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                             anchor="w", width=22).pack(side=tk.LEFT)
                    tk.Label(row, text=f"v{info.get('version', '?')}",
                             font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.LEFT)
                    tk.Label(row, text=info.get("purpose", ""),
                             font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_SECONDARY).pack(side=tk.RIGHT, padx=PAD)
            except Exception:
                pass
        else:
            tk.Label(self._inner, text="DATABASE folder empty",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)

        # Show recent changes
        if self._recent_changes:
            tk.Label(self._inner, text="Recent Changes",
                     font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor="w", pady=(6, 0))
            for event_type, fname, mod_id, ts in self._recent_changes[-8:]:
                color = TEXT_SUCCESS if event_type == "created" else TEXT_WARNING
                row = tk.Frame(self._inner, bg=BG_PANEL_ALT)
                row.pack(fill=tk.X, pady=1, padx=2)
                tk.Label(row, text=f"  {ts}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=TEXT_MUTED, width=10).pack(side=tk.LEFT)
                tk.Label(row, text=f"{event_type[:8]}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=color, width=10).pack(side=tk.LEFT)
                tk.Label(row, text=fname[:30], font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=TEXT_SECONDARY).pack(side=tk.LEFT)
