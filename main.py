"""御龙挂机助手程序入口。

当前阶段:W1 配置系统。
启动流程:初始化日志 → 输出版本信息 → 加载设置与挂机方案。
不包含任何游戏操作逻辑。
"""

import sys

from app.bootstrap import load_profile, load_settings
from app.constants import APP_NAME, APP_VERSION
from utils.logger import get_logger, setup_logging
from utils.validation import ConfigValidationError

logger = get_logger()


def main() -> int:
    """程序入口:初始化日志,加载并展示配置。

    Returns:
        进程退出码,0 表示正常退出,1 表示配置错误。
    """
    setup_logging()
    logger.info("Script started")
    logger.info("%s v%s (W1: configuration system)", APP_NAME, APP_VERSION)
    print(f"{APP_NAME} v{APP_VERSION}")

    try:
        settings = load_settings()
        profile = load_profile()
    except ConfigValidationError as exc:
        logger.error("Configuration error: %s", exc)
        print(f"配置错误: {exc}", file=sys.stderr)
        return 1

    # 应用配置中的日志设置
    setup_logging(
        level=settings.logging.level,
        file_enabled=settings.logging.file_enabled,
    )

    logger.info(
        "Profile '%s': map=%s, x=%d, y=%d, tolerance=%d, max_local_revive=%d",
        profile.name,
        profile.location.map,
        profile.location.x,
        profile.location.y,
        profile.location.tolerance,
        profile.max_local_revive,
    )
    print(
        f"挂机方案: {profile.name} | 地图: {profile.location.map} | "
        f"坐标: ({profile.location.x}, {profile.location.y}) | "
        f"容差: {profile.location.tolerance} | "
        f"最大原地复活: {profile.max_local_revive}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
