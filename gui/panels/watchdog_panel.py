"""
WatchDog Activity Panel — shows raw monitoring events as they occur.
"""
import tkinter as tk
from collections import deque
from pathlib import Path
from typing import Deque, Tuple

from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, FONT_HEADER, FONT_MONO, FONT_MONO_S,
    PAD, PAD_S, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_SUCCESS,
    TEXT_WARNING, TEXT_ERROR,
)


class WatchDogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._events: Deque[Tuple[str, str, str, str]] = deque(maxlen=50)
        self._build()

    def _build(self):
        header = tk.Label(self, text="WATCHDOG ACTIVITY", font=FONT_HEADER,
                          bg=BG_PANEL, fg=ACCENT_BLUE)
        header.pack(anchor="w", padx=PAD, pady=(PAD, PAD_S))

        container = tk.Frame(self, bg=BG_PANEL)
        container.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))

        self._text = tk.Text(
            container,
            bg=BG_PANEL,
            fg=TEXT_SECONDARY,
            font=FONT_MONO_S,
            state=tk.DISABLED,
            wrap=tk.WORD,
            relief=tk.FLAT,
            highlightthickness=0,
            insertbackground=TEXT_PRIMARY,
        )
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                  command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure tags
        self._text.tag_configure("created",  foreground=TEXT_SUCCESS)
        self._text.tag_configure("modified", foreground=TEXT_WARNING)
        self._text.tag_configure("deleted",  foreground=TEXT_ERROR)
        self._text.tag_configure("ts",       foreground=TEXT_MUTED)
        self._text.tag_configure("path",     foreground=TEXT_SECONDARY)

        self._append_line("👁️  WatchDog monitoring initialized", "ts")

    def add_event(self, event_type: str, path: Path, module_id: str):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._events.append((ts, event_type, str(path.name), module_id or ""))
        self._render_event(ts, event_type, path.name, module_id or "")

    def _render_event(self, ts: str, event_type: str, fname: str, module_id: str):
        self._text.configure(state=tk.NORMAL)
        tag = event_type if event_type in ("created", "modified", "deleted") else "path"
        self._text.insert(tk.END, f"[{ts}] ", "ts")
        self._text.insert(tk.END, f"{event_type:<10}", tag)
        self._text.insert(tk.END, f" {fname}\n", "path")
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    def _append_line(self, text: str, tag: str = "path"):
        self._text.configure(state=tk.NORMAL)
        self._text.insert(tk.END, text + "\n", tag)
        self._text.configure(state=tk.DISABLED)
