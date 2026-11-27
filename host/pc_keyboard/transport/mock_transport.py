from __future__ import annotations

from .base import FifoTransport


class MockFifoTransport(FifoTransport):
    """No hardware: echo TX or return 0 for offline UI tests."""

    def __init__(self) -> None:
        self._open = False

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def step_u64(self, tx_u64: int) -> int:
        if not self._open:
            raise RuntimeError("transport not open")
        return tx_u64 & ((1 << 64) - 1)
