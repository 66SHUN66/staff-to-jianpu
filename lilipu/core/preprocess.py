# -*- coding: utf-8 -*-
"""图像预处理（OpenCV 可选）。

Audiveris 对倾斜、低分辨率、偏暗的图很敏感，先做一轮标准化能明显提升识别率：
灰度化 → 小图放大 → 去噪 → 自适应二值化 → 倾斜校正。
没有 OpenCV 时直接返回原图，不影响主流程。
"""

from __future__ import annotations

import os
import shutil

from ..logging_setup import get_logger
from ..paths import temp_dir

logger = get_logger(__name__)


def cv_available() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def _imread(path: str):
    import cv2
    import numpy as np

    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _imwrite(path: str, image) -> bool:
    import cv2

    ext = os.path.splitext(path)[1] or ".png"
    ok, buffer = cv2.imencode(ext, image)
    if not ok:
        return False
    buffer.tofile(path)
    return True


def _deskew(gray):
    """按暗色像素的最小外接矩形估计倾斜角，超过 0.3° 才旋转。"""
    import cv2
    import numpy as np

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if coords.size == 0:
        return gray, 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.3:
        return gray, 0.0
    height, width = gray.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(gray, matrix, (width, height),
                             flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle


def preprocess_image(src: str, dst_dir: str | None = None) -> str:
    """返回预处理后的图片路径；失败或缺少 OpenCV 时返回原路径。"""
    if not cv_available():
        return src
    dst_dir = dst_dir or temp_dir("pre")
    os.makedirs(dst_dir, exist_ok=True)

    image = _imread(src)
    if image is None:
        logger.warning("图像读取失败，跳过预处理: %s", src)
        return src

    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 手机拍的谱子常见宽度不足 1500px，放大两倍对小音符识别帮助很大
    height, width = gray.shape[:2]
    if width < 1500:
        scale = min(3.0, 1500 / max(1, width))
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 31, 10)
    binary, angle = _deskew(binary)

    stem = os.path.splitext(os.path.basename(src))[0]
    out_path = os.path.join(dst_dir, f"{stem}_pre.png")
    if not _imwrite(out_path, binary):
        logger.warning("预处理结果写入失败，改用原图: %s", src)
        return src
    if angle:
        logger.info("已校正倾斜 %.1f°: %s", -angle, os.path.basename(src))
    return out_path


def copy_as_png(src: str, dst_dir: str | None = None) -> str:
    """缺少 OpenCV 时的兜底：把原图复制到临时目录，统一由流水线管理生命周期。"""
    dst_dir = dst_dir or temp_dir("pre")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    try:
        shutil.copyfile(src, dst)
        return dst
    except Exception:
        return src
