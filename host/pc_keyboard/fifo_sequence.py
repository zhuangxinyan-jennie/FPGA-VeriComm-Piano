"""Build TX u64 sequence for vlfd_cmd_bridge one-shot strobe (0 -> 1 -> 0)."""

from __future__ import annotations

from typing import List

from .codec import encode_tx_u64, u64_to_4xu16


def strobe_command_tx_u64_list(key_id: int, key_on: int) -> List[int]:
    """
    One FPGA command: strobe low, strobe high (latch), strobe low.
    Extra leading idle cycles help if the bridge sync delays key_id by 1 cycle.
    """
    kid = key_id & 0xF
    kon = 1 if key_on else 0
    seq: List[int] = []
    # idle: key + on stable, strobe 0
    for _ in range(2):
        seq.append(encode_tx_u64(kid, kon, 0))
    seq.append(encode_tx_u64(kid, kon, 0))
    seq.append(encode_tx_u64(kid, kon, 1))
    seq.append(encode_tx_u64(kid, kon, 0))
    return seq


def strobe_command_tx_words(key_id: int, key_on: int) -> List[List[int]]:
    """Same as strobe_command_tx_u64_list but each step as 4 x u16 for vlfd_io_write_read."""
    return [u64_to_4xu16(u) for u in strobe_command_tx_u64_list(key_id, key_on)]
