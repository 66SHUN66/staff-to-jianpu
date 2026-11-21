# -*- coding: utf-8 -*-
"""时值分析：把 quarterLength 换算成简谱的减时线、增时线和附点。"""

from __future__ import annotations

#: 简谱常用时值等级（单位：四分音符 = 1）
_CANDIDATES = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25)

#: 每个等级对应的简谱写法：(减时线条数, 附点数, 增时线数量)
_TABLE = {
    4.0: (0, 0, 3),
    3.0: (0, 0, 2),
    2.0: (0, 0, 1),
    1.5: (0, 1, 0),
    1.0: (0, 0, 0),
    0.75: (1, 1, 0),
    0.5: (1, 0, 0),
    0.25: (2, 0, 0),
}


def analyze_duration(quarter_length: float, dots: int = 0) -> dict:
    """返回 ``{quarters, level, underlines, dots, dashes}``。

    - ``underlines``：音符下方的减时线条数（八分音符 1 条，十六分音符 2 条）
    - ``dots``：附点数（附点四分、附点八分）
    - ``dashes``：音符后面的增时线数量（二分音符 1 条，全音符 3 条）
    """
    try:
        ql = float(quarter_length)
    except (TypeError, ValueError):
        ql = 1.0
    if ql <= 0:
        ql = 1.0

    # 落到最近的常用时值，避免 0.4999 这类浮点误差被判成十六分音符
    level = min(_CANDIDATES, key=lambda c: abs(c - ql))
    underlines, aug_dots, dashes = _TABLE[level]
    if dots and aug_dots == 0 and level >= 1.0:
        # music21 明确给了附点，但时值受连音线影响被抹平时，仍按附点显示
        aug_dots = int(dots)

    return {
        "quarters": ql,
        "level": level,
        "underlines": underlines,
        "dots": aug_dots,
        "dashes": dashes,
    }


def duration_label(quarter_length: float) -> str:
    """给界面/日志用的中文时值名。"""
    level = analyze_duration(quarter_length)["level"]
    return {
        4.0: "全音符",
        3.0: "附点二分音符",
        2.0: "二分音符",
        1.5: "附点四分音符",
        1.0: "四分音符",
        0.75: "附点八分音符",
        0.5: "八分音符",
        0.25: "十六分音符",
    }.get(level, "四分音符")
