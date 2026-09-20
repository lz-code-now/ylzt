"""御龙挂机助手程序入口(W6:真实挂机闭环)。

启动流程:初始化日志 → 加载配置 → 组装 RuntimeRunner → 运行闭环。

两种模式:
- 默认(mock):全 Mock 链路,任何平台可运行,演示完整
  "挂机 → 死亡 → 复活 → 回城 → 再挂机"业务闭环
- --real:真实链路(WindowsGameAdapter + Tesseract OCR),
  仅 Windows 真机可用;macOS 上组装时即报错

运行中按 F10 紧急停止(安全停止链路),Ctrl+C 同效。
"""

from __future__ import annotations

import argparse
import sys

from app.bootstrap import load_profile, load_settings
from app.constants import APP_NAME, APP_VERSION
from app.runner import RuntimeRunner, RunnerError
from game.mock_adapter import MockGameAdapter
from utils.logger import get_logger, setup_logging
from utils.validation import ConfigValidationError

logger = get_logger()


def main(argv: list[str] | None = None) -> int:
    """程序入口。

    Returns:
        进程退出码:0 正常结束,1 配置错误,2 组装失败。
    """
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动图形界面(tkinter);默认命令行演示模式",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用真实适配器(需 Windows);默认 mock 演示模式",
    )
    parser.add_argument("--profile", default="default", help="挂机方案名称")
    args = parser.parse_args(argv)

    setup_logging()
    logger.info("Script started")
    logger.info("%s v%s (W9: Portable)", APP_NAME, APP_VERSION)
    print(f"{APP_NAME} v{APP_VERSION}")

    try:
        settings = load_settings()
        profile = load_profile(args.profile)
    except ConfigValidationError as exc:
        logger.error("Configuration error: %s", exc)
        print(f"配置错误: {exc}", file=sys.stderr)
        return 1

    setup_logging(
        level=settings.logging.level,
        file_enabled=settings.logging.file_enabled,
    )

    if args.gui:
        return _run_gui(settings, args)

    print(
        f"挂机方案: {profile.name} | 地图: {profile.location.map} | "
        f"坐标: ({profile.location.x}, {profile.location.y}) | "
        f"模式: {'real' if args.real else 'mock'}"
    )

    try:
        runner = RuntimeRunner(
            settings=settings,
            profile=profile,
            mock=not args.real,
        )
        if not args.real:
            _stage_mock_scenario(runner, max_local_revive=profile.max_local_revive)
        # mock 演示:闭环跑完回城→再挂机后达到 tick 上限自然结束
        # real 模式:不限 tick,由 F10/Ctrl+C 紧急停止
        end_state = runner.run(max_ticks=None if args.real else 200)
    except RunnerError as exc:
        logger.error("Runner 组装失败: %s", exc)
        print(f"启动失败: {exc}", file=sys.stderr)
        return 2
    print(f"结束状态: {end_state}")
    return 0


def _run_gui(settings, args) -> int:
    """启动 GUI:扫描全部挂机方案供下拉选择。"""
    from app.bootstrap import PROFILES_DIR
    from app.gui import run_gui
    from models.profile import Profile

    profiles: dict[str, Profile] = {}
    if PROFILES_DIR.is_dir():
        for yaml_file in sorted(PROFILES_DIR.glob("*.yaml")):
            try:
                profiles[yaml_file.stem] = load_profile(yaml_file.stem)
            except ConfigValidationError as exc:
                logger.warning("跳过无效方案 %s: %s", yaml_file.name, exc)
    if not profiles:
        print("未找到任何有效挂机方案", file=sys.stderr)
        return 1
    initial = args.profile if args.profile in profiles else next(iter(profiles))
    run_gui(settings, profiles, initial)
    return 0


def _stage_mock_scenario(runner: RuntimeRunner, max_local_revive: int) -> None:
    """编排 mock 演示剧本:到达 → 开战 → 死亡 N 次 → 安全复活 → 回城 → 再挂机。

    mock 适配器默认不死亡、战斗恒开启;演示模式注入计划死亡,
    复活脚本按"前 N 次原地复活成功、最后 1 次走安全复活"编排,
    与 DESIGN 13.2 复活逻辑一致。
    """
    adapter = runner.adapter
    if adapter is None:
        adapter = runner.build().adapter
    assert isinstance(adapter, MockGameAdapter)
    # 第 1 次死亡发生在进入战斗后;之后每次复活回到战斗再死一次
    adapter.planned_deaths = max_local_revive + 1
    # 前 N 次原地复活成功;第 N+1 次死亡走 SAFE_REVIVE(脚本耗尽默认成功)
    adapter.revive_script = [True] * max_local_revive
    print(
        f"演示剧本: 计划死亡 {adapter.planned_deaths} 次"
        f"(原地复活 {max_local_revive} 次 → 安全复活 1 次 → 回城)"
    )


if __name__ == "__main__":
    _exit_code = 0
    try:
        _exit_code = main()
    except SystemExit as exc:
        _exit_code = exc.code if isinstance(exc.code, int) else 1
    except BaseException:
        # 崩溃保护:写 crash.log(可执行文件旁)并停住控制台
        import traceback
        from datetime import datetime

        try:
            from app.bootstrap import PROJECT_ROOT

            content = traceback.format_exc()
            (PROJECT_ROOT / "crash.log").write_text(
                f"[{datetime.now().isoformat()}] {content}", encoding="utf-8"
            )
            print(f"\n程序崩溃,详情已写入: {PROJECT_ROOT / 'crash.log'}", file=sys.stderr)
        except Exception:
            traceback.print_exc()
        _exit_code = 1

    # 双击运行且失败时停住控制台,避免"闪退"看不到错误(管道环境不停)
    if _exit_code not in (0, None):
        try:
            if sys.stdin is not None and sys.stdin.isatty():
                input("\n程序异常退出(见上方提示 / logs 目录),按回车键关闭...")
        except (EOFError, OSError):
            pass
    raise SystemExit(_exit_code or 0)
