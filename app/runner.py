"""RuntimeRunner:挂机闭环组装与运行(W6)。

对应 DESIGN.md 21 节 W6"真实挂机闭环"(第一个 MVP):
把 W1 配置、W2 状态机、W4 识别、W5 适配器、W3 热键
组装成"启动 → 挂机 → 死亡 → 复活 → 回城 → 再挂机"的完整闭环。

两种运行模式(由 OCR 引擎与依赖注入决定):
- mock:全 Mock 链路,任何平台可运行(开发/演示/测试)
- real:真实适配器(WindowsGameAdapter)+ Tesseract OCR,
  Windows 真机运行;macOS 上仅组装校验

安全停止(DESIGN 17 三层):
- F10 紧急停止热键 → request_stop → 状态机 _safe_stop → STOP
- 循环收到终态自动结束
- Ctrl+C 同步触发 request_stop
"""

from __future__ import annotations

import signal
from collections.abc import Callable
from pathlib import Path

from app.bootstrap import load_profile
from engine.state_machine import StateMachine
from game.adapter import GameAdapter
from game.image_match import OpenCVTemplateMatcher
from game.input import HotkeyManager, InputController, MockHotkeyManager, MockInputController
from game.mock_adapter import MockGameAdapter
from game.ocr import MockOcrEngine, OcrEngine
from game.ocr_tesseract import TesseractOcrEngine
from game.screen import MockScreenCapture, ScreenCapture
from game.window import MockWindowManager, WindowManager
from models.profile import Profile
from models.settings import AppSettings
from utils.logger import get_logger

logger = get_logger("runner")

DEFAULT_TICK_SECONDS = 0.5


class RunnerError(RuntimeError):
    """Runner 组装或运行失败。"""


class RuntimeRunner:
    """挂机闭环运行器。

    Args:
        settings: 应用设置。
        profile: 挂机方案。
        mock: True 用全 Mock 链路;False 组装真实链路(需 Windows)。
        hotkeys: 热键管理器;mock 模式默认 MockHotkeyManager,
            real 模式默认由 windows_bindings 提供。
        templates_dir: 模板目录。
        debug_dir: 识别调试截图目录(None=不保存)。
        sleep: 等待函数(测试可注入)。
        runner_settings: 附加开关,见 RunnerSettings。
    """

    def __init__(
        self,
        *,
        settings: AppSettings,
        profile: Profile,
        mock: bool = False,
        hotkeys: HotkeyManager | None = None,
        templates_dir: Path | str | None = None,
        debug_dir: Path | str | None = None,
        sleep: Callable[[float], None] | None = None,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self.settings = settings
        self.profile = profile
        self.mock = mock
        self.tick_seconds = tick_seconds
        import time

        self.sleep = sleep or time.sleep
        self.templates_dir = Path(templates_dir or Path("game/templates"))
        self.debug_dir = debug_dir
        self.machine: StateMachine | None = None
        self.adapter: GameAdapter | None = None
        # 热键:显式传入 > 按模式选择
        if hotkeys is not None:
            self.hotkeys = hotkeys
        elif mock:
            self.hotkeys = MockHotkeyManager()
        else:
            try:
                from game.windows_bindings import KeyboardHotkeyManager
            except RuntimeError as exc:
                raise RunnerError(str(exc)) from exc
            self.hotkeys = KeyboardHotkeyManager()

    # ------------------------------------------------------------------
    # 组装
    # ------------------------------------------------------------------

    def _build_ocr(self) -> OcrEngine:
        ocr_config = self.settings.game.ocr
        if self.mock or ocr_config.engine == "mock":
            return MockOcrEngine()
        if ocr_config.engine == "tesseract":
            return TesseractOcrEngine(ocr_config)
        raise RunnerError(f"未知 OCR 引擎: {ocr_config.engine!r}")

    def _build_adapter(self) -> GameAdapter:
        if self.mock:
            return MockGameAdapter()
        try:
            from game.windows_bindings import (
                MssScreenCapture,
                PyAutoGuiInput,
                Win32WindowManager,
            )
        except RuntimeError as exc:
            raise RunnerError(str(exc)) from exc
        from game.windows_adapter import WindowsGameAdapter

        try:
            return WindowsGameAdapter(
                window_manager=Win32WindowManager(),
                capture=MssScreenCapture(),
                input_controller=PyAutoGuiInput(),
                ocr=self._build_ocr(),
                matcher=OpenCVTemplateMatcher(),
                settings=self.settings,
                templates_dir=self.templates_dir,
                debug_dir=self.debug_dir,
            )
        except RuntimeError as exc:
            # 绑定类为延迟导入,实例化时才可能报缺库
            raise RunnerError(str(exc)) from exc

    def build(self) -> StateMachine:
        """组装状态机并注册热键;返回可运行的 StateMachine。"""
        self.adapter = self._build_adapter()
        self.machine = StateMachine(
            self.adapter, self.profile, self.settings
        )
        self._register_hotkeys()
        return self.machine

    def _register_hotkeys(self) -> None:
        """注册紧急停止与暂停/恢复热键(DESIGN 17 与 7.1)。"""
        assert self.machine is not None
        app = self.settings.app
        self.hotkeys.register(app.emergency_stop_key, self.machine.request_stop)
        self.hotkeys.register(app.pause_key, self.machine.pause)
        self.hotkeys.register(app.resume_key, self.machine.resume)
        logger.info(
            "热键已注册: %s 紧急停止 | %s 暂停 | %s 恢复",
            app.emergency_stop_key,
            app.pause_key,
            app.resume_key,
        )

    # ------------------------------------------------------------------
    # 运行
    # ------------------------------------------------------------------

    def run(self, max_ticks: int | None = None) -> str:
        """运行闭环直到终态或达到 tick 上限;返回结束状态名。

        Args:
            max_ticks: 透传给 StateMachine.run 的防死循环上限;
                None 表示不限(由紧急热键/Ctrl+C 停止)。
        """
        if self.machine is None:
            self.build()
        assert self.machine is not None
        self._install_signal_handlers()
        logger.info("挂机闭环启动: 方案=%s mock=%s", self.profile.name, self.mock)
        try:
            end_state = self.machine.run(max_ticks=max_ticks)
        except KeyboardInterrupt:
            logger.warning("收到 Ctrl+C,触发安全停止")
            self.machine.request_stop()
            end_state = self.machine.run(max_ticks=10)
        finally:
            self.hotkeys.unregister_all()
        logger.info("挂机闭环结束: %s", end_state.name)
        return end_state.name

    def _install_signal_handlers(self) -> None:
        """Ctrl+C 转为安全停止(仅主线程有效,失败忽略)。"""
        try:
            signal.signal(signal.SIGINT, self._on_sigint)
        except ValueError:
            # 非主线程(如测试)无法设置信号处理器
            pass

    def _on_sigint(self, _signum, _frame) -> None:
        assert self.machine is not None
        self.machine.request_stop()


def create_mock_runner(settings: AppSettings, profile_name: str = "default") -> RuntimeRunner:
    """便捷工厂:全 Mock 闭环(macOS 可运行,用于演示与联调)。"""
    profile = load_profile(profile_name)
    return RuntimeRunner(settings=settings, profile=profile, mock=True)
