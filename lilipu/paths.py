# -*- coding: utf-8 -*-
"""跨平台路径：用户数据目录、临时目录、打包资源定位。

设计要点：
- 数据目录按平台惯例放置（Windows 用 %APPDATA%，macOS 用 Application Support，
  Linux 用 XDG_DATA_HOME），不再写死某个盘符。
- 临时产物统一放在系统临时目录下的 ``lilipu`` 子目录，便于集中清理。
- 打包后资源既可能在 PyInstaller 的 ``_MEIPASS``，也可能在 exe 同级目录。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

from . import APP_ID, LEGACY_APP_ID


def _frozen_dir() -> str:
    """打包运行时的可执行文件所在目录；源码运行时返回空串。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return ""


def project_root() -> str:
    """源码根目录，或打包后的 exe 所在目录。"""
    frozen = _frozen_dir()
    if frozen:
        return frozen
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """定位随包资源（字体、示例图、图标等）。

    查找顺序：PyInstaller 解包目录 → exe 同级目录 → 源码根目录。
    找不到时返回源码根目录下的拼接路径，调用方可据此判断“不存在”。
    """
    bases = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(meipass)
    bases.append(project_root())
    for base in bases:
        candidate = os.path.join(base, *parts)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(bases[-1], *parts)


def _data_home() -> str:
    """各平台的用户数据根目录。"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return base


def app_data_dir(create: bool = True) -> str:
    """本程序的数据目录（历史记录、日志、图标兜底）。"""
    path = os.path.join(_data_home(), APP_ID)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def legacy_data_dir() -> str:
    """旧版本（ScoreConverter）的数据目录，仅用于迁移。"""
    return os.path.join(_data_home(), LEGACY_APP_ID)


def temp_dir(*parts: str, create: bool = True) -> str:
    """系统临时目录下的工作区，可继续向下拼接子路径。"""
    path = os.path.join(tempfile.gettempdir(), APP_ID.lower(), *parts)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def cleanup_temp_dir(max_age_days: int = 7, root: str | None = None) -> int:
    """清理临时工作区中超过 ``max_age_days`` 天的文件，返回删除数量。

    启动时调用即可，不会影响正在进行的转换：正在写出的文件 mtime 都是新的。
    设置为 0 表示清理全部历史文件（测试与“立即释放空间”场景）。
    """
    root = root or temp_dir()
    if not os.path.isdir(root):
        return 0

    cutoff = time.time() - max(0, int(max_age_days)) * 86400
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(path) >= cutoff:
                    continue
                os.remove(path)
                removed += 1
            except OSError:
                continue
        for name in dirnames:
            path = os.path.join(dirpath, name)
            try:
                if not os.listdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue
    return removed
