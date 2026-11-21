# -*- coding: utf-8 -*-
"""字体查找测试：必须返回可用字体对象，不允许抛异常。"""

from __future__ import annotations

from lilipu.render.fonts import get_font


def test_get_font_returns_object():
    font = get_font(24)
    assert font is not None


def test_font_is_cached_and_reusable():
    a = get_font(32)
    b = get_font(32)
    assert a is b, "同字号应命中缓存，避免反复读字体文件"
