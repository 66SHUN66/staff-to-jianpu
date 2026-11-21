# -*- coding: utf-8 -*-
"""印刷级简谱渲染（Pillow 实现）。

对外接口：
    from lilipu.render import PrintJianpuRenderer, render_to_png, render_to_svg
"""

from .duration import analyze_duration  # noqa: F401
from .fonts import get_font  # noqa: F401
from .layout import LayoutEngine  # noqa: F401
from .print_renderer import PrintJianpuRenderer

#: 渲染能力可用标记（供调用方做降级判断，保持向后兼容）
RENDER_AVAILABLE = True

_default_renderer = None


def get_renderer(font_size=44, page_width=1200):
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = PrintJianpuRenderer(font_size=font_size, page_width=page_width)
    return _default_renderer


def render_to_png(notes, meta=None, output_path=None, font_size=44, page_width=1200):
    """便捷函数：渲染简谱为 PNG。"""
    r = PrintJianpuRenderer(font_size=font_size, page_width=page_width)
    return r.render_png(notes, meta, output_path)


def render_to_svg(notes, meta=None, output_path=None, font_size=44, page_width=1200):
    """便捷函数：渲染简谱为 SVG。"""
    r = PrintJianpuRenderer(font_size=font_size, page_width=page_width)
    return r.render_svg(notes, meta, output_path)
