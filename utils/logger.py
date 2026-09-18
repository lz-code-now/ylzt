"""Logging 基础能力。

依据 DESIGN.md 第 19 节,日志格式:

    [2026-09-18 16:41:02] [INFO] Script started

日志输出到控制台与 logs/app.log;
ERROR 及以上级别额外写入 logs/error.log。
"""

from __future__ import annotations

import logging
from pathlib import Path

# 项目根目录下的 logs/
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
APP_LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 应用统一使用的 logger 命名空间
ROOT_LOGGER_NAME = "ylzt"


def setup_logging(
    level: int | str = logging.INFO, file_enabled: bool = True
) -> None:
    """初始化应用日志配置。

    可重复调用:每次调用会重置已有 handler,不会产生重复日志。

    Args:
        level: 日志级别(如 logging.INFO 或 "INFO"),默认 INFO。
        file_enabled: 是否写入日志文件,默认 True。
    """
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.setLevel(level)
    root.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if file_enabled:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        app_handler = logging.FileHandler(APP_LOG_FILE, encoding="utf-8")
        app_handler.setFormatter(formatter)
        root.addHandler(app_handler)

        error_handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root.addHandler(error_handler)


def get_logger(name: str | None = None) -> logging.Logger:
    """获取挂在应用命名空间下的 logger。

    Args:
        name: 子模块名;为 None 时返回应用根 logger。
    """
    if not name:
        return logging.getLogger(ROOT_LOGGER_NAME)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
