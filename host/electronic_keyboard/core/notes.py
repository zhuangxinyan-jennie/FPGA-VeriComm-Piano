# -*- coding: utf-8 -*-
# MIDI note helpers and PC keyboard bindings (extend: octave, voice).

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


def midi_to_name(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi // 12) - 1
    return f"{names[midi % 12]}{octave}"


def midi_to_freq(midi: int) -> float:
    # Equal temperament, A4 = 440 Hz
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


@dataclass
class KeyBinding:
    """key_id: tk key char. fpga_key_id: 0..11 semitone in octave (C..B) for FPGA UART."""

    key_id: str
    midi: int
    fpga_key_id: int
    is_black: bool
    key_char: str


def build_default_octave_bindings(octave: int = 4) -> List[KeyBinding]:
    # Whites A S D F G H J -> C D E F G A B
    # Blacks W E T Y U -> C# D# F# G# A#
    # fpga_key_id matches fpga_piano_top.v: 0=C .. 11=B
    base = 12 * (octave + 1)
    whites: List[tuple] = [
        ("a", 0, "A"),
        ("s", 2, "S"),
        ("d", 4, "D"),
        ("f", 5, "F"),
        ("g", 7, "G"),
        ("h", 9, "H"),
        ("j", 11, "J"),
    ]
    blacks: List[tuple] = [
        ("w", 1, "W"),
        ("e", 3, "E"),
        ("t", 6, "T"),
        ("y", 8, "Y"),
        ("u", 10, "U"),
    ]
    out: List[KeyBinding] = []
    for kid, off, ch in whites:
        out.append(
            KeyBinding(
                key_id=kid,
                midi=base + off,
                fpga_key_id=off,
                is_black=False,
                key_char=ch,
            )
        )
    for kid, off, ch in blacks:
        out.append(
            KeyBinding(
                key_id=kid,
                midi=base + off,
                fpga_key_id=off,
                is_black=True,
                key_char=ch,
            )
        )
    return out


def binding_map_by_key_id(bindings: List[KeyBinding]) -> Dict[str, KeyBinding]:
    return {b.key_id: b for b in bindings}
