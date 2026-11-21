# -*- coding: utf-8 -*-
"""本地打包脚本：python scripts/build.py

仅供开发者本地出包；CI 用同一入口。

两个 Windows 上踩过的坑，这里统一处理：
1. 控制台默认 cp1252/gbk，直接 print 中文会抛 UnicodeEncodeError → 先把 stdout 切到 UTF-8；
2. 脚本从 scripts/ 启动时 sys.path[0] 是 scripts/，`import lilipu` 会失败 → 手动把仓库根加进去。
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _force_utf8_console() -> None:
    """把标准输出切到 UTF-8，避免 Windows 老代码页把中文打印炸掉。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


def main() -> int:
    _force_utf8_console()
    os.chdir(ROOT)

    # 图标不存仓库，打包前现场生成
    try:
        from lilipu.icon import ensure_icon

        ensure_icon()
    except Exception as exc:
        print(f"[warn] 图标生成失败，继续打包: {exc!r}")

    # 字库可选：存在则一起打进包
    font_dir = os.path.join(ROOT, "assets", "fonts")
    if not os.path.isdir(font_dir) or not os.listdir(font_dir):
        print("[warn] assets/fonts empty, falling back to system fonts")

    cmd = [sys.executable, "-m", "PyInstaller", "scripts/lilipu.spec", "--noconfirm", "--clean"]
    print("$ " + " ".join(cmd))
    code = subprocess.call(cmd)
    if code == 0:
        dist = os.path.join(ROOT, "dist")
        exe = os.path.join(dist, "Lilipu.exe" if sys.platform == "win32" else "Lilipu")
        if os.path.exists(exe):
            size_mb = os.path.getsize(exe) / 1024 / 1024
            print(f"[ok] output: {exe} ({size_mb:.1f} MB)")
        else:
            print("[warn] expected output not found, check spec")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
