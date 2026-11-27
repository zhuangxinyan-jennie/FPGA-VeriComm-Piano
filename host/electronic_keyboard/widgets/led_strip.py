# -*- coding: utf-8 -*-
# One row of LEDs: 12 semitones C..B (tkinter Canvas).

from __future__ import annotations

import tkinter as tk


class LedStripCanvas(tk.Canvas):
    def __init__(self, parent, **kw) -> None:
        super().__init__(
            parent,
            height=44,
            bg="#2b2b2e",
            highlightthickness=0,
            **kw,
        )
        self._mask = 0
        self.bind("<Configure>", self._draw)

    def set_mask(self, mask: int) -> None:
        self._mask = mask & 0xFFF
        self._draw()

    def _draw(self, _event=None) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 120)
        h = self.winfo_height()
        n = 12
        margin = 4
        gap = 3
        usable = w - 2 * margin
        cell = (usable - (n - 1) * gap) / n
        cy = h // 2
        r = min(cell, h - 8) / 2
        for i in range(n):
            x = margin + i * (cell + gap) + cell / 2
            on = (self._mask >> i) & 1
            fill = "#50dc78" if on else "#37373c"
            outline = "#288c3c" if on else "#232328"
            self.create_oval(
                x - r,
                cy - r,
                x + r,
                cy + r,
                fill=fill,
                outline=outline,
                width=1,
            )
