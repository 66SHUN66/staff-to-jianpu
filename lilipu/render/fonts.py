# -*- coding: utf-8 -*-
"""中文字体定位。

优先使用随包字库（assets/fonts），其次按平台查找系统字体，
最后才退回 PIL 默认位图字体。避免把 Windows 字体路径写死。
"""

from __future__ import annotations

import glob
import os
import sys

from PIL import ImageFont

from ..logging_setup import get_logger
from ..paths import resource_path

logger = get_logger(__name__)
_font_cache: dict = {}
_fallback_warned = False


def _bundled_fonts(bold: bool) -> list:
    """随包字体目录中挑选常规/粗体字库。"""
    font_dir = resource_path("assets", "fonts")
    if not os.path.isdir(font_dir):
        return []
    files = sorted(glob.glob(os.path.join(font_dir, "*.ttf")))
    files += sorted(glob.glob(os.path.join(font_dir, "*.otf")))
    files += sorted(glob.glob(os.path.join(font_dir, "*.ttc")))
    if not files:
        return []
    bold_hits = [f for f in files if any(k in os.path.basename(f).lower() for k in ("bold", "bd", "heavy", "semibold"))]
    regular_hits = [f for f in files if f not in bold_hits]
    return (bold_hits + regular_hits) if bold else (regular_hits + bold_hits)


def _system_fonts(bold: bool) -> list:
    """各平台常见中文字体候选。"""
    if sys.platform == "win32":
        win = os.environ.get("WINDIR", r"C:\\Windows")
        names = ["msyhbd.ttc", "msyh.ttc"] if bold else ["msyh.ttc", "msyhbd.ttc"]
        return [os.path.join(win, "Fonts", n) for n in names + ["simhei.ttf", "simsun.ttc"]]
    if sys.platform == "darwin":
        return [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    return [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]


def _matplotlib_fonts(bold: bool) -> list:
    """装了 matplotlib 时借用它的字体库索引，能覆盖更多发行版。"""
    try:
        from matplotlib import font_manager
        names = ["Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei", "Microsoft YaHei"]
        found = font_manager.findfont(names[0], fallback_to_default=False)
        return [found]
    except Exception:
        return []


def get_font(size: int, bold: bool = True):
    """返回指定字号的中文字体对象，尽量保证不是位图字体。"""
    global _fallback_warned
    key = (int(size), bool(bold))
    if key in _font_cache:
        return _font_cache[key]

    env = os.environ.get("LILIPU_FONT_BOLD" if bold else "LILIPU_FONT")
    candidates = ([env] if env else []) + _bundled_fonts(bold) + _system_fonts(bold) + _matplotlib_fonts(bold)
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            font = ImageFont.truetype(path, size)
            _font_cache[key] = font
            return font
        except Exception:
            continue

    if not _fallback_warned:
        logger.warning("未找到中文字体，将使用 PIL 默认字体，中文可能显示为方块；"
                       "可设置环境变量 LILIPU_FONT 指向一个 ttf/otf 文件。")
        _fallback_warned = True
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font
