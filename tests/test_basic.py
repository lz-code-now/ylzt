"""W0 基础测试:版本常量、日志初始化、程序入口。"""

import logging

from app.constants import APP_NAME, APP_VERSION
from utils.logger import ROOT_LOGGER_NAME, setup_logging


def test_app_constants() -> None:
    """版本与应用名常量已定义。"""
    assert APP_NAME == "御龙挂机助手"
    assert APP_VERSION == "0.1.0"


def test_main_outputs_version(capsys) -> None:
    """main() mock 模式正常退出并输出版本信息(W6 闭环入口)。"""
    from main import main

    # mock 演示闭环(tick 上限内跑完:到达→战斗→死亡×6→复活→回城→再挂机)
    assert main(["--profile", "default"]) == 0
    output = capsys.readouterr().out
    assert APP_NAME in output
    assert APP_VERSION in output
    assert "结束状态" in output


def test_setup_logging_configures_root_logger() -> None:
    """setup_logging 后应用 logger 可用且级别正确。"""
    setup_logging(level=logging.DEBUG)
    root = logging.getLogger(ROOT_LOGGER_NAME)
    assert root.level == logging.DEBUG
    assert root.handlers  # 控制台 + 文件 handler 已挂载


def test_setup_logging_is_idempotent() -> None:
    """重复调用 setup_logging 不会累积 handler。"""
    setup_logging()
    count = len(logging.getLogger(ROOT_LOGGER_NAME).handlers)
    setup_logging()
    assert len(logging.getLogger(ROOT_LOGGER_NAME).handlers) == count
