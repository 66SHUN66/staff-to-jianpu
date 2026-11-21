# -*- coding: utf-8 -*-
"""向后兼容垫片。

旧版文档/脚本里的 `from render_jianpu import render_jianpu` 写法仍可用，
内部转发到 :mod:`lilipu.render`。
"""

from lilipu.render import RENDER_AVAILABLE, render_to_png, render_to_svg

try:
    from lilipu.render.print_renderer import PrintJianpuRenderer as JianpuRenderer
except Exception:  # pragma: no cover
    JianpuRenderer = None


def render_jianpu(notes, meta, output_path, font_size=44, page_width=1200):
    return render_to_png(notes, meta, output_path, font_size=font_size, page_width=page_width)


__all__ = ["RENDER_AVAILABLE", "JianpuRenderer", "render_jianpu", "render_to_png", "render_to_svg"]
