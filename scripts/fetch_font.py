# -*- coding: utf-8 -*-
"""下载 Noto Sans SC 到 assets/fonts，供打包时随包携带中文字体。

单文件 ttf：https://github.com/googlefonts/noto-cjk 太重，
这里用 Google Fonts 的静态切片（体积小、授权干净）。
"""

from __future__ import annotations

import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST_DIR = os.path.join(ROOT, "assets", "fonts")

URLS = [
    "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
]
TARGET = "NotoSansSC-Regular.otf"


def download(url: str, dest: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lilipu-build"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
            shutil_copy(resp, fh)
        return os.path.getsize(dest) > 100 * 1024
    except Exception as exc:
        print(f"[warn] {url} -> {exc}")
        return False


def shutil_copy(src, dst) -> None:
    while True:
        chunk = src.read(1024 * 256)
        if not chunk:
            break
        dst.write(chunk)


def main() -> int:
    os.makedirs(DEST_DIR, exist_ok=True)
    dest = os.path.join(DEST_DIR, TARGET)
    if os.path.exists(dest) and os.path.getsize(dest) > 100 * 1024:
        print(f"[skip] 已存在: {dest}")
        return 0
    for url in URLS:
        print(f"[get] {url}")
        if download(url, dest):
            print(f"[ok] 已保存: {dest}")
            return 0
    print("[err] 所有镜像均下载失败；程序会自动回退到系统字体，不影响运行")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
