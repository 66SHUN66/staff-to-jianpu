# -*- coding: utf-8 -*-
"""渲染模块测试：能出图、尺寸正确、画面不是空白。"""

from __future__ import annotations

from lilipu.render import render_to_png, render_to_svg

META = {"key": "1=C", "time": "4/4"}

NOTES = [
    {"type": "note", "num": "1", "octave": 1, "accidental": "", "midi": 72,
     "duration": 0.5, "dots": 0, "beat": 3.0, "offset": 0.0},
    {"type": "note", "num": "2", "octave": 1, "accidental": "", "midi": 74,
     "duration": 0.5, "dots": 0, "beat": 3.5, "offset": 0.5},
    {"type": "note", "num": "3", "octave": 1, "accidental": "", "midi": 76,
     "duration": 0.5, "dots": 0, "beat": 4.0, "offset": 1.0},
    {"type": "note", "num": "5", "octave": 0, "accidental": "#", "midi": 68,
     "duration": 1.0, "dots": 0, "beat": 4.5, "offset": 1.5},
    {"type": "bar", "offset": 2.5},
]


def test_render_png(tmp_path):
    out = tmp_path / "jianpu.png"
    img = render_to_png(NOTES, META, str(out))
    assert img is not None, "渲染应返回 PIL.Image"
    assert img.size[0] == 1200, "页宽应等于默认 page_width"
    assert img.size[1] > 0
    assert out.exists()

    # 画面必须存在深色像素，避免出现“全白空图”
    low, _high = img.convert("L").getextrema()
    assert low < 200


def test_render_svg(tmp_path):
    out = tmp_path / "jianpu.svg"
    svg = render_to_svg(NOTES, META, str(out))
    assert "<svg" in svg
    assert "1=C" in svg
    assert out.exists()


def test_empty_notes_returns_none(tmp_path):
    assert render_to_png([], META, str(tmp_path / "empty.png")) is None
