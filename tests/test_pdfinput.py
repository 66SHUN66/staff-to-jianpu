# -*- coding: utf-8 -*-
"""PDF 拆页测试：一页 PDF 应产出一张 PNG。"""

from __future__ import annotations

import os

import pytest

pymupdf = pytest.importorskip("pymupdf")

from lilipu.core.pdfinput import pdf_to_images  # noqa: E402


def test_pdf_to_images(tmp_path):
    pdf_path = tmp_path / "score.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "staff notation page 1")
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    images = pdf_to_images(str(pdf_path), dpi=100, out_dir=str(tmp_path / "out"))
    assert len(images) == 2, "两页 PDF 应拆出两张图"
    for path in images:
        assert os.path.exists(path)
