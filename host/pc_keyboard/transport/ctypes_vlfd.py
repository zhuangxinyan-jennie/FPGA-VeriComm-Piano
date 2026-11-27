"""
Optional: load vlfd-ffi (https://github.com/0xtaruhi/vlfd-ffi) shared library.

Build vlfd-ffi, then set env VLFD_FFI_DLL to the path of the .dll / .so / .dylib,
or place the library next to this file as vlfd_ffi.dll (Windows) / libvlfd_ffi.so (Linux).

Exports used: vlfd_io_open, vlfd_io_write_read, vlfd_io_close, vlfd_get_last_error_message.
"""

from __future__ import annotations

import ctypes
import os
import platform
from typing import List, Optional

from ..codec import u64_from_4xu16, u64_to_4xu16
from .base import FifoTransport


def _default_dll_name() -> str:
    s = platform.system()
    if s == "Windows":
        return "vlfd_ffi.dll"
    if s == "Darwin":
        return "libvlfd_ffi.dylib"
    return "libvlfd_ffi.so"


class CtypesVlfdTransport(FifoTransport):
    def __init__(self, dll_path: Optional[str] = None) -> None:
        path = dll_path or os.environ.get("VLFD_FFI_DLL")
        if not path:
            here = os.path.dirname(os.path.abspath(__file__))
            cand = os.path.join(os.path.dirname(os.path.dirname(here)), _default_dll_name())
            if os.path.isfile(cand):
                path = cand
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(
                "vlfd-ffi library not found. Build from "
                "https://github.com/0xtaruhi/vlfd-ffi and set VLFD_FFI_DLL to the .dll/.so path."
            )
        self._dll_path = path
        self._dll: Optional[ctypes.CDLL] = None
        self._dev: Optional[ctypes.c_void_p] = None

    def open(self) -> None:
        self._dll = ctypes.CDLL(self._dll_path)
        self._dll.vlfd_io_open.restype = ctypes.c_void_p
        self._dll.vlfd_io_open.argtypes = []
        self._dll.vlfd_io_write_read.restype = ctypes.c_int
        self._dll.vlfd_io_write_read.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.c_uint,
        ]
        self._dll.vlfd_io_close.restype = ctypes.c_int
        self._dll.vlfd_io_close.argtypes = [ctypes.c_void_p]
        self._dll.vlfd_get_last_error_message.restype = ctypes.c_char_p
        self._dll.vlfd_get_last_error_message.argtypes = []

        dev = self._dll.vlfd_io_open()
        if not dev:
            msg = self._dll.vlfd_get_last_error_message()
            raise OSError(msg.decode("utf-8", errors="replace") if msg else "vlfd_io_open failed")
        self._dev = ctypes.c_void_p(dev)

    def close(self) -> None:
        if self._dll and self._dev:
            self._dll.vlfd_io_close(self._dev)
        self._dev = None
        self._dll = None

    def step_u64(self, tx_u64: int) -> int:
        if not self._dll or self._dev is None:
            raise RuntimeError("transport not open")
        words = u64_to_4xu16(tx_u64)
        tx = (ctypes.c_uint16 * 4)(*words)
        rx = (ctypes.c_uint16 * 4)()
        ret = self._dll.vlfd_io_write_read(self._dev, tx, rx, 4)
        if ret != 0:
            msg = self._dll.vlfd_get_last_error_message()
            err = msg.decode("utf-8", errors="replace") if msg else "vlfd_io_write_read failed"
            raise OSError(err)
        return u64_from_4xu16([rx[i] for i in range(4)])
