from __future__ import annotations

from abc import ABC, abstractmethod


class FifoTransport(ABC):
    """One SMIMS clock step: send 64-bit VeriComm TX word, receive 64-bit RX sample."""

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def step_u64(self, tx_u64: int) -> int:
        """Return RX FIFO 64-bit word after applying TX for one virtual clock."""
