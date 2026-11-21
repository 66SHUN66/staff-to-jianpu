# -*- coding: utf-8 -*-
"""日志初始化：控制台 + 按用户数据目录落盘的 debug.log。"""

from __future__ import annotations

import logging
import os

from .paths import app_data_dir

LOG_FILE = os.path.join(app_data_dir(), "debug.log")
_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """配置 root logger，重复调用无副作用。"""
    global _configured
    if _configured:
        return
    handlers = []
    try:
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
    except Exception:
        pass
    try:
        handlers.append(logging.StreamHandler())
    except Exception:
        # PyInstaller --windowed 下没有控制台，忽略即可
        pass
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
