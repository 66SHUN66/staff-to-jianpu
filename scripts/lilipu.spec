# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：python scripts/build.py

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
ASSETS = os.path.join(ROOT, 'assets')

# 只收集需要的资源，避免把示例图和字体全打进无关位置
datas = []
for sub in ('fonts', 'examples'):
    src = os.path.join(ASSETS, sub)
    if os.path.isdir(src):
        datas.append((src, os.path.join('assets', sub)))

icon_path = os.path.join(ASSETS, 'icon.ico')

# 体积优化：这些库完全用不到，明确排除
excludes = [
    'pandas', 'matplotlib', 'scipy', 'sklearn', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'IPython', 'jupyter', 'notebook', 'pytest', 'setuptools', 'pip', 'tkinter.test',
    'test', 'unittest', 'pydoc_data', 'lib2to3',
]

hiddenimports = [
    'PIL.ImageFont',
    'PIL.ImageTk',
    'music21.musicxml',
    'music21.stream',
    'music21.harmony',
]

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Lilipu',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Lilipu',
)
