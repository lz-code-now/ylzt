"""启动引导:加载配置文件并构建数据模型。

- 应用设置:config/settings.yaml
- 挂机方案:config/profiles/<name>.yaml

文件缺失、YAML 语法错误、结构错误统一抛出 ConfigValidationError,
错误消息包含文件路径与字段路径。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from models.profile import Profile
from models.settings import AppSettings
from utils.validation import ConfigValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
