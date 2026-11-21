#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离谱 Lilipu 启动入口。

用法：
    python main.py
"""

import os
import sys

# PyInstaller --windowed 下 stdout/stderr 为 None，部分库（music21 等）会因此崩溃
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")

from lilipu.ui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
