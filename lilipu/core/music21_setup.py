# -*- coding: utf-8 -*-
"""music21 运行环境预配置。

music21 默认会尝试联网、调用 MuseScore 等外部程序，在打包环境里容易卡死；
解析前统一把这些路径置空，并只执行一次。
"""

from __future__ import annotations

from ..logging_setup import get_logger

logger = get_logger(__name__)
_configured = False


def configure_music21() -> None:
    global _configured
    if _configured:
        return
    try:
        from music21 import environment as _m21_env

        settings = _m21_env.UserSettings()
        for key in (
            "musicxmlPath",
            "musescoreDirectPNGPath",
            "graphicsPath",
            "pdfPath",
            "midiPath",
            "vectorPath",
            "braillePath",
        ):
            try:
                settings[key] = None
            except Exception:
                pass
        logger.info("music21 环境预配置完成")
    except Exception as exc:  # music21 缺失时不影响其他功能
        logger.warning("music21 预配置失败: %s", exc)
    _configured = True
