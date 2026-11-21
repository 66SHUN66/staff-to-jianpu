# -*- coding: utf-8 -*-
"""排版引擎：按小节宽度分行、按页高分页。

渲染器只负责“画”，换行和分页这类几何问题都交给这里，
方便以后加标题区、歌词区而不影响画法。
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


class LayoutEngine:
    """把一串带宽度的小节排成行，再把行排成页。"""

    def __init__(self, page_width: int = 1200, font_size: int = 44,
                 margin: int = 64, title_height: int = 0,
                 max_page_height: int = 1700):
        self.page_width = int(page_width)
        self.font_size = int(font_size)
        self.margin = int(margin)
        self.title_height = int(title_height)
        self.max_page_height = int(max_page_height)

        self.content_width = max(1, self.page_width - 2 * self.margin)
        # 行高留出高音点、减时线和增时线的空间
        self.row_height = int(self.font_size * 2.0) + 16
        usable = max(1, self.max_page_height - 2 * self.margin - self.title_height)
        self.rows_per_page = max(1, usable // self.row_height)

    # ---- 分行 ----
    def split_measures(self, items: Sequence[Tuple[str, object, float]]) -> List[List[Tuple[str, object, float]]]:
        """按 ``bar`` 元素切分成小节；末尾没有小节线的内容单独成段。"""
        measure: List[Tuple[str, object, float]] = []
        measures: List[List[Tuple[str, object, float]]] = []
        for item in items:
            measure.append(item)
            if item[0] == "bar":
                measures.append(measure)
                measure = []
        if measure:
            measures.append(measure)
        return measures

    def pack_measures(self, measures: Iterable[Sequence[Tuple[str, object, float]]]) -> List[List[List[Tuple[float, str, object, float]]]]:
        """返回页 → 行 → [(x, kind, payload, width)] 的嵌套结构。"""
        measures = list(measures)
        measure_widths = [sum(it[2] for it in m) for m in measures]

        rows: List[List[Tuple[float, str, object, float]]] = []
        row: List[Tuple[float, str, object, float]] = []
        x = 0.0
        for measure, width in zip(measures, measure_widths):
            # 单小节本身超宽时也允许独占一行，避免无限循环
            if row and x + width > self.content_width:
                rows.append(row)
                row = []
                x = 0.0
            for kind, payload, item_width in measure:
                row.append((x, kind, payload, item_width))
                x += item_width
        if row:
            rows.append(row)

        pages: List[List[List[Tuple[float, str, object, float]]]] = []
        for index in range(0, len(rows), self.rows_per_page):
            pages.append(rows[index:index + self.rows_per_page])
        return pages or [[]]

    def layout(self, items: Sequence[Tuple[str, object, float]]) -> List[List[List[Tuple[float, str, object, float]]]]:
        """一步完成：元素序列 → 页 → 行。"""
        return self.pack_measures(self.split_measures(items))

    # ---- 坐标 ----
    def page_height(self, row_count: int) -> int:
        height = 2 * self.margin + self.title_height + row_count * self.row_height
        return max(height, 320)

    def row_baseline(self, row_index: int) -> int:
        """某一行音符数字的“顶线”y 坐标。"""
        return self.margin + self.title_height + row_index * self.row_height + int(self.font_size * 0.75)
