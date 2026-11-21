# -*- coding: utf-8 -*-
"""印刷级简谱渲染：Pillow 输出 PNG，同时输出等价的 SVG。

渲染数据契约（由 ``lilipu.core.converter`` 产出）::

    {"type": "note", "num": "1", "octave": 1, "accidental": "", "midi": 72,
     "duration": 0.5, "dots": 0, "beat": 3.0, "offset": 0.0}
    {"type": "rest", "num": "0", "duration": 1.0, ...}
    {"type": "bar"}

``underlines`` / ``dashes`` 由 :func:`lilipu.render.duration.analyze_duration`
统一推导，调用方不必自己算。
"""

from __future__ import annotations

import html
import os
from typing import List, Optional, Sequence

from PIL import Image, ImageDraw

from ..logging_setup import get_logger
from .duration import analyze_duration
from .fonts import get_font
from .layout import LayoutEngine

logger = get_logger(__name__)

#: 小节线元素额外占用的横向空间（相对字号）
BAR_RATIO = 1.15
#: 增时线单条长度（相对字号）
DASH_RATIO = 1.05
#: 数字左右留白（相对字号）
PAD_RATIO = 0.42


class PrintJianpuRenderer:
    """把简谱元素画成印刷级图片。"""

    def __init__(self, font_size: int = 44, page_width: int = 1200, margin: int = 64):
        self.font_size = int(font_size)
        self.page_width = int(page_width)
        self.margin = int(margin)

        self.note_font = get_font(self.font_size, bold=True)
        self.title_font = get_font(max(20, int(self.font_size * 0.85)), bold=True)
        self.small_font = get_font(max(14, int(self.font_size * 0.55)), bold=False)

        self.pad = self.font_size * PAD_RATIO
        self.dash_len = self.font_size * DASH_RATIO
        self.bar_width = self.font_size * BAR_RATIO
        self.dot_radius = max(2, int(self.font_size * 0.075))
        self.underline_gap = max(3, int(self.font_size * 0.16))
        self.title_height = int(self.font_size * 2.0)

        self._measure_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # ---------------------------------------------------------------- 布局输入
    def _width(self, text: str, font=None) -> float:
        font = font or self.note_font
        try:
            return float(self._measure_draw.textlength(text, font=font))
        except Exception:  # 极端情况下退回估算
            box = self._measure_draw.textbbox((0, 0), text, font=font)
            return float(box[2] - box[0])

    def _note_payload(self, element: dict) -> dict:
        if element.get("type") == "rest":
            return {
                "num": "0", "accidental": "", "octave": 0,
                "underlines": 0, "dots": 0, "dashes": 0, "is_rest": True,
                "duration": element.get("duration", 1.0),
            }
        timing = analyze_duration(element.get("duration", 1.0), int(element.get("dots", 0) or 0))
        return {
            "num": str(element.get("num", "")),
            "accidental": str(element.get("accidental", "") or ""),
            "octave": int(element.get("octave", 0) or 0),
            "underlines": timing["underlines"],
            "dots": timing["dots"],
            "dashes": timing["dashes"],
            "is_rest": False,
            "duration": element.get("duration", 1.0),
        }

    def _item(self, element: dict) -> tuple:
        kind = element.get("type")
        if kind == "bar":
            return ("bar", element, self.bar_width)
        payload = self._note_payload(element)
        text = f"{payload['accidental']}{payload['num']}"
        width = self._width(text) + 2 * self.pad + payload["dashes"] * self.dash_len
        return ("note", payload, width)

    def build_items(self, notes: Sequence[dict]) -> List[tuple]:
        """把渲染数据转成 ``(kind, payload, width)`` 序列。"""
        return [self._item(el) for el in notes]

    def _layout_engine(self) -> LayoutEngine:
        return LayoutEngine(
            page_width=self.page_width,
            font_size=self.font_size,
            margin=self.margin,
            title_height=self.title_height,
        )

    def paginate(self, notes: Sequence[dict]) -> List[List[List[tuple]]]:
        return self._layout_engine().layout(self.build_items(notes))

    # ---------------------------------------------------------------- PNG
    def _header_text(self, meta: Optional[dict]) -> str:
        meta = meta or {}
        return f"{meta.get('key', '1=C')}   {meta.get('time', '4/4')}"

    def render_pages(self, notes: Sequence[dict], meta: Optional[dict] = None) -> List[Image.Image]:
        """逐页生成 RGB 图片。"""
        if not notes:
            return []
        engine = self._layout_engine()
        pages = engine.layout(self.build_items(notes))
        images = []
        for page in pages:
            height = engine.page_height(len(page))
            img = Image.new("RGB", (self.page_width, height), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            self._draw_header(draw, meta, page)
            for row_index, row in enumerate(page):
                self._draw_row(draw, row, engine.row_baseline(row_index))
            images.append(img)
        return images

    def render_png(self, notes: Sequence[dict], meta: Optional[dict] = None,
                   output_path: Optional[str] = None) -> Optional[Image.Image]:
        """渲染为 PNG；``notes`` 为空返回 ``None``。"""
        pages = self.render_pages(notes, meta)
        if not pages:
            return None
        if len(pages) == 1:
            img = pages[0]
        else:
            # 多页纵向拼接成一张长图，方便一次导出
            width = self.page_width
            height = sum(p.height for p in pages)
            img = Image.new("RGB", (width, height), (255, 255, 255))
            offset = 0
            for page in pages:
                img.paste(page, (0, offset))
                offset += page.height
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            img.save(output_path, format="PNG")
            logger.info("已输出 PNG: %s", output_path)
        return img

    def _draw_header(self, draw: ImageDraw.ImageDraw, meta: Optional[dict], page) -> None:
        draw.text((self.margin, self.margin), self._header_text(meta),
                  font=self.title_font, fill=(20, 20, 20))
        # 标题下的细分隔线，让谱面更整齐
        y = self.margin + self.title_height - self.font_size * 0.35
        draw.line([(self.margin, y), (self.page_width - self.margin, y)], fill=(210, 210, 210), width=1)

    def _draw_row(self, draw: ImageDraw.ImageDraw, row, y_top: int) -> None:
        for x_offset, kind, payload, width in row:
            x = self.margin + x_offset
            if kind == "bar":
                draw.line([(x + width / 2, y_top - self.font_size * 0.45),
                           (x + width / 2, y_top + self.font_size * 1.45)],
                          fill=(40, 40, 40), width=max(2, int(self.font_size * 0.05)))
                continue
            self._draw_note(draw, payload, x, y_top, width)

    def _draw_note(self, draw: ImageDraw.ImageDraw, payload: dict,
                   x: float, y_top: int, width: float) -> None:
        text = f"{payload['accidental']}{payload['num']}"
        font = self.note_font
        box = draw.textbbox((0, 0), text, font=font)
        text_w = box[2] - box[0]
        text_h = box[3] - box[1]
        tx = x + (self.pad + (width - 2 * self.pad - payload["dashes"] * self.dash_len - text_w) / 2) - box[0]
        ty = y_top + (self.font_size - text_h) / 2 - box[1]
        draw.text((tx, ty), text, font=font, fill=(15, 15, 15))

        center_x = x + (width - payload["dashes"] * self.dash_len) / 2

        # 高低音点
        octave = payload["octave"]
        if octave > 0:
            base_y = y_top - self.font_size * 0.18
            step = self.dot_radius * 2.6
            for i in range(min(octave, 3)):
                cy = base_y - i * step
                draw.ellipse([center_x - self.dot_radius, cy - self.dot_radius,
                              center_x + self.dot_radius, cy + self.dot_radius], fill=(15, 15, 15))
        elif octave < 0:
            base_y = y_top + self.font_size * 1.28
            step = self.dot_radius * 2.6
            for i in range(min(-octave, 3)):
                cy = base_y + i * step
                draw.ellipse([center_x - self.dot_radius, cy - self.dot_radius,
                              center_x + self.dot_radius, cy + self.dot_radius], fill=(15, 15, 15))

        # 减时线
        for i in range(payload["underlines"]):
            y = y_top + self.font_size * 1.14 + i * self.underline_gap
            draw.line([(x + self.pad * 0.4, y), (x + width - payload["dashes"] * self.dash_len - self.pad * 0.4, y)],
                      fill=(15, 15, 15), width=max(2, int(self.font_size * 0.035)))

        # 增时线（画成横线，比字符更整齐）
        for i in range(payload["dashes"]):
            left = x + width - (payload["dashes"] - i) * self.dash_len + self.dash_len * 0.12
            y = y_top + self.font_size * 0.5
            draw.line([(left, y), (left + self.dash_len * 0.78, y)],
                      fill=(15, 15, 15), width=max(2, int(self.font_size * 0.05)))

        # 附点
        if payload["dots"]:
            dot_x = x + width - payload["dashes"] * self.dash_len - self.pad * 0.1
            dot_y = y_top + self.font_size * 0.62
            r = self.dot_radius
            for i in range(int(payload["dots"])):
                draw.ellipse([dot_x - r, dot_y - r - i * r * 2.6, dot_x + r, dot_y + r - i * r * 2.6],
                             fill=(15, 15, 15))

    # ---------------------------------------------------------------- SVG
    def render_svg(self, notes: Sequence[dict], meta: Optional[dict] = None,
                   output_path: Optional[str] = None) -> Optional[str]:
        """输出矢量 SVG，字号与 PNG 一致，可直接放进网页或打印。"""
        if not notes:
            return None
        engine = self._layout_engine()
        pages = engine.layout(self.build_items(notes))
        page_heights = [engine.page_height(len(page)) for page in pages]
        total_height = sum(page_heights) or engine.page_height(0)

        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.page_width}" height="{total_height}" '
            f'viewBox="0 0 {self.page_width} {total_height}">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<style>text{font-family:"Noto Sans SC","Source Han Sans SC","Microsoft YaHei",sans-serif;'
            'fill:#111}.hdr{font-weight:700}.num{font-weight:700}</style>',
        ]

        offset_y = 0
        for page, page_height in zip(pages, page_heights):
            parts.append(f'<g transform="translate(0 {offset_y})">')
            parts.append(
                f'<text x="{self.margin}" y="{self.margin + int(self.font_size * 0.85)}" '
                f'class="hdr" font-size="{int(self.font_size * 0.85)}">'
                f'{html.escape(self._header_text(meta))}</text>'
            )
            line_y = self.margin + self.title_height - self.font_size * 0.35
            parts.append(f'<line x1="{self.margin}" y1="{line_y}" x2="{self.page_width - self.margin}" '
                         f'y2="{line_y}" stroke="#d2d2d2" stroke-width="1"/>')

            for row_index, row in enumerate(page):
                y_top = engine.row_baseline(row_index)
                for x_offset, kind, payload, width in row:
                    x = self.margin + x_offset
                    if kind == "bar":
                        parts.append(
                            f'<line x1="{x + width / 2:.1f}" y1="{y_top - self.font_size * 0.45:.1f}" '
                            f'x2="{x + width / 2:.1f}" y2="{y_top + self.font_size * 1.45:.1f}" '
                            f'stroke="#282828" stroke-width="{max(2, int(self.font_size * 0.05))}"/>'
                        )
                        continue
                    self._svg_note(parts, payload, x, y_top, width)
            parts.append('</g>')
            offset_y += page_height

        parts.append('</svg>')
        svg = "\n".join(parts)
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(svg)
            logger.info("已输出 SVG: %s", output_path)
        return svg

    def _svg_note(self, parts: List[str], payload: dict, x: float, y_top: int, width: float) -> None:
        text = html.escape(f"{payload['accidental']}{payload['num']}")
        dash_len = payload["dashes"] * self.dash_len
        center_x = x + (width - dash_len) / 2
        text_y = y_top + self.font_size * 0.72
        parts.append(
            f'<text x="{center_x:.1f}" y="{text_y:.1f}" text-anchor="middle" class="num" '
            f'font-size="{self.font_size}">{text}</text>'
        )

        octave = payload["octave"]
        r = self.dot_radius
        if octave > 0:
            for i in range(min(octave, 3)):
                cy = y_top - self.font_size * 0.18 - i * r * 2.6
                parts.append(f'<circle cx="{center_x:.1f}" cy="{cy:.1f}" r="{r}" fill="#111"/>')
        elif octave < 0:
            for i in range(min(-octave, 3)):
                cy = y_top + self.font_size * 1.28 + i * r * 2.6
                parts.append(f'<circle cx="{center_x:.1f}" cy="{cy:.1f}" r="{r}" fill="#111"/>')

        for i in range(payload["underlines"]):
            y = y_top + self.font_size * 1.14 + i * self.underline_gap
            parts.append(
                f'<line x1="{x + self.pad * 0.4:.1f}" y1="{y:.1f}" '
                f'x2="{x + width - dash_len - self.pad * 0.4:.1f}" y2="{y:.1f}" '
                f'stroke="#111" stroke-width="{max(2, int(self.font_size * 0.035))}"/>'
            )

        for i in range(payload["dashes"]):
            left = x + width - (payload["dashes"] - i) * self.dash_len + self.dash_len * 0.12
            y = y_top + self.font_size * 0.5
            parts.append(
                f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + self.dash_len * 0.78:.1f}" y2="{y:.1f}" '
                f'stroke="#111" stroke-width="{max(2, int(self.font_size * 0.05))}"/>'
            )

        if payload["dots"]:
            dot_x = x + width - dash_len - self.pad * 0.1
            dot_y = y_top + self.font_size * 0.62
            for i in range(int(payload["dots"])):
                parts.append(
                    f'<circle cx="{dot_x:.1f}" cy="{dot_y - i * r * 2.6:.1f}" r="{r}" fill="#111"/>'
                )
