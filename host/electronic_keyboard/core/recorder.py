# -*- coding: utf-8 -*-
# Records performance events (future: export, scoring).

from __future__ import annotations

import time
from typing import List, Optional

from .events import EventKind, PlayEvent


class PerformanceRecorder:
    def __init__(self) -> None:
        self._events: List[PlayEvent] = []
        self._recording = False
        self._t0: float = 0.0

    def start(self) -> None:
        self._events.clear()
        self._recording = True
        self._t0 = time.perf_counter()

    def stop(self) -> None:
        self._recording = False

    def clear(self) -> None:
        self._events.clear()

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def count(self) -> int:
        return len(self._events)

    def now_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def record(
        self,
        kind: EventKind,
        note_id: int,
        note_name: str,
        extra: Optional[str] = None,
    ) -> None:
        if not self._recording:
            return
        if kind not in (
            EventKind.NOTE_ON,
            EventKind.NOTE_OFF,
            EventKind.SERIAL_RECV,
            EventKind.SERIAL_SEND,
        ):
            return
        self._events.append(
            PlayEvent(
                kind=kind,
                note_id=note_id,
                note_name=note_name,
                t_ms=self.now_ms(),
                extra=extra,
            )
        )

    def all_events(self) -> List[PlayEvent]:
        return list(self._events)

    def last_event(self) -> Optional[PlayEvent]:
        return self._events[-1] if self._events else None
