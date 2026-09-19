# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller 打包配置(DESIGN.md 第 21 节 W9)。

模式:onedir(DESIGN W9),产物为目录,含可执行文件与依赖。

资源策略:config/、game/templates/、tessdata **不打包进可执行文件**,
而是由 scripts/build.py 复制到 dist 产物目录旁边 —— 挂机助手
需要用户可编辑配置(config/*.yaml)、可实测替换模板(templates/*.png)、
可指定 OCR 语言包,外置资源比封包更合理。

构建命令:
    .venv/bin/pyinstaller ylzt.spec --noconfirm
或使用封装脚本:
    .venv/bin/python scripts/build.py
"""

from PyInstaller.utils.hooks import collect_data_files  # noqa: F401  (预留给 datas 扩展)
import sys

# Windows 绑定层使用延迟导入(pywin32/mss/pyautogui/keyboard),
# PyInstaller 静态分析可能漏收;用 collect 显式收集。
hiddenimports = [
    "pytesseract",
    "PIL",
    "PIL._tkinter_finder",
    "cv2",
    "yaml",
]
if sys.platform == "win32":
    hiddenimports += [
        "win32gui",
        "win32con",
        "mss",
        "pyautogui",
        "keyboard",
    ]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 无关大模块,减小体积
        "matplotlib",
        "numpy.tests",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ylzt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 保留控制台:命令行演示模式与日志输出需要
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ylzt",
)
