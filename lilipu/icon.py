# -*- coding: utf-8 -*-
"""程序图标：仓库不存二进制，按需用 Pillow 画出来。

这样打包和源码运行都不依赖预置的 .ico 文件，仓库也不必提交二进制资源。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

from .logging_setup import get_logger
from .paths import app_data_dir, resource_path
from .render.fonts import get_font

logger = get_logger(__name__)


def render_icon(size: int = 256) -> Image.Image:
    """画一个紫渐变底、白色「1」+ 高音点 + 减时线的简谱风格图标。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 垂直渐变：#7c3aed -> #4f46e5
    top = (124, 58, 237)
    bottom = (79, 70, 229)
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        gradient.putpixel(
            (0, y),
            (
                round(top[0] + (bottom[0] - top[0]) * t),
                round(top[1] + (bottom[1] - top[1]) * t),
                round(top[2] + (bottom[2] - top[2]) * t),
            ),
        )
    gradient = gradient.resize((size, size))

    pad = int(size * 0.06)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=int(size * 0.22),
        fill=255,
    )
    img.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    font = get_font(int(size * 0.52), bold=True)
    text = "1"
    box = draw.textbbox((0, 0), text, font=font)
    tw = box[2] - box[0]
    tx = (size - tw) / 2 - box[0]
    ty = int(size * 0.30) - box[1]
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

    # 高音点
    dot_r = max(3, int(size * 0.035))
    cx = size // 2
    cy = int(size * 0.22)
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(255, 255, 255, 255))

    # 减时线
    line_w = int(size * 0.26)
    line_h = max(2, int(size * 0.022))
    ly = int(size * 0.72)
    draw.rounded_rectangle(
        [cx - line_w // 2, ly, cx + line_w // 2, ly + line_h],
        radius=line_h // 2,
        fill=(255, 255, 255, 255),
    )
    return img


def ensure_icon(size: int = 256) -> str | None:
    """返回可用的 .ico 路径；缺失时现场生成。"""
    target = resource_path("assets", "icon.ico")
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    try:
        if os.path.exists(target):
            return target
        render_icon(size).save(target, format="ICO", sizes=sizes)
        return target
    except Exception as exc:
        logger.debug("生成图标失败，改写数据目录: %s", exc)

    fallback = os.path.join(app_data_dir(), "icon.ico")
    try:
        if not os.path.exists(fallback):
            render_icon(size).save(fallback, format="ICO", sizes=sizes)
        return fallback
    except Exception as exc:
        logger.warning("图标不可用: %s", exc)
        return None
