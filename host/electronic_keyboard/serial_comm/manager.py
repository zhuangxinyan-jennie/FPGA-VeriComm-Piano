# -*- coding: utf-8 -*-
# Serial: KEY_ON / KEY_OFF (id 0..11) for fpga_piano_top.v; read loop.

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None  # type: ignore


class SerialManager:
    def __init__(
        self,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_line = on_line
        self._ser: Optional[serial.Serial] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def list_ports() -> list[str]:
        if serial is None:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        self.disconnect()
        if serial is None:
            return False
        try:
            self._ser = serial.Serial(port, baudrate, timeout=0.1)
            self._stop.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception:
            self._ser = None
            return False

    def disconnect(self) -> None:
        self._stop.set()
        if self._read_thread is not None:
            self._read_thread.join(timeout=1.0)
            self._read_thread = None
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def _read_loop(self) -> None:
        buf = bytearray()
        while not self._stop.is_set() and self._ser and self._ser.is_open:
            try:
                data = self._ser.read(256)
                if not data:
                    time.sleep(0.01)
                    continue
                buf.extend(data)
                while b"\n" in buf:
                    line, _, rest = buf.partition(b"\n")
                    buf = rest
                    try:
                        s = line.decode("utf-8", errors="replace").strip()
                    except Exception:
                        continue
                    if s and self._on_line:
                        self._on_line(s)
            except Exception:
                time.sleep(0.05)

    def send_key_on(self, key_id_0_11: int) -> None:
        self._write_line(f"KEY_ON:{key_id_0_11}\n")

    def send_key_off(self, key_id_0_11: int) -> None:
        self._write_line(f"KEY_OFF:{key_id_0_11}\n")

    def _write_line(self, text: str) -> None:
        if not self._ser or not self._ser.is_open:
            return
        try:
            self._ser.write(text.encode("utf-8"))
        except Exception:
            pass
