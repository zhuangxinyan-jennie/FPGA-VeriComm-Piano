# -*- coding: utf-8 -*-
# On-screen piano: one octave (tkinter Canvas).

from __future__ import annotations

from typing import Iterable, Set

import tkinter as tk

from core.notes import KeyBinding


class PianoKeysCanvas(tk.Canvas):
    def __init__(self, bindings: list[KeyBinding], parent, **kw) -> None:
        super().__init__(
            parent,
            height=160,
            bg="#e8e8ee",
            highlightthickness=0,
            **kw,
        )
        self._bindings = bindings
        self._pressed: Set[int] = set()
        self.bind("<Configure>", self._draw)

    def set_pressed(self, midis: Iterable[int]) -> None:
        self._pressed = set(midis)
        self._draw()

    def _draw(self, _event=None) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 200)
        h = self.winfo_height()
        white_h = int(h * 0.92)
        black_h = int(h * 0.55)
        n_white = 7
        margin = 8
        key_w = (w - 2 * margin) / n_white

        white_midi_order: list[int] = []
        for b in self._bindings:
            if not b.is_black:
                white_midi_order.append(b.midi)
        white_midi_order.sort()

        for i in range(7):
            x0 = margin + i * key_w
            midi = white_midi_order[i] if i < len(white_midi_order) else 0
            active = midi in self._pressed
            fill = "#b4d2ff" if active else "#f5f5fa"
            self.create_rectangle(
                x0,
                8,
                x0 + key_w - 1,
                8 + white_h,
                fill=fill,
                outline="#28282d",
                width=1,
            )

        black_positions = [0, 1, 3, 4, 5]
        black_midis = sorted([b.midi for b in self._bindings if b.is_black])
        bw = key_w * 0.58
        for idx, pos in enumerate(black_positions):
            if idx >= len(black_midis):
                break
            midi = black_midis[idx]
            x0 = margin + pos * key_w + key_w - bw / 2
            active = midi in self._pressed
            fill = "#5a78c8" if active else "#232328"
            self.create_rectangle(
                x0,
                8,
                x0 + bw,
                8 + black_h,
                fill=fill,
                outline="#0a0a0c",
                width=1,
            )

        for b in self._bindings:
            midi = b.midi
            if not b.is_black:
                wi = white_midi_order.index(midi) if midi in white_midi_order else 0
                x0 = margin + wi * key_w + key_w * 0.35
                self.create_text(
                    x0,
                    8 + white_h - 8,
                    text=b.key_char,
                    fill="#3c3c46",
                    font=("Segoe UI", 8),
                    anchor="nw",
                )
            else:
                bi = black_midis.index(midi) if midi in black_midis else 0
                pos = black_positions[bi] if bi < len(black_positions) else 0
                x0 = margin + pos * key_w + key_w - bw / 2 + bw * 0.35
                self.create_text(
                    x0,
                    8 + black_h - 6,
                    text=b.key_char,
                    fill="#cccccc",
                    font=("Segoe UI", 8),
                    anchor="nw",
                )
