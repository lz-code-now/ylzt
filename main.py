"""御龙挂机助手程序入口。

当前阶段:W0 项目初始化。
仅完成日志初始化与版本信息输出,不包含任何游戏操作逻辑。
"""

from app.constants import APP_NAME, APP_VERSION
from utils.logger import get_logger, setup_logging

logger = get_logger()


def main() -> int:
    """程序入口:初始化日志并输出版本信息。

    Returns:
        进程退出码,0 表示正常退出。
    """
    setup_logging()
    logger.info("Script started")
    logger.info("%s v%s (W0: project initialization)", APP_NAME, APP_VERSION)
    print(f"{APP_NAME} v{APP_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
