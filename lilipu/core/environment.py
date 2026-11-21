# -*- coding: utf-8 -*-
"""运行环境探测：Audiveris、Java、OpenCV、music21。

界面只依赖这里的结论，不做自己的平台判断，方便以后换引擎。
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

from ..logging_setup import get_logger

logger = get_logger(__name__)

AUDIVERIS_HINTS = {
    "win32": [
        r"C:\Program Files\Audiveris\Audiveris.exe",
        r"C:\Program Files\Audiveris\audiveris.bat",
        r"C:\Program Files (x86)\Audiveris\Audiveris.exe",
    ],
    "darwin": [
        "/Applications/Audiveris.app/Contents/MacOS/Audiveris",
        "/Applications/Audiveris.app/Contents/MacOS/audiveris",
    ],
}


def _glob_candidates(patterns: list) -> list:
    found = []
    for pattern in patterns:
        try:
            found.extend(sorted(glob.glob(pattern)))
        except Exception:
            continue
    return found


def find_audiveris() -> str | None:
    """按环境变量 → PATH → 常见安装目录的顺序查找 Audiveris。"""
    env = os.environ.get("LILIPU_AUDIVERIS")
    if env and os.path.exists(env):
        return env

    for name in ("audiveris", "Audiveris", "audiveris.bat", "Audiveris.exe"):
        hit = shutil.which(name)
        if hit:
            return hit

    candidates = list(AUDIVERIS_HINTS.get(sys.platform, []))
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(os.path.join(local, "Audiveris", "Audiveris.exe"))
        candidates.append(r"C:\Program Files\Audiveris\*")
    elif sys.platform == "darwin":
        candidates.append("/Applications/Audiveris*.app/Contents/MacOS/*")
    else:
        candidates += [
            "/opt/audiveris/bin/audiveris",
            "/usr/local/bin/audiveris",
            "/usr/bin/audiveris",
            os.path.expanduser("~/Audiveris/bin/audiveris"),
        ]
    for path in candidates:
        if "*" in path:
            for hit in _glob_candidates([path]):
                if os.path.isfile(hit):
                    return hit
            continue
        if os.path.exists(path):
            return path
    return None


def find_java() -> str | None:
    """Audiveris 5+ 自带 JRE；这里找的是可选的系统 Java。"""
    for name in ("java", "java.exe"):
        hit = shutil.which(name)
        if hit:
            return hit
    for path in (
        r"C:\Program Files\Java\jdk-17\bin\java.exe",
        r"C:\Program Files\Eclipse Adoptium\jdk-17*\bin\java.exe",
        "/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/java",
        "/usr/lib/jvm/*/bin/java",
    ):
        if "*" in path:
            hits = _glob_candidates([path])
            if hits:
                return hits[0]
        elif os.path.exists(path):
            return path
    return None


def _version_of(exe: str, args: list) -> str:
    try:
        out = subprocess.run([exe] + args, capture_output=True, text=True, timeout=15)
        text = (out.stdout or "") + (out.stderr or "")
        for line in text.splitlines():
            line = line.strip()
            if any(ch.isdigit() for ch in line) and len(line) < 120:
                return line
    except Exception:
        pass
    return ""


class EnvironmentChecker:
    """一次性收集所有引擎的状态，界面据此决定默认引擎。"""

    def __init__(self, probe_version: bool = True):
        self.probe_version = probe_version

    def check(self) -> dict:
        audiveris = find_audiveris()
        info = {
            "platform": sys.platform,
            "audiveris_path": audiveris,
            "audiveris": bool(audiveris),
            "audiveris_version": _version_of(audiveris, ["-version"])[:60] if (audiveris and self.probe_version) else "",
            "java_path": find_java(),
            "opencv": _has_module("cv2"),
            "music21": _has_module("music21"),
            "fallback_ready": _has_module("cv2") and _has_module("numpy"),
        }
        info["java"] = bool(info["java_path"])
        info["engine"] = "audiveris" if info["audiveris"] else ("opencv" if info["fallback_ready"] else "none")
        info["engine_label"] = {
            "audiveris": "引擎：Audiveris 高精度识别",
            "opencv": "引擎：OpenCV 音高草图（不识别调号/节奏）",
            "none": "引擎：未就绪（缺 Audiveris 且缺 OpenCV）",
        }[info["engine"]]
        info["suggestion"] = self._suggestion(info)
        logger.info("环境探测结果: %s", info["engine_label"])
        return info

    @staticmethod
    def _suggestion(info: dict) -> str:
        if info["audiveris"]:
            return "已检测到 Audiveris，可识别调号、拍号与完整节奏。"
        if info["fallback_ready"]:
            return (
                "未检测到 Audiveris，当前只能输出音高草图。\n"
                "想要完整简谱：安装 Audiveris（自带 Java，无需另装 JDK），"
                "装好重启本程序即可自动切换。"
            )
        return "既没有 Audiveris 也没有 OpenCV，无法识别。请重新安装依赖或使用源码运行。"


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def quick_engine() -> str:
    """轻量判断（不探测版本），供启动时使用。"""
    if find_audiveris():
        return "audiveris"
    return "opencv" if _has_module("cv2") else "none"
