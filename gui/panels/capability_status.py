"""
Capability Status Panel — shows all registered capabilities across all modules.

Refreshes on two triggers:
  1. The 500ms poll loop in main_window (background)
  2. Immediately when capability_expansion fires add_capability_listener
     (e.g. new module loaded, external capabilities.json edit, module removed)
"""
import datetime
import json
import tkinter as tk
from pathlib import Path
from typing import Dict

from gui.styles import (
    ACCENT_BLUE, BG_PANEL, BG_PANEL_ALT, BORDER, FONT_HEADER, FONT_MONO,
    FONT_MONO_S, PAD, PAD_S, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_SUCCESS, TEXT_WARNING,
)

DATABASE_ROOT = Path("DATABASE")


class CapabilityStatusPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._last_hash = ""   # detect actual changes to avoid flicker
        self._build()

    def _build(self):
        # Header row with live update timestamp
        hdr = tk.Frame(self, bg=BG_PANEL)
        hdr.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_S))
        tk.Label(hdr, text="CAPABILITY STATUS", font=FONT_HEADER,
                 bg=BG_PANEL, fg=ACCENT_BLUE).pack(side=tk.LEFT)
        self._updated_var = tk.StringVar(value="")
        tk.Label(hdr, textvariable=self._updated_var, font=FONT_MONO_S,
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(side=tk.RIGHT)

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

        tk.Label(self._inner, text="Awaiting capabilities...",
                 font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)

    def refresh(self):
        """
        Reload from global_registry.json and redraw.
        Only redraws if the content actually changed (hash check).
        """
        reg_path = DATABASE_ROOT / "capabilities" / "global_registry.json"

        if not reg_path.exists():
            new_hash = "__empty__"
        else:
            try:
                raw = reg_path.read_text(encoding="utf-8")
                new_hash = str(hash(raw))
            except Exception:
                return

        # Skip redraw if nothing changed
        if new_hash == self._last_hash:
            return
        self._last_hash = new_hash

        # Parse
        global_reg: Dict = {}
        if reg_path.exists():
            try:
                global_reg = json.loads(reg_path.read_text(encoding="utf-8"))
            except Exception:
                return

        # Rebuild inner content
        for w in self._inner.winfo_children():
            w.destroy()

        total = 0
        for module_id, cap_entry in global_reg.items():
            actions = cap_entry.get("actions", [])
            if not actions:
                continue

            mod_name = cap_entry.get("module_name", module_id)

            # Module header row
            mod_hdr = tk.Frame(self._inner, bg=BG_PANEL)
            mod_hdr.pack(fill=tk.X, padx=2, pady=(4, 0))
            tk.Label(mod_hdr, text=f"▸ {mod_name}",
                     font=FONT_MONO, bg=BG_PANEL, fg=TEXT_PRIMARY,
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(mod_hdr, text=f"[{module_id}]  {len(actions)} caps",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED,
                     anchor="e").pack(side=tk.RIGHT)

            for action in actions:
                name  = action.get("name", "?")
                desc  = action.get("description", "")[:55]
                ins   = ", ".join(action.get("inputs", []))[:30]
                outs  = ", ".join(action.get("outputs", []))[:30]

                row = tk.Frame(self._inner, bg=BG_PANEL_ALT,
                               highlightthickness=1, highlightbackground=BORDER)
                row.pack(fill=tk.X, padx=8, pady=1)

                # Name
                tk.Label(row, text=f"  ✦ {name}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=TEXT_SUCCESS,
                         anchor="w", width=22).pack(side=tk.LEFT)

                # Description
                if desc:
                    tk.Label(row, text=desc, font=FONT_MONO_S,
                             bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                             anchor="w").pack(side=tk.LEFT, padx=(4, 0))

                # I/O hint on right
                if ins or outs:
                    io_text = f"in:{ins}" if ins else ""
                    if outs:
                        io_text += f"  out:{outs}" if io_text else f"out:{outs}"
                    tk.Label(row, text=io_text, font=FONT_MONO_S,
                             bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD)

                total += 1

        if total == 0:
            tk.Label(self._inner, text="No capabilities registered",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=10)
        else:
            tk.Label(self._inner, text=f"Total: {total} capabilities",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=(4, 2))

        # Update timestamp
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._updated_var.set(f"updated {ts}")
