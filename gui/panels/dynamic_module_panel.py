"""
Dynamic Module Panel — auto-generated GUI panel for a single ONLINE module.

Built entirely from the module's UI descriptor produced by UIAdaptationEngine.
Each capability becomes an interactive control:
  text_input  → Label + Entry + Run button
  file_input  → Label + Entry + Browse button + Run button
  slider      → Label + Scale + Run button
  toggle      → Label + Checkbutton + Run button
  dropdown    → Label + OptionMenu + Run button
  trigger     → Single Run button (no input needed)

The panel dispatches capability calls through the IntentRouter and shows
the result inline. It rebuilds itself completely whenever the descriptor
is updated (capability added/removed/changed).
"""
import datetime
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Severity, bus
from gui.styles import (
    BG_PANEL, BG_PANEL_ALT, BG_HEADER, BORDER,
    FONT_HEADER, FONT_MONO, FONT_MONO_S, FONT_SMALL, FONT_BODY,
    PAD, PAD_S,
    TEXT_ERROR, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_SUCCESS, TEXT_WARNING,
)


class DynamicModulePanel(tk.Frame):
    """
    A self-contained dashboard panel for one module.
    Rebuilt automatically when the module's descriptor changes.
    """

    def __init__(self, parent, descriptor: Dict[str, Any],
                 on_dispatch: Callable[[str, str, Any], None],
                 **kwargs):
        """
        descriptor  — UI descriptor from UIAdaptationEngine
        on_dispatch — callback(module_id, intent_label, payload)
        """
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._descriptor  = descriptor
        self._on_dispatch = on_dispatch
        self._input_vars: Dict[str, tk.Variable] = {}
        self._result_vars: Dict[str, tk.StringVar] = {}
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        d = self._descriptor
        color = d.get("dashboard_color", "#388bfd")
        icon  = d.get("dashboard_icon", "📦")
        name  = d.get("name", d["module_id"])

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_HEADER,
                       highlightthickness=1, highlightbackground=color)
        hdr.pack(fill=tk.X)

        tk.Label(hdr, text=f"{icon}  {name}",
                 font=FONT_HEADER, bg=BG_HEADER, fg=color).pack(side=tk.LEFT, padx=PAD, pady=PAD_S)

        meta = f"v{d.get('version','?')}  ·  {d.get('purpose','?')}  ·  {d.get('environment','?')}"
        tk.Label(hdr, text=meta, font=FONT_MONO_S,
                 bg=BG_HEADER, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD)

        # ── Scrollable body ───────────────────────────────────────────────
        body_container = tk.Frame(self, bg=BG_PANEL)
        body_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(body_container, bg=BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(body_container, orient="vertical",
                                  command=canvas.yview)
        self._body = tk.Frame(canvas, bg=BG_PANEL)
        self._body.bind("<Configure>",
                         lambda e: canvas.configure(
                             scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Capabilities section ──────────────────────────────────────────
        caps = d.get("capabilities", [])
        if caps:
            tk.Label(self._body, text="CAPABILITIES",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(
                anchor="w", padx=PAD, pady=(PAD, PAD_S))

            for cap in caps:
                self._build_capability_control(cap, color)
        else:
            tk.Label(self._body, text="No capabilities declared",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=PAD)

        # ── Workflows section ─────────────────────────────────────────────
        workflows = d.get("workflows", [])
        if workflows:
            tk.Frame(self._body, bg=BORDER, height=1).pack(fill=tk.X, padx=PAD, pady=PAD_S)
            tk.Label(self._body, text="WORKFLOWS",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(
                anchor="w", padx=PAD, pady=(0, PAD_S))

            wf_row = tk.Frame(self._body, bg=BG_PANEL)
            wf_row.pack(fill=tk.X, padx=PAD, pady=(0, PAD))
            for wf in workflows:
                tk.Label(wf_row, text=f"▸ {wf}", font=FONT_MONO_S,
                         bg=BG_PANEL_ALT, fg=color,
                         padx=PAD_S, pady=2,
                         relief=tk.FLAT,
                         highlightthickness=1,
                         highlightbackground=BORDER).pack(
                    side=tk.LEFT, padx=2)

        # ── Ecosystem placement section ───────────────────────────────────
        slots      = d.get("slots", [])
        slot_icons = d.get("slot_icons", [])
        synergies  = d.get("synergies", [])
        connections = d.get("connections", [])

        if slots or synergies:
            tk.Frame(self._body, bg=BORDER, height=1).pack(fill=tk.X, padx=PAD, pady=PAD_S)
            tk.Label(self._body, text="ECOSYSTEM PLACEMENT",
                     font=FONT_MONO_S, bg=BG_PANEL, fg=TEXT_MUTED).pack(
                anchor="w", padx=PAD, pady=(0, PAD_S))

            if slots:
                slot_row = tk.Frame(self._body, bg=BG_PANEL)
                slot_row.pack(fill=tk.X, padx=PAD, pady=(0, PAD_S))
                tk.Label(slot_row, text="Slots:", font=FONT_MONO_S,
                         bg=BG_PANEL, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, PAD_S))
                for icon, slot in zip(slot_icons, slots):
                    tk.Label(slot_row, text=f"{icon} {slot}", font=FONT_MONO_S,
                             bg=BG_PANEL_ALT, fg=color,
                             padx=PAD_S, pady=1,
                             highlightthickness=1,
                             highlightbackground=BORDER).pack(side=tk.LEFT, padx=2)

            if synergies:
                for syn_desc in synergies[:3]:
                    tk.Label(self._body, text=f"  ⚡ {syn_desc}",
                             font=FONT_MONO_S, bg=BG_PANEL, fg="#d29922",
                             anchor="w").pack(anchor="w", padx=PAD)

    def _build_capability_control(self, cap: Dict[str, Any], accent: str):
        """Build one capability row with its widget and Run button."""
        name        = cap.get("name", "?")
        description = cap.get("description", "")
        widget_type = cap.get("widget_type", "text_input")
        intent      = cap.get("intent_label", name)
        inputs      = cap.get("inputs", [])
        outputs     = cap.get("outputs", [])

        frame = tk.Frame(self._body, bg=BG_PANEL_ALT,
                         highlightthickness=1, highlightbackground=BORDER)
        frame.pack(fill=tk.X, padx=PAD, pady=2)

        # Capability name + description
        info_row = tk.Frame(frame, bg=BG_PANEL_ALT)
        info_row.pack(fill=tk.X, padx=PAD_S, pady=(PAD_S, 0))
        tk.Label(info_row, text=f"✦ {name}", font=FONT_MONO,
                 bg=BG_PANEL_ALT, fg=accent, anchor="w").pack(side=tk.LEFT)
        if description:
            tk.Label(info_row, text=f"  {description[:60]}",
                     font=FONT_MONO_S, bg=BG_PANEL_ALT,
                     fg=TEXT_MUTED, anchor="w").pack(side=tk.LEFT)

        # I/O hint
        if inputs or outputs:
            io_text = ""
            if inputs:
                io_text += "in: " + ", ".join(inputs)[:40]
            if outputs:
                io_text += ("  →  " if io_text else "→  ") + ", ".join(outputs)[:40]
            tk.Label(info_row, text=io_text, font=FONT_MONO_S,
                     bg=BG_PANEL_ALT, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=PAD_S)

        # Input widget + Run button
        ctrl_row = tk.Frame(frame, bg=BG_PANEL_ALT)
        ctrl_row.pack(fill=tk.X, padx=PAD_S, pady=(2, PAD_S))

        input_var = self._build_input_widget(ctrl_row, name, widget_type, inputs)
        self._input_vars[name] = input_var

        # Run button
        run_btn = tk.Button(
            ctrl_row,
            text="▶ Run",
            font=FONT_MONO_S,
            bg=BG_PANEL_ALT,
            fg=accent,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=BG_PANEL_ALT,
            activeforeground=TEXT_PRIMARY,
            command=lambda n=name, i=intent, v=input_var: self._run_capability(n, i, v),
        )
        run_btn.pack(side=tk.LEFT, padx=(PAD_S, 0))

        # Result display
        result_var = tk.StringVar(value="")
        self._result_vars[name] = result_var
        result_lbl = tk.Label(ctrl_row, textvariable=result_var,
                               font=FONT_MONO_S, bg=BG_PANEL_ALT,
                               fg=TEXT_SECONDARY, anchor="w", wraplength=400)
        result_lbl.pack(side=tk.LEFT, padx=PAD_S, fill=tk.X, expand=True)

    def _build_input_widget(self, parent: tk.Frame, name: str,
                             widget_type: str, inputs: List[str]) -> tk.Variable:
        """Build the appropriate input widget and return its variable."""

        if widget_type == "trigger":
            # No input needed — just a variable placeholder
            return tk.StringVar(value="")

        if widget_type == "toggle":
            var = tk.BooleanVar(value=False)
            tk.Checkbutton(parent, variable=var, text="enabled",
                           bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                           selectcolor=BG_PANEL_ALT,
                           activebackground=BG_PANEL_ALT,
                           font=FONT_MONO_S).pack(side=tk.LEFT)
            return var

        if widget_type == "slider":
            var = tk.IntVar(value=100)
            tk.Scale(parent, variable=var, from_=1, to=512,
                     orient=tk.HORIZONTAL, length=160,
                     bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                     troughcolor=BG_PANEL_ALT,
                     highlightthickness=0,
                     font=FONT_MONO_S).pack(side=tk.LEFT)
            return var

        if widget_type == "dropdown":
            var = tk.StringVar(value="option_1")
            options = ["option_1", "option_2", "option_3"]
            om = tk.OptionMenu(parent, var, *options)
            om.configure(bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                         activebackground=BG_PANEL_ALT,
                         font=FONT_MONO_S, relief=tk.FLAT,
                         highlightthickness=1,
                         highlightbackground=BORDER)
            om["menu"].configure(bg=BG_PANEL_ALT, fg=TEXT_SECONDARY,
                                  font=FONT_MONO_S)
            om.pack(side=tk.LEFT)
            return var

        if widget_type == "file_input":
            var = tk.StringVar(value="")
            entry = tk.Entry(parent, textvariable=var, width=28,
                             bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                             insertbackground=TEXT_PRIMARY,
                             relief=tk.FLAT,
                             highlightthickness=1,
                             highlightbackground=BORDER,
                             font=FONT_MONO_S)
            entry.pack(side=tk.LEFT, padx=(0, 2))
            tk.Button(parent, text="📁", font=FONT_MONO_S,
                      bg=BG_PANEL_ALT, fg=TEXT_MUTED,
                      relief=tk.FLAT, cursor="hand2",
                      command=lambda v=var: v.set(
                          filedialog.askopenfilename() or v.get()
                      )).pack(side=tk.LEFT, padx=(0, PAD_S))
            return var

        # Default: text_input
        var = tk.StringVar(value="")
        hint = inputs[0].split(":")[0] if inputs else "input"
        entry = tk.Entry(parent, textvariable=var, width=32,
                         bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                         insertbackground=TEXT_PRIMARY,
                         relief=tk.FLAT,
                         highlightthickness=1,
                         highlightbackground=BORDER,
                         font=FONT_MONO_S)
        entry.insert(0, f"")
        entry.pack(side=tk.LEFT, padx=(0, PAD_S))
        return var

    # ── Dispatch ──────────────────────────────────────────────────────────

    def _run_capability(self, cap_name: str, intent_label: str, input_var: tk.Variable):
        """Dispatch a capability call through the intent router."""
        try:
            raw = input_var.get()
            payload = {"input": raw, "capability": cap_name}

            self._result_vars[cap_name].set("⏳ running...")
            self._on_dispatch(self._descriptor["module_id"], intent_label, payload)

            # Show dispatch confirmation (actual result would come from router callback)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._result_vars[cap_name].set(f"✅ dispatched [{ts}]")

        except Exception as e:
            self._result_vars[cap_name].set(f"❌ {e}")

    # ── Update ────────────────────────────────────────────────────────────

    def update_descriptor(self, descriptor: Dict[str, Any]):
        """Rebuild the panel with a new descriptor (capability set changed)."""
        self._descriptor = descriptor
        self._input_vars.clear()
        self._result_vars.clear()
        for w in self.winfo_children():
            w.destroy()
        self._build()
