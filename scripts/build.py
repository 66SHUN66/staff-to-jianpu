# -*- coding: utf-8 -*-
"""本地打包脚本：python scripts/build.py [--onefile]

仅供开发者本地出包；CI 用同一入口。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    os.chdir(ROOT)

    # 图标不存仓库，打包前现场生成
    try:
        from lilipu.icon import ensure_icon
        ensure_icon()
    except Exception as exc:
        print(f"[warn] 图标生成失败，继续打包: {exc}")

    # 字库可选：存在则一起打进包
    font_dir = os.path.join(ROOT, "assets", "fonts")
    if not os.path.isdir(font_dir) or not os.listdir(font_dir):
        print("[warn] assets/fonts 为空，程序将回退到系统字体")

    cmd = [sys.executable, "-m", "PyInstaller", "scripts/lilipu.spec", "--noconfirm", "--clean"]
    print("$ " + " ".join(cmd))
    code = subprocess.call(cmd)
    if code == 0:
        dist = os.path.join(ROOT, "dist")
        exe = os.path.join(dist, "Lilipu.exe" if sys.platform == "win32" else "Lilipu")
        if os.path.exists(exe):
            size_mb = os.path.getsize(exe) / 1024 / 1024
            print(f"[ok] 产物: {exe} ({size_mb:.1f} MB)")
        else:
            print("[warn] 未找到预期产物，请检查 spec 配置")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
