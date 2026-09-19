"""启动引导:加载配置文件并构建数据模型。

- 应用设置:config/settings.yaml
- 挂机方案:config/profiles/<name>.yaml

文件缺失、YAML 语法错误、结构错误统一抛出 ConfigValidationError,
错误消息包含文件路径与字段路径。
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from models.profile import Profile
from models.settings import AppSettings
from utils.validation import ConfigValidationError


def _project_root() -> Path:
    """定位项目根目录(资源查找基准)。

    - 源码运行:app/bootstrap.py 的上两级
    - PyInstaller onedir:可执行文件所在目录(资源与 exe 同级分发,
      便于用户直接编辑 config/ 与替换 templates/);
      PyInstaller 6 的 sys._MEIPASS 指向 _internal/,不适合外置资源
    - PyInstaller onefile:sys._MEIPASS(解包临时目录)
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "config").is_dir():
            return exe_dir
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return exe_dir
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _project_root()
CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
PROFILES_DIR = CONFIG_DIR / "profiles"


def read_yaml(path: Path) -> dict:
    """读取 YAML 文件并返回字典;文件/语法错误统一转为 ConfigValidationError。"""
    if not path.is_file():
        raise ConfigValidationError(f"配置文件不存在: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"YAML 语法错误: {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigValidationError(f"配置文件顶层必须是映射结构: {path}")
    return data


def load_settings(path: Path | None = None) -> AppSettings:
    """加载应用设置。"""
    return AppSettings.from_dict(read_yaml(path or SETTINGS_FILE))


def load_profile(name: str = "default", path: Path | None = None) -> Profile:
    """按名称加载挂机方案;也可直接指定文件路径。"""
    if path is None:
        path = PROFILES_DIR / f"{name}.yaml"
    return Profile.from_dict(read_yaml(path))
