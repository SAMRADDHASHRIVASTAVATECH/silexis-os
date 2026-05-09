"""
Live Event Log — timestamped record of all system events from all components.
"""
import tkinter as tk
from collections import deque
from typing import Deque

from core.event_bus import SystemEvent, Severity
from gui.styles import (
    BG_PANEL, FONT_MONO_S, PAD, PAD_S, SEVERITY_COLORS, TEXT_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, FONT_HEADER,
)


class EventLogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._events: Deque[SystemEvent] = deque(maxlen=500)
        self._auto_scroll = True
        self._build()

    def _build(self):
        # Header row
        header_row = tk.Frame(self, bg=BG_PANEL)
        header_row.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_S))

        tk.Label(header_row, text="LIVE EVENT LOG", font=FONT_HEADER,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(side=tk.LEFT)

        # Auto-scroll toggle
        self._scroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            header_row, text="Auto-scroll", variable=self._scroll_var,
            bg=BG_PANEL, fg=TEXT_MUTED, selectcolor=BG_PANEL,
            activebackground=BG_PANEL, activeforeground=TEXT_SECONDARY,
            font=FONT_MONO_S,
            command=lambda: setattr(self, "_auto_scroll", self._scroll_var.get()),
        ).pack(side=tk.RIGHT)

        # Clear button
        tk.Button(
            header_row, text="Clear", font=FONT_MONO_S,
            bg=BG_PANEL, fg=TEXT_MUTED, relief=tk.FLAT,
            activebackground=BG_PANEL, activeforeground=TEXT_PRIMARY,
            command=self._clear,
        ).pack(side=tk.RIGHT, padx=PAD)

        # Text widget
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
        )
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                  command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Tags for severity
        for sev, color in SEVERITY_COLORS.items():
            self._text.tag_configure(sev, foreground=color)
        self._text.tag_configure("TS",        foreground=TEXT_MUTED)
        self._text.tag_configure("COMPONENT", foreground="#58a6ff")
        self._text.tag_configure("MODULE",    foreground="#bc8cff")

    def append(self, event: SystemEvent):
        self._events.append(event)
        self._text.configure(state=tk.NORMAL)

        # Timestamp
        self._text.insert(tk.END, f"[{event.formatted_time}] ", "TS")
        # Component
        comp = f"{event.component:<22}"
        self._text.insert(tk.END, comp, "COMPONENT")
        # Module ID if present
        if event.module_id:
            self._text.insert(tk.END, f"[{event.module_id}] ", "MODULE")
        # Description
        self._text.insert(tk.END, f"{event.description}\n", event.severity.value)

        if self._auto_scroll:
            self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    def _clear(self):
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.configure(state=tk.DISABLED)
        self._events.clear()
