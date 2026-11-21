# -*- coding: utf-8 -*-
"""批处理流水线：输入整理 → 预处理 → OMR → 简谱转换 → 渲染 → 历史记录。

界面只调用 :class:`ScoreConverter`，不关心底层用哪种引擎。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..logging_setup import get_logger
from ..paths import temp_dir
from ..render import render_to_png, render_to_svg
from . import fallback
from .audiveris import AudiverisRunner
from .converter import JianpuConverter
from .history import HistoryManager
from .pdfinput import pdf_to_images
from .preprocess import preprocess_image

logger = get_logger(__name__)

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
PDF_SUFFIXES = (".pdf",)

#: 进度回调类型：(阶段说明, 0~1 的进度)
ProgressCallback = Callable[[str, float], None]


@dataclass
class Result:
    """单张谱面的转换结果。"""

    ok: bool
    source: str
    engine: str = ""
    text: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    notes: List[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    png_path: Optional[str] = None
    svg_path: Optional[str] = None
    xml_path: Optional[str] = None
    elapsed: float = 0.0
    error: str = ""

    @property
    def has_sketch(self) -> bool:
        return bool(self.meta.get("mode") == "sketch")

    def summary(self) -> str:
        if not self.ok:
            return f"{os.path.basename(self.source)}：失败（{self.error or '未知原因'}）"
        name = os.path.basename(self.source)
        return f"{name}：{self.meta.get('key', '?')} {self.meta.get('time', '?')}，{len(self.notes)} 个元素"


class ScoreConverter:
    """把图片/PDF 转成简谱的统一入口。"""

    def __init__(self, converter: JianpuConverter | None = None,
                 runner: AudiverisRunner | None = None,
                 history: HistoryManager | None = None,
                 keep_artifacts: bool = True):
        self.converter = converter or JianpuConverter()
        self.runner = runner or AudiverisRunner()
        self.history = history or HistoryManager()
        self.keep_artifacts = keep_artifacts

    # ---------------------------------------------------------------- 输入
    @staticmethod
    def inputs_to_images(paths: List[str], on_progress: ProgressCallback | None = None) -> List[str]:
        """把用户选的文件整理成图片列表：PDF 按页拆开，图片原样保留。"""
        images: List[str] = []
        seen = set()
        total = max(1, len(paths))
        for index, path in enumerate(paths):
            if not path or not os.path.exists(path):
                logger.warning("输入不存在，跳过: %s", path)
                continue
            suffix = os.path.splitext(path)[1].lower()
            if suffix in PDF_SUFFIXES:
                try:
                    pages = pdf_to_images(path)
                except Exception as exc:
                    logger.exception("PDF 拆页失败: %s", path)
                    raise RuntimeError(f"PDF 拆页失败（{os.path.basename(path)}）：{exc}") from exc
                for page in pages:
                    if page not in seen:
                        seen.add(page)
                        images.append(page)
            elif suffix in IMAGE_SUFFIXES:
                if path not in seen:
                    seen.add(path)
                    images.append(path)
            else:
                logger.warning("不支持的文件类型，跳过: %s", path)
            if on_progress:
                on_progress(f"整理输入 {index + 1}/{total}", (index + 1) / total * 0.2)
        return images

    # ---------------------------------------------------------------- 转换
    def _engine(self, engine: str) -> str:
        engine = (engine or "auto").lower()
        if engine != "auto":
            return engine
        return "audiveris" if self.runner.available else "opencv"

    def _render(self, result: Result, stem: str) -> None:
        if not result.notes:
            return
        out_dir = temp_dir("out")
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = f"{stem}_{stamp}"
        try:
            png_path = os.path.join(out_dir, base + ".png")
            if render_to_png(result.notes, result.meta, png_path) is not None:
                result.png_path = png_path
        except Exception as exc:
            logger.exception("PNG 渲染失败")
            result.warnings.append(f"PNG 渲染失败：{exc}")
        try:
            svg_path = os.path.join(out_dir, base + ".svg")
            if render_to_svg(result.notes, result.meta, svg_path):
                result.svg_path = svg_path
        except Exception as exc:
            logger.exception("SVG 渲染失败")
            result.warnings.append(f"SVG 渲染失败：{exc}")

    def convert_one(self, image_path: str, engine: str = "auto") -> Result:
        """转换单张图片。"""
        started = time.time()
        engine = self._engine(engine)
        result = Result(ok=False, source=image_path, engine=engine)

        if engine == "audiveris" and self.runner.available:
            prepared = preprocess_image(image_path)
            omr = self.runner.run(prepared)
            result.elapsed = omr.get("elapsed", 0.0)
            if omr["ok"]:
                text, warnings, notes, meta = self.converter.convert(omr["musicxml"])
                result.text = text
                result.warnings.extend(warnings)
                result.notes = notes
                result.meta = meta
                result.xml_path = omr["musicxml"]
                result.ok = bool(notes)
                if not result.ok:
                    result.error = "MusicXML 转换后没有音符"
            else:
                result.error = omr.get("error", "Audiveris 识别失败")
                result.warnings.append(result.error)
                if omr.get("log"):
                    result.warnings.append("Audiveris 日志末尾：\n" + omr["log"][-1200:])
        elif engine == "audiveris":
            result.error = "未检测到 Audiveris，已自动改用 OpenCV 草图模式。"
            result.warnings.append(result.error)
            engine = result.engine = "opencv"

        if not result.ok and engine in ("opencv", "audiveris"):
            text, warnings, notes, meta = fallback.convert(image_path)
            if notes:
                result.text = text
                result.notes = notes
                result.meta = meta
                result.warnings.extend(warnings)
                result.engine = "opencv"
                result.ok = True
            elif not result.error:
                result.error = "未能识别出任何音符"
                result.warnings.extend(warnings)

        if result.ok:
            stem = os.path.splitext(os.path.basename(image_path))[0]
            self._render(result, stem)
            try:
                self.history.add(image_path, result.text or "", result.meta,
                                 engine=result.engine, warnings=result.warnings)
            except Exception:
                logger.exception("写入历史记录失败")

        elapsed = time.time() - started
        result.elapsed = max(result.elapsed, elapsed)
        if result.elapsed <= 0:
            result.elapsed = elapsed
        logger.info("结果: %s", result.summary())
        return result

    def convert_files(self, paths: List[str], engine: str = "auto",
                      on_progress: ProgressCallback | None = None) -> List[Result]:
        """批量转换，失败项不影响后续项。"""
        images = self.inputs_to_images(paths, on_progress)
        results: List[Result] = []
        total = max(1, len(images))
        for index, image in enumerate(images):
            if on_progress:
                on_progress(f"识别 {index + 1}/{total}：{os.path.basename(image)}",
                            0.2 + 0.7 * index / total)
            try:
                results.append(self.convert_one(image, engine))
            except Exception as exc:
                logger.exception("转换异常: %s", image)
                results.append(Result(ok=False, source=image, error=str(exc),
                                      warnings=[f"转换异常：{exc}"]))
        if on_progress:
            on_progress("完成", 1.0)
        return results
