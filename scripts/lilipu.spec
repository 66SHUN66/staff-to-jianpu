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

# 体积优化：这些库完全用不到，明确排除（含环境和用户机器上偶然装了的巨无霸）
excludes = [
    'pandas', 'matplotlib', 'scipy', 'sklearn', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'IPython', 'jupyter', 'notebook', 'pytest', 'setuptools', 'pip', 'tkinter.test',
    'test', 'unittest', 'pydoc_data', 'lib2to3',
    'torch', 'torchvision', 'torchaudio', 'tensorflow', 'jax', 'keras',
    'numba', 'llvmlite', 'pyarrow', 'dask', 'bokeh', 'tornado',
]

hiddenimports = [
    'PIL.ImageFont',
    'PIL.ImageTk',
    'music21.musicxml',
    'music21.stream',
    'music21.harmony',
]

a = Analysis(
    # 用绝对路径：从 .spec 构建时 PyInstaller 会以 spec 所在目录为基准解析相对路径，
    # 写 'main.py' 会变成 scripts/main.py 而报找不到脚本。
    [os.path.join(ROOT, 'main.py')],
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

# 单文件模式：双击即用，产物就是 dist/Lilipu.exe，方便直接丢 Release 附件
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='Lilipu',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=icon_path if os.path.exists(icon_path) else None,
)
