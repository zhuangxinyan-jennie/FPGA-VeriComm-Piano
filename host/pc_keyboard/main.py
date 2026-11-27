# -*- coding: utf-8 -*-
"""Run: from zxy/piano_VLFD directory:  python -m pc_keyboard.main"""

from __future__ import annotations

from .ui_vlfd import VlfdMainWindow


def main() -> None:
    VlfdMainWindow().run()


if __name__ == "__main__":
    main()
