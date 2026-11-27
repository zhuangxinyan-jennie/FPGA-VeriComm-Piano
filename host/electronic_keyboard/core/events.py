# -*- coding: utf-8 -*-
# Play/serial event kinds (future: scoring, piano roll, export).

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class EventKind(Enum):
    NOTE_ON = auto()
    NOTE_OFF = auto()
    SERIAL_SEND = auto()
    SERIAL_RECV = auto()


@dataclass
class PlayEvent:
    kind: EventKind
    note_id: int
    note_name: str
    t_ms: int
    extra: Optional[str] = None
