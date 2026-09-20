#!/usr/bin/env python3

"""W9 打包脚本:构建 Portable onedir 产物(DESIGN.md 第 21 节 W9)。

流程:
1. 环境检查(PyInstaller 可用、tests 全过、资源文件齐全)
2. 清理旧产物(build/ dist/)
3. pyinstaller ylzt.spec 构建 onedir
4. 复制外置资源到产物目录(config/、game/templates/、可选 tessdata)
5. 产物冒烟:运行打包后的可执行文件(命令行演示模式)
6. 输出产物结构与 Windows 真机部署说明

用法:
    .venv/bin/python scripts/build.py            # 完整流程
    .venv/bin/python scripts/build.py --no-tests # 跳过测试(调试用)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_DIST = DIST_DIR / "ylzt"
EXE_NAME = "ylzt.exe" if sys.platform == "win32" else "ylzt"

# 随产物分发的外置资源(用户可编辑/替换)
COPY_RESOURCES = [
    ("config/settings.yaml", "config/settings.yaml"),
    ("config/profiles", "config/profiles"),
    ("game/templates", "game/templates"),
]


def info(message: str) -> None:
    print(f"[build] {message}")


def fail(message: str) -> int:
    print(f"[build][错误] {message}", file=sys.stderr)
    return 1


def run(command: list[str], **kwargs) -> int:
    info("$ " + " ".join(str(part) for part in command))
    return subprocess.run(command, check=False, **kwargs).returncode


def check_environment() -> bool:
    """打包前置条件。"""
    if shutil.which("pyinstaller") is None and run(
        [sys.executable, "-c", "import PyInstaller"]
    ) != 0:
        fail("未安装 PyInstaller: pip install pyinstaller")
        return False
    for src, _ in COPY_RESOURCES:
        if not (PROJECT_ROOT / src).exists():
            fail(f"缺少资源: {src}")
            return False
    return True


def run_tests() -> int:
    """打包前跑全量测试,失败不打包。"""
    return run([sys.executable, "-m", "pytest", "-q"])


def clean() -> None:
    for directory in (BUILD_DIR, DIST_DIR):
        if directory.exists():
            info(f"清理 {directory}")
            shutil.rmtree(directory)


def build() -> int:
    return run(
        [sys.executable, "-m", "PyInstaller", "ylzt.spec", "--noconfirm"],
        cwd=PROJECT_ROOT,
    )


def copy_resources() -> None:
    """复制外置资源到产物目录(与可执行文件同级)。"""
    for src_rel, dest_rel in COPY_RESOURCES:
        src = PROJECT_ROOT / src_rel
        dest = APP_DIST / dest_rel
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            info(f"资源目录 {src_rel} -> {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            info(f"资源文件 {src_rel} -> {dest}")


def write_readme() -> None:
    """产物目录附部署说明(ASCII 文件名,避免 Windows 编码问题)。"""
    text = """御龙挂机助手 - Portable 使用说明

目录结构:
  ylzt(.exe)          主程序
  config/settings.yaml 应用设置(可用记事本编辑)
  config/profiles/     挂机方案
  game/templates/      模板图片(实测替换)

Windows 首次运行前置:
  1. 安装 Tesseract OCR(建议默认路径 C:/Program Files/Tesseract-OCR),
     并在 config/settings.yaml 的 game.ocr.tesseract_cmd 填入
     tesseract.exe 完整路径
  2. 安装中文语言包(chi_sim;安装器勾选或复制到 tessdata/)
  3. 在 config/settings.yaml 中把 game.ocr.engine 改为 tesseract
  4. 真实模式运行(需管理员权限注册全局热键):
         ylzt.exe --real
     演示模式(无需游戏):
         ylzt.exe

安全停止: F10 紧急停止 | F8 暂停 | F9 恢复 | Ctrl+C 同效
"""
    target = APP_DIST / "README.txt"
    target.write_text(text, encoding="utf-8-sig")
    info(f"已写入 {target.name}")


def smoke_test() -> int:
    """运行打包产物(命令行演示模式)验证可启动。"""
    exe = APP_DIST / EXE_NAME
    if not exe.exists():
        fail(f"产物缺失: {exe}")
        return 1
    info("产物冒烟: 运行 --help")
    code = run([str(exe), "--help"])
    if code != 0:
        fail("产物冒烟失败(--help 退出码非 0)")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="御龙挂机助手打包脚本")
    parser.add_argument("--no-tests", action="store_true", help="跳过打包前测试")
    parser.add_argument("--no-smoke", action="store_true", help="跳过产物冒烟")
    args = parser.parse_args()

    if not check_environment():
        return 1
    if not args.no_tests and run_tests() != 0:
        fail("测试未通过,取消打包")
        return 1

    clean()
    build_ok = build() == 0
    # 资源复制独立于 PyInstaller 结果:即使构建失败也保证产物结构完整,
    # 便于区分"构建失败"与"资源缺失"两类问题
    copy_resources()
    write_readme()
    if not build_ok:
        fail("PyInstaller 构建失败(详见上方日志)")
        return 1

    if not args.no_smoke and smoke_test() != 0:
        return 1

    info("打包完成")
    info(f"产物目录: {APP_DIST}")
    info("部署: 整个 dist/ylzt/ 目录复制到 Windows 机器即可(见 使用说明.txt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
