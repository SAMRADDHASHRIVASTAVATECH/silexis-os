"""
Drag-and-Drop Module Area panel.
Accepts folder drops and triggers the pipeline.
"""
import asyncio
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Optional

from gui.styles import (
    ACCENT_BLUE, BG_DROP, BG_DROP_HOVER, BG_PANEL, BORDER, BORDER_ACCENT,
    FONT_BODY, FONT_HEADER, FONT_MONO, PAD, TEXT_MUTED, TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class DropArea(tk.Frame):
    """
    Visual drop zone. On Windows, uses a Browse button as fallback
    since native folder DnD requires tkinterdnd2.
    Attempts to use tkinterdnd2 if available.
    """

    def __init__(self, parent, on_module_dropped: Callable[[Path], None], **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._on_drop = on_module_dropped
        self._hover = False
        self._build()
        self._try_enable_dnd()

    def _build(self):
        # Header
        header = tk.Label(
            self,
            text="DRAG AND DROP MODULE AREA",
            font=FONT_HEADER,
            bg=BG_PANEL,
            fg=ACCENT_BLUE,
        )
        header.pack(pady=(PAD, 2))

        # Drop zone canvas
        self._canvas = tk.Canvas(
            self,
            bg=BG_DROP,
            highlightthickness=2,
            highlightbackground=BORDER,
            height=90,
            cursor="hand2",
        )
        self._canvas.pack(fill=tk.X, padx=PAD, pady=(0, PAD))
        self._canvas.bind("<Configure>", self._redraw)
        self._canvas.bind("<Button-1>", self._browse_folder)
        self._canvas.bind("<Enter>", self._on_enter)
        self._canvas.bind("<Leave>", self._on_leave)

        # Status label
        self._status_var = tk.StringVar(value="")
        self._status_label = tk.Label(
            self,
            textvariable=self._status_var,
            font=FONT_MONO,
            bg=BG_PANEL,
            fg=TEXT_SECONDARY,
            wraplength=500,
        )
        self._status_label.pack(pady=(0, PAD))

    def _redraw(self, event=None):
        self._canvas.delete("all")
        w = self._canvas.winfo_width() or 400
        h = self._canvas.winfo_height() or 90

        bg = BG_DROP_HOVER if self._hover else BG_DROP
        self._canvas.configure(bg=bg)

        # Dashed border
        dash = (6, 4)
        border_color = BORDER_ACCENT if self._hover else BORDER
        self._canvas.create_rectangle(8, 8, w - 8, h - 8,
                                       outline=border_color, dash=dash, width=2)

        # Icon
        self._canvas.create_text(w // 2, h // 2 - 14,
                                  text="📂", font=("Segoe UI Emoji", 20),
                                  fill=TEXT_PRIMARY)
        # Text
        self._canvas.create_text(w // 2, h // 2 + 14,
                                  text="Drop full module folder here  —  or click to browse",
                                  font=FONT_BODY, fill=TEXT_SECONDARY)

    def _on_enter(self, event):
        self._hover = True
        self._redraw()
        self._canvas.configure(highlightbackground=BORDER_ACCENT)

    def _on_leave(self, event):
        self._hover = False
        self._redraw()
        self._canvas.configure(highlightbackground=BORDER)

    def _browse_folder(self, event=None):
        folder = filedialog.askdirectory(title="Select Module Folder")
        if folder:
            self._accept(Path(folder))

    def _accept(self, path: Path):
        self._status_var.set(f"📂  Accepted: {path.name}")
        self._status_label.configure(fg=ACCENT_BLUE)
        self._on_drop(path)

    def _try_enable_dnd(self):
        """Try to enable native drag-and-drop via tkinterdnd2."""
        try:
            from tkinterdnd2 import DND_FILES
            self._canvas.drop_target_register(DND_FILES)
            self._canvas.dnd_bind("<<Drop>>", self._on_dnd_drop)
            self._canvas.dnd_bind("<<DragEnter>>", lambda e: self._on_enter(e))
            self._canvas.dnd_bind("<<DragLeave>>", lambda e: self._on_leave(e))
        except Exception:
            pass  # tkinterdnd2 not available — browse button is the fallback

    def _on_dnd_drop(self, event):
        raw = event.data.strip()
        # tkinterdnd2 wraps paths with braces on Windows
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = Path(raw)
        if path.is_dir():
            self._accept(path)
        else:
            self._status_var.set(f"⚠️  Please drop a folder, not a file.")
            self._status_label.configure(fg="#d29922")

    def set_status(self, text: str, color: str = TEXT_SECONDARY):
        self._status_var.set(text)
        self._status_label.configure(fg=color)
