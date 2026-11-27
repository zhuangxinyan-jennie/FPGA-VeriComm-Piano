"""VeriComm 64-bit packing for piano_vlfd (same rules as tools/smims_fifo_helper + vlfd_io u16 order)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# Must match piano_vlfd_cons.xml (pin order = bit index for multi-bit buses).
PINS = {
    "rst_n": "P151",
    "vc_key_id": ["P148", "P150", "P152", "P160"],
    "vc_key_on": "P161",
    "vc_cmd_strobe": "P162",
    "led": ["P7", "P6", "P5", "P4", "P9", "P8", "P16", "P15", "P11", "P10", "P20", "P18"],
    "out_freq_hz": [
        "P17", "P22", "P21", "P23", "P44", "P45", "P46", "P43", "P40", "P41", "P42",
        "P33", "P34", "P35", "P36", "P30",
    ],
    "out_last_event_ts": [
        "P31", "P24", "P27", "P29", "P110", "P109", "P99", "P98", "P94", "P93", "P84",
        "P83", "P82", "P73", "P71", "P63",
    ],
}


def _map_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "vericomm_map.json")


def load_vericomm_map() -> Dict[str, Any]:
    with open(_map_path(), encoding="utf-8") as f:
        return json.load(f)


def encode_tx_u64(key_id: int, key_on: int, cmd_strobe: int, rst_n: int = 1) -> int:
    m = load_vericomm_map()["input"]
    w = 0
    if rst_n:
        w |= 1 << m[PINS["rst_n"]]
    kid = key_id & 0xF
    for i, pin in enumerate(PINS["vc_key_id"]):
        if (kid >> i) & 1:
            w |= 1 << m[pin]
    if key_on & 1:
        w |= 1 << m[PINS["vc_key_on"]]
    if cmd_strobe & 1:
        w |= 1 << m[PINS["vc_cmd_strobe"]]
    return w


def _out_bit(word: int, pin: str) -> int:
    m = load_vericomm_map()["output"]
    idx = m[pin]
    return (word >> (idx - 1)) & 1


def decode_rx_u64(word: int) -> Dict[str, Any]:
    leds: List[int] = []
    for pin in PINS["led"]:
        leds.append(_out_bit(word, pin))
    freq = 0
    for i, pin in enumerate(PINS["out_freq_hz"]):
        if _out_bit(word, pin):
            freq |= 1 << i
    ts = 0
    for i, pin in enumerate(PINS["out_last_event_ts"]):
        if _out_bit(word, pin):
            ts |= 1 << i
    return {"led": leds, "freq_hz": freq, "last_event_ts": ts}


def parse_rabbit_read_line(line: str) -> int:
    s = line.strip()
    if len(s) != 64:
        raise ValueError("expect 64 binary chars per line")
    return int(s, 2)


def u64_to_rabbit_binary_line(u: int) -> str:
    """64 chars, MSB first (same as RabbitWriteData.txt)."""
    return format(u & ((1 << 64) - 1), "064b")


def u64_to_4xu16(u: int) -> List[int]:
    """u16 words for vlfd_io_write_read (little-endian u16 slice of 64-bit word)."""
    u &= (1 << 64) - 1
    return [(u >> (16 * i)) & 0xFFFF for i in range(4)]


def u64_from_4xu16(words: List[int]) -> int:
    w = 0
    for i, x in enumerate(words[:4]):
        w |= (int(x) & 0xFFFF) << (16 * i)
    return w
