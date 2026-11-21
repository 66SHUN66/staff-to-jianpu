# -*- coding: utf-8 -*-
"""Audiveris 调用封装。

Audiveris 5 的命令行用法::

    audiveris -batch -export -output <输出目录> <图片或PDF>

批量模式下它会为每个输入生成 ``<名字>.mxl``（压缩 MusicXML）和 ``<名字>.omr``。
这里负责拼命令、等结果、把日志尾巴带回去给界面显示。
"""

from __future__ import annotations

import os
import subprocess
import time

from ..logging_setup import get_logger
from ..paths import temp_dir
from .environment import find_audiveris

logger = get_logger(__name__)

OUTPUT_SUFFIXES = (".mxl", ".musicxml", ".xml")


class AudiverisRunner:
    """单文件 OMR 执行器。"""

    def __init__(self, executable: str | None = None, timeout: int = 300):
        self.executable = executable or find_audiveris()
        self.timeout = int(timeout)

    @property
    def available(self) -> bool:
        return bool(self.executable and os.path.exists(self.executable))

    def _command(self, image_path: str, out_dir: str) -> list:
        return [self.executable, "-batch", "-export", "-output", out_dir, "-force", image_path]

    def run(self, image_path: str, out_dir: str | None = None,
            timeout: int | None = None) -> dict:
        """执行识别，返回 ``{ok, musicxml, log, error, elapsed}``。"""
        started = time.time()
        if not self.available:
            return {"ok": False, "musicxml": None, "log": "", "elapsed": 0.0,
                    "error": "未找到 Audiveris，请先安装或设置 LILIPU_AUDIVERIS 环境变量。"}

        out_dir = out_dir or temp_dir("omr", os.path.splitext(os.path.basename(image_path))[0])
        os.makedirs(out_dir, exist_ok=True)

        cmd = self._command(image_path, out_dir)
        logger.info("执行 Audiveris: %s", " ".join(cmd))
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                creationflags=creationflags,
                shell=bool(self.executable and self.executable.lower().endswith((".bat", ".cmd"))),
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - started
            logger.warning("Audiveris 超时（%.0f 秒）", elapsed)
            return {"ok": False, "musicxml": None, "log": "", "elapsed": elapsed,
                    "error": f"识别超时（超过 {timeout or self.timeout} 秒），可尝试降低图片分辨率或换更清晰的谱面。"}
        except Exception as exc:
            logger.exception("Audiveris 启动失败")
            return {"ok": False, "musicxml": None, "log": "", "elapsed": time.time() - started,
                    "error": f"无法启动 Audiveris：{exc}"}

        log = "\n".join(part for part in (completed.stdout, completed.stderr) if part)[-4000:]
        musicxml = self._find_result(out_dir, image_path)
        elapsed = time.time() - started

        if not musicxml:
            error = "Audiveris 未产出 MusicXML"
            if completed.returncode != 0:
                error += f"（退出码 {completed.returncode}）"
            if "Exception" in log or "Error" in log:
                error += "；日志见下方"
            return {"ok": False, "musicxml": None, "log": log, "elapsed": elapsed, "error": error}

        logger.info("Audiveris 识别完成，用时 %.1f 秒", elapsed)
        return {"ok": True, "musicxml": musicxml, "log": log, "elapsed": elapsed, "error": ""}

    @staticmethod
    def _find_result(out_dir: str, image_path: str) -> str | None:
        stem = os.path.splitext(os.path.basename(image_path))[0].lower()
        best = None
        for dirpath, _dirnames, filenames in os.walk(out_dir):
            for name in filenames:
                if not name.lower().endswith(OUTPUT_SUFFIXES):
                    continue
                path = os.path.join(dirpath, name)
                if stem and stem in name.lower():
                    return path
                best = best or path
        return best
