# -*- coding: utf-8 -*-
"""PDF 输入支持：把多页 PDF 逐页栅格化成 PNG，交给识别流水线。"""

from __future__ import annotations

import os

from ..logging_setup import get_logger
from ..paths import temp_dir

logger = get_logger(__name__)


def pdf_to_images(pdf_path: str, dpi: int = 200, out_dir: str | None = None) -> list:
    """把 PDF 每一页渲染成 PNG，返回按页码排序的文件路径列表。

    Args:
        pdf_path: PDF 文件路径。
        dpi: 渲染分辨率，200 足够 Audiveris 识别五线谱。
        out_dir: 输出目录，默认放到应用临时目录下的 pdf/ 里。
    """
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("缺少 PDF 解析库，请执行 pip install pymupdf") from exc

    out_dir = out_dir or os.path.join(temp_dir(), "pdf")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    paths = []
    with pymupdf.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            out_path = os.path.join(out_dir, f"{stem}_p{index + 1}.png")
            pix.save(out_path)
            paths.append(out_path)
    logger.info("PDF 拆页完成: %s -> %d 页", os.path.basename(pdf_path), len(paths))
    return paths
