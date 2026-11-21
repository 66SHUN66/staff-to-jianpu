# -*- coding: utf-8 -*-
"""OpenCV 降级识别：只估音高轮廓，不识别调号、节奏和小节线。

这不是“完整简谱”，界面和结果里都会显式提示用户。
定位五线谱行 → 找音符头 → 按纵向位置换算音级。
"""

from __future__ import annotations

from typing import List, Tuple

from ..logging_setup import get_logger

logger = get_logger(__name__)

SKETCH_NOTICE = (
    "当前是 OpenCV 音高草图模式：只按纵向位置估算音高，"
    "不识别调号、节奏时值和小节线，不能当作完整简谱使用。"
    "需要完整结果请安装 Audiveris。"
)

#: 高音谱号下，最下面一条线是 E4；用“字母序号 + 7×八度”表示音级序号
_E4_DIATONIC = 4 * 7 + 2


def _load_gray(path: str):
    import cv2
    import numpy as np

    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    return image


def _staff_rows(binary) -> List[int]:
    """返回所有五线谱线的 y 坐标（每 5 条为一组）。"""
    import cv2
    import numpy as np

    height, width = binary.shape[:2]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, width // 25), 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    density = (horizontal > 0).sum(axis=1) / max(1, width)
    rows = [int(y) for y in np.where(density > 0.45)[0]]
    lines: List[int] = []
    for y in rows:
        if lines and y - lines[-1] <= 2:
            continue
        lines.append(y)
    return lines


def _group_staffs(lines: List[int]) -> List[List[int]]:
    """把相邻等距的 5 条线归为一组谱表。"""
    groups: List[List[int]] = []
    current: List[int] = []
    for y in lines:
        if not current:
            current = [y]
            continue
        gap = y - current[-1]
        if gap <= 30 and (len(current) < 2 or gap <= (current[-1] - current[0]) / max(1, len(current) - 1) * 2.2):
            current.append(y)
            if len(current) == 5:
                groups.append(current)
                current = []
        else:
            current = [y]
    if len(current) >= 5:
        groups.append(current[:5])
    return groups


def _note_heads(binary, staff_groups: List[List[int]]) -> List[Tuple[int, int]]:
    """找音符头：面积和宽高比在合理区间，且靠近谱表。"""
    import cv2

    height, width = binary.shape[:2]
    spacing = 1.0
    if staff_groups:
        top = staff_groups[0][0]
        spacing = max(4.0, (staff_groups[0][4] - top) / 4.0)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    heads: List[Tuple[int, int]] = []
    min_area = max(12, int(spacing * spacing * 0.6))
    max_area = int(spacing * spacing * 22)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        ratio = w / float(h)
        if not (0.7 <= ratio <= 2.6):
            continue
        if w > spacing * 3.2 or h > spacing * 2.0:
            continue
        if not staff_groups and not (height * 0.05 < y < height * 0.95):
            continue
        heads.append((x + w // 2, y + h // 2))
    heads.sort()
    return heads


def convert(image_path: str) -> Tuple[str | None, List[str], List[dict], dict]:
    """返回 ``(文本, 警告, 渲染数据, 元信息)``，与 JianpuConverter 保持同构。"""
    warnings: List[str] = [SKETCH_NOTICE]
    gray = _load_gray(image_path)
    if gray is None:
        return None, ["图片读取失败，请确认文件未损坏。"], [], {}

    try:
        import cv2

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        lines = _staff_rows(binary)
        staffs = _group_staffs(lines)
        if not staffs:
            warnings.append("没有检测到五线谱，可能是图片模糊或不是谱面照片。")
            return None, warnings, [], {}
        heads = _note_heads(binary, staffs)
    except Exception as exc:
        logger.exception("OpenCV 草图识别失败")
        return None, [f"OpenCV 识别失败：{exc}"], [], {}

    if not heads:
        warnings.append("没有检测到音符头，无法给出音高草图。")
        return None, warnings, [], {}

    from .converter import note_token

    spacing = (staffs[0][4] - staffs[0][0]) / 4.0
    bottom = staffs[0][4]
    notes: List[dict] = []
    offset = 0.0

    for _x, y in heads[:400]:
        step = (bottom - y) / (spacing / 2.0)  # 以半格为单位
        diatonic = _E4_DIATONIC + int(round(step))
        delta = diatonic - 28  # C4 记为 0
        degree = delta % 7 + 1
        octave = delta // 7
        notes.append({
            "type": "note",
            "num": str(degree),
            "octave": int(octave),
            "accidental": "",
            "pname": "",
            "midi": 60 + diatonic - 28,
            "duration": 1.0,
            "dots": 0,
            "beat": offset,
            "offset": offset,
        })
        offset += 1.0

    meta = {
        "key": "1=?",
        "time": "?",
        "mode": "sketch",
        "measures": 0,
        "note_count": len(notes),
        "staffs": len(staffs),
    }
    text = " ".join(note_token(n) for n in notes)
    warnings.append(f"按 {len(staffs)} 行谱表、{len(heads)} 个音符头估算；小节与节奏均为占位值。")
    logger.info("OpenCV 草图完成：%d 个音符头", len(heads))
    return text, warnings, notes, meta
