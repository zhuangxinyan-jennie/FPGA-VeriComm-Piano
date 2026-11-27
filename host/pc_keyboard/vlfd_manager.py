# -*- coding: utf-8 -*-
"""Background worker: run strobe sequences over FifoTransport (like serial_comm/manager.py)."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Dict, Optional

# Second arg: which command produced this RX ("on" / "off" / "error").
RxCallback = Optional[Callable[[Dict, str], None]]

from .codec import decode_rx_u64, encode_tx_u64
from .fifo_sequence import strobe_command_tx_u64_list
from .transport import CtypesVlfdTransport, FifoTransport, MockFifoTransport


class VlfdFifoManager:
    def __init__(
        self,
        on_rx_sample: RxCallback = None,
    ) -> None:
        self._on_rx_sample = on_rx_sample
        self._transport: Optional[FifoTransport] = None
        self._q: queue.Queue = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.last_connect_error: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self._transport is not None

    def connect_mock(self) -> bool:
        self.disconnect()
        try:
            t: FifoTransport = MockFifoTransport()
            t.open()
            self._transport = t
            self._start_worker()
            return True
        except Exception:
            self._transport = None
            return False

    def connect_vlfd_ffi(self, dll_path: Optional[str] = None) -> bool:
        self.disconnect()
        self.last_connect_error = None
        try:
            t = CtypesVlfdTransport(dll_path=dll_path)
            t.open()
            self._transport = t
            self._start_worker()
            return True
        except Exception as e:
            self._transport = None
            self.last_connect_error = str(e)
            return False

    def disconnect(self) -> None:
        self._stop.set()
        if self._worker:
            self._q.put(None)
            self._worker.join(timeout=2.0)
            self._worker = None
        self._stop.clear()
        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None

    def _start_worker(self) -> None:
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._q.get()
            if item is None:
                break
            kind, kid = item
            if not self._transport:
                continue
            try:
                key_on = 1 if kind == "on" else 0
                rx_last = 0
                for tx in strobe_command_tx_u64_list(kid, key_on):
                    rx_last = self._transport.step_u64(tx)
                    time.sleep(0)  # yield
                # Strobe ends before freq_hz/led regs settle; pump idle clocks so RX matches RTL.
                idle_tx = encode_tx_u64(kid, key_on, 0)
                for _ in range(8):
                    rx_last = self._transport.step_u64(idle_tx)
                    time.sleep(0)
                if self._on_rx_sample:
                    self._on_rx_sample(decode_rx_u64(rx_last), kind)
            except Exception as e:
                if self._on_rx_sample:
                    self._on_rx_sample(
                        {"error": str(e), "led": [], "freq_hz": 0, "last_event_ts": 0},
                        "error",
                    )

    def send_key_on(self, key_id_0_11: int) -> None:
        if self._transport:
            self._q.put(("on", int(key_id_0_11) & 0xF))

    def send_key_off(self, key_id_0_11: int) -> None:
        if self._transport:
            self._q.put(("off", int(key_id_0_11) & 0xF))
