"""
Module Management Panel — the top section of the GUI.

Left side:  Drag-and-drop zone (accepts module folders, click to browse).
Right side: Live module list — every loaded module with its stage, stats,
            and per-module Stop / Remove buttons.

This panel is the sole entry point for loading modules and the sole
control surface for managing them.
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Dict, Optional

from core.module_state import ModuleRecord, ModuleStage, registry
from gui.styles import (
    STAGE_COLORS,
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED, ACCENT_ORANGE,
    BG_DARK, BG_DROP, BG_DROP_HOVER, BG_HEADER, BG_PANEL, BG_PANEL_ALT,
    BORDER, BORDER_ACCENT,
    FONT_BODY, FONT_HEADER, FONT_MONO, FONT_MONO_S, FONT_SMALL, FONT_TITLE,
    PAD, PAD_S,
    TEXT_ERROR, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_SUCCESS, TEXT_WARNING,
)


class ModuleManagementPanel(tk.Frame):
    """
    Combined drop zone + module management list.
    Layout: [DROP ZONE (left)] | [MODULE LIST (right)]
    """

    def __init__(self, parent, on_module_dropped: Callable[[Path], None],
                 on_stop: Callable[[str], None],
                 on_remove: Callable[[str], None],
                 **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._on_drop   = on_module_dropped
        self._on_stop   = on_stop
        self._on_remove = on_remove
        self._hover     = False
        self._build()
        registry.add_listener(self._refresh_list)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        # Section header
        header_row = tk.Frame(self, bg=BG_PANEL)
        header_row.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_S))
        tk.Label(header_row, text="MODULE MANAGEMENT",
                 font=FONT_HEADER, bg=BG_PANEL, fg=ACCENT_BLUE).pack(side=tk.LEFT)

        # Kafka status indicator
        self._kafka_var = tk.StringVar(value="⬤ Kafka: checking...")
        self._kafka_label = tk.Label(header_row, textvariable=self._kafka_var,
                                      font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED)
        self._kafka_label.pack(side=tk.RIGHT, padx=PAD)

        # Two-column body
        body = tk.Frame(self, bg=BG_PANEL)
        body.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # Left: drop zone
        drop_frame = tk.Frame(body, bg=BG_PANEL)
        drop_frame.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_S))
        self._build_drop_zone(drop_frame)

        # Vertical divider
        tk.Frame(body, bg=BORDER, width=1).grid(row=0, column=0,
                                                  sticky="nse", padx=(0, PAD_S))

        # Right: module list
        list_frame = tk.Frame(body, bg=BG_PANEL)
        list_frame.grid(row=0, column=1, sticky="nsew", padx=(PAD_S, 0))
        self._build_module_list(list_frame)

    def _build_drop_zone(self, parent: tk.Frame):
        tk.Label(parent, text="DROP ZONE", font=FONT_MONO_S,
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(0, PAD_S))

        self._canvas = tk.Canvas(parent, bg=BG_DROP, highlightthickness=2,
                                  highlightbackground=BORDER, height=110, cursor="hand2")
        self._canvas.pack(fill=tk.X, pady=(0, PAD_S))
        self._canvas.bind("<Configure>", self._redraw)
        self._canvas.bind("<Button-1>",  self._browse_folder)
        self._canvas.bind("<Enter>",     self._on_enter)
        self._canvas.bind("<Leave>",     self._on_leave)
        self._try_enable_dnd()

        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(parent, textvariable=self._status_var,
                                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_SECONDARY,
                                     wraplength=280, justify=tk.LEFT)
        self._status_lbl.pack(anchor="w")

    def _build_module_list(self, parent: tk.Frame):
        hdr = tk.Frame(parent, bg=BG_PANEL)
        hdr.pack(fill=tk.X, pady=(0, PAD_S))
        tk.Label(hdr, text="ACTIVE MODULES", font=FONT_MONO_S,
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(side=tk.LEFT)
        self._count_var = tk.StringVar(value="0 loaded")
        tk.Label(hdr, textvariable=self._count_var, font=FONT_MONO_S,
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(side=tk.RIGHT)

        container = tk.Frame(parent, bg=BG_PANEL)
        container.pack(fill=tk.BOTH, expand=True)

        self._list_canvas = tk.Canvas(container, bg=BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                  command=self._list_canvas.yview)
        self._list_inner = tk.Frame(self._list_canvas, bg=BG_PANEL)
        self._list_inner.bind(
            "<Configure>",
            lambda e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all"))
        )
        self._list_canvas.create_window((0, 0), window=self._list_inner, anchor="nw")
        self._list_canvas.configure(yscrollcommand=scrollbar.set)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self._list_inner, text="No modules loaded",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=8)

    # ── Drop Zone Drawing ─────────────────────────────────────────────────

    def _redraw(self, event=None):
        self._canvas.delete("all")
        w = self._canvas.winfo_width() or 300
        h = self._canvas.winfo_height() or 110
        self._canvas.configure(bg=BG_DROP_HOVER if self._hover else BG_DROP)
        border_color = BORDER_ACCENT if self._hover else BORDER
        self._canvas.create_rectangle(8, 8, w - 8, h - 8,
                                       outline=border_color, dash=(6, 4), width=2)
        self._canvas.create_text(w // 2, h // 2 - 16,
                                  text="📂", font=("Segoe UI Emoji", 22),
                                  fill=TEXT_PRIMARY)
        self._canvas.create_text(w // 2, h // 2 + 14,
                                  text="Drop module folder here",
                                  font=FONT_BODY, fill=TEXT_SECONDARY)
        self._canvas.create_text(w // 2, h // 2 + 30,
                                  text="or click to browse",
                                  font=FONT_SMALL, fill=TEXT_MUTED)

    def _on_enter(self, _):
        self._hover = True
        self._redraw()
        self._canvas.configure(highlightbackground=BORDER_ACCENT)

    def _on_leave(self, _):
        self._hover = False
        self._redraw()
        self._canvas.configure(highlightbackground=BORDER)

    def _browse_folder(self, _=None):
        folder = filedialog.askdirectory(title="Select Module Folder")
        if folder:
            self._accept(Path(folder))

    def _accept(self, path: Path):
        # Duplicate check
        if registry.is_duplicate(str(path)):
            self.set_status(f"⚠️  Already loaded: {path.name}", TEXT_WARNING)
            return
        self.set_status(f"⚙️  Processing: {path.name} ...", ACCENT_ORANGE)
        self._on_drop(path)

    def _try_enable_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            self._canvas.drop_target_register(DND_FILES)
            self._canvas.dnd_bind("<<Drop>>",      self._on_dnd_drop)
            self._canvas.dnd_bind("<<DragEnter>>",  lambda e: self._on_enter(e))
            self._canvas.dnd_bind("<<DragLeave>>",  lambda e: self._on_leave(e))
        except Exception:
            pass

    def _on_dnd_drop(self, event):
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = Path(raw)
        if path.is_dir():
            self._accept(path)
        else:
            self.set_status("⚠️  Drop a folder, not a file.", TEXT_WARNING)

    # ── Module List ───────────────────────────────────────────────────────

    def _refresh_list(self):
        """Called by registry listener whenever state changes."""
        for w in self._list_inner.winfo_children():
            w.destroy()

        modules = registry.all()
        self._count_var.set(f"{len(modules)} loaded")

        if not modules:
            tk.Label(self._list_inner, text="No modules loaded",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=8)
            return

        for mod in modules:
            self._render_row(mod)

    def _render_row(self, mod: ModuleRecord):
        stage_color = STAGE_COLORS.get(mod.stage.value, TEXT_SECONDARY)
        is_online   = mod.stage == ModuleStage.ONLINE
        is_terminal = mod.stage in (ModuleStage.FAILED, ModuleStage.STOPPED)

        row = tk.Frame(self._list_inner, bg=BG_PANEL_ALT,
                       highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill=tk.X, pady=2, padx=2)

        # Stage icon
        tk.Label(row, text=mod.stage_icon, font=("Segoe UI Emoji", 11),
                 bg=BG_PANEL_ALT).pack(side=tk.LEFT, padx=(PAD, 2), pady=PAD_S)

        # Info block
        info = tk.Frame(row, bg=BG_PANEL_ALT)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=PAD_S)

        tk.Label(info, text=mod.name[:24], font=FONT_MONO,
                 bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, anchor="w").pack(anchor="w")

        detail = f"ID:{mod.module_id}  {mod.stage.value}"
        if mod.environment:
            detail += f"  env:{mod.environment}"
        if mod.capabilities:
            detail += f"  caps:{len(mod.capabilities)}"
        tk.Label(info, text=detail, font=FONT_MONO_S,
                 bg=BG_PANEL_ALT, fg=stage_color, anchor="w").pack(anchor="w")

        if mod.error:
            tk.Label(info, text=f"⚠ {mod.error[:50]}", font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_ERROR, anchor="w").pack(anchor="w")

        # Action buttons
        btn_frame = tk.Frame(row, bg=BG_PANEL_ALT)
        btn_frame.pack(side=tk.RIGHT, padx=PAD_S, pady=PAD_S)

        if is_online:
            # Stop button — only for ONLINE modules
            tk.Button(
                btn_frame, text="⏹ Stop",
                font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_WARNING,
                relief=tk.FLAT, cursor="hand2",
                activebackground=BG_PANEL_ALT, activeforeground=ACCENT_ORANGE,
                command=lambda mid=mod.module_id: self._on_stop(mid),
            ).pack(side=tk.LEFT, padx=2)

        if is_terminal:
            # Remove button — only for FAILED/STOPPED modules
            tk.Button(
                btn_frame, text="✕ Remove",
                font=FONT_MONO_S, bg=BG_PANEL_ALT, fg=TEXT_ERROR,
                relief=tk.FLAT, cursor="hand2",
                activebackground=BG_PANEL_ALT, activeforeground=ACCENT_RED,
                command=lambda mid=mod.module_id: self._on_remove(mid),
            ).pack(side=tk.LEFT, padx=2)

    # ── Public helpers ────────────────────────────────────────────────────

    def set_status(self, text: str, color: str = TEXT_SECONDARY):
        self._status_var.set(text)
        self._status_lbl.configure(fg=color)

    def set_kafka_status(self, connected: bool):
        if connected:
            self._kafka_var.set("⬤ Kafka: connected")
            self._kafka_label.configure(fg=TEXT_SUCCESS)
        else:
            self._kafka_var.set("⬤ Kafka: in-process fallback")
            self._kafka_label.configure(fg=TEXT_WARNING)
