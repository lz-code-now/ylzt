"""WindowsGameAdapter:真实 GameAdapter 的组合逻辑层(W5)。

对应 DESIGN.md 21 节 W5:把 MockGameAdapter 替换为真实实现。
所有动作优先使用游戏自身 UI/快捷键(DESIGN W5),动作方式来自
``ActionBindings`` 配置(快捷键 / 点击坐标 / 小地图换算)。

架构说明:本文件只包含**平台无关的组合逻辑**
(窗口管理 + 截图 + 识别 + 输入的编排),依赖通过构造函数注入,
因此在 macOS 上也能用 Mock 依赖完整测试。
真正的 Windows 绑定(pywin32 / MSS / PyAutoGUI / keyboard)
见 game/windows_bindings.py。

容错策略:动作方法在游戏窗口丢失时不抛异常(no-op + 警告日志),
让状态机自身的 is_game_running / Watchdog 走 RECOVER → ERROR 恢复链路
(DESIGN 15/16),避免业务循环直接崩溃。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from game.adapter import GameAdapter
from game.image_match import TemplateMatcher, load_template
from game.input import InputController
from game.ocr import OcrEngine
from game.recognition import (
    CombatStateRecognizer,
    DeathRecognizer,
    MapRecognizer,
    PositionRecognizer,
)
from game.screen import ScreenCapture
from game.window import WindowManager
from models.recognition import RecognitionResult
from models.region import Region
from models.settings import ActionBindings, AppSettings
from utils.logger import get_logger

logger = get_logger("game")


class AdapterError(RuntimeError):
    """适配器操作失败(如游戏窗口未找到)。"""


def _require_region(
    regions: dict[str, Region], name: str
) -> Region | None:
    """取已配置的 ROI;未配置时记录警告并返回 None(识别退化为全窗口)。"""
    region = regions.get(name)
    if region is None:
        logger.warning("regions.%s 未配置,识别将使用整个窗口截图", name)
    return region


class WindowsGameAdapter(GameAdapter):
    """真实 GameAdapter:组合窗口/截图/识别/输入能力。

    Args:
        window_manager: 窗口查找与激活(Windows 绑定或 Mock)。
        capture: 截图(Windows 绑定或 Mock)。
        input_controller: 鼠标键盘输入(Windows 绑定或 Mock)。
        ocr: OCR 引擎(W6 接入真实引擎,当前可用 Mock)。
        matcher: 模板匹配器。
        settings: 应用设置(提供 window_title_contains / regions / actions)。
        templates_dir: 模板图片目录(game/templates)。
        debug_dir: 识别失败调试截图目录;None 表示不保存。
        sleep: 等待函数,默认 time.sleep;测试可注入。
    """

    def __init__(
        self,
        *,
        window_manager: WindowManager,
        capture: ScreenCapture,
        input_controller: InputController,
        ocr: OcrEngine,
        matcher: TemplateMatcher,
        settings: AppSettings,
        templates_dir: Path | str = Path("game/templates"),
        debug_dir: Path | str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.window_manager = window_manager
        self.capture = capture
        self.input = input_controller
        self.ocr = ocr
        self.matcher = matcher
        self.settings = settings
        self.bindings: ActionBindings = settings.game.actions
        self.templates_dir = Path(templates_dir)
        self.sleep = sleep

        game = settings.game
        self._window = None
        # 最近一次识别结果(按类别),供调试与 GUI 展示(W7)
        self.last_results: dict[str, RecognitionResult] = {}
        self._map_recognizer = MapRecognizer(
            ocr, region=_require_region(game.regions, "map_name"), debug_dir=debug_dir
        )
        self._position_recognizer = PositionRecognizer(
            ocr, region=_require_region(game.regions, "position"), debug_dir=debug_dir
        )
        self._death_recognizer = DeathRecognizer(
            matcher,
            template=self._load_template("death_dialog.png", "死亡对话框"),
            region=_require_region(game.regions, "death_dialog"),
            debug_dir=debug_dir,
        )
        self._combat_recognizer = CombatStateRecognizer(
            matcher,
            template=self._load_template("combat_on.png", "自动战斗开启"),
            region=_require_region(game.regions, "combat_button"),
            debug_dir=debug_dir,
        )

    # ------------------------------------------------------------------
    # 内部:窗口与截图
    # ------------------------------------------------------------------

    def _find_window(self):
        """按标题模糊查找游戏窗口;找不到返回 None。"""
        window = self.window_manager.find(self.settings.game.window_title_contains)
        self._window = window
        return window

    def _ensure_window(self):
        """确保游戏窗口存在并已缓存;失败抛 AdapterError。"""
        if self._window is not None and self.window_manager.is_alive(self._window):
            return self._window
        window = self._find_window()
        if window is None:
            raise AdapterError(
                f"未找到标题包含 {self.settings.game.window_title_contains!r} 的游戏窗口"
            )
        return window

    def _capture_window(self) -> object:
        """截取游戏窗口;窗口不存在抛 AdapterError。"""
        window = self._ensure_window()
        return self.capture.capture_window(window)

    def _recognize(self, recognizer, key: str) -> RecognitionResult:
        """带窗口丢失容错的识别:失败返回失败结果。"""
        try:
            image = self._capture_window()
        except AdapterError as exc:
            return RecognitionResult(success=False, detail=str(exc))
        result = recognizer.recognize(image)
        self.last_results[key] = result
        return result

    # ------------------------------------------------------------------
    # 内部:模板与动作
    # ------------------------------------------------------------------

    def _load_template(self, filename: str, label: str):
        """加载模板;文件不存在时记录警告并返回 None(对应识别将失败)。"""
        path = self.templates_dir / filename
        try:
            return load_template(path)
        except (FileNotFoundError, OSError) as exc:
            logger.warning("模板 %s(%s)未就绪: %s", filename, label, exc)
            return None

    def _press(self, key: str) -> None:
        """按下快捷键并等待游戏反应。"""
        self.input.press_key(key)
        self.sleep(self.bindings.post_action_delay_seconds)

    def _click_window(self, point: tuple[int, int]) -> None:
        """点击窗口内相对坐标(换算为屏幕绝对坐标)。"""
        window = self._ensure_window()
        screen_x = window.left + point[0]
        screen_y = window.top + point[1]
        self.input.click(screen_x, screen_y)
        self.sleep(self.bindings.post_action_delay_seconds)

    def _trigger(self, key: str | None, click: tuple[int, int] | None, label: str) -> None:
        """按优先级触发动作:快捷键 → 点击;都未配置抛 AdapterError。"""
        if key:
            self._press(key)
            return
        if click:
            self._click_window(click)
            return
        raise AdapterError(f"动作 {label!r} 未配置快捷键或点击坐标(game.actions)")

    # ------------------------------------------------------------------
    # GameAdapter 接口实现
    # ------------------------------------------------------------------

    def is_game_running(self) -> bool:
        return self._find_window() is not None

    def capture_screenshot(self):
        """截取游戏窗口(恢复现场用);窗口丢失返回 None。"""
        try:
            return self._capture_window()
        except AdapterError:
            return None

    def activate_game(self) -> None:
        try:
            window = self._ensure_window()
        except AdapterError as exc:
            logger.warning("激活游戏窗口失败: %s", exc)
            return
        self.window_manager.activate(window)

    def get_current_map(self) -> str | None:
        result = self._recognize(self._map_recognizer, "map")
        return result.value if result.success else None

    def get_position(self) -> tuple[int, int] | None:
        result = self._recognize(self._position_recognizer, "position")
        return result.value if result.success else None

    def is_dead(self) -> bool:
        result = self._recognize(self._death_recognizer, "death")
        return bool(result.value) if result.success else False

    def is_auto_combat_enabled(self) -> bool:
        result = self._recognize(self._combat_recognizer, "combat")
        return bool(result.value) if result.success else False

    def navigate_to(self, x: int, y: int) -> None:
        try:
            self._navigate_to(x, y)
        except AdapterError as exc:
            logger.warning("寻路触发失败: %s", exc)

    def _navigate_to(self, x: int, y: int) -> None:
        bindings = self.bindings
        # 优先:游戏内寻路快捷键
        if bindings.navigate_key:
            self._press(bindings.navigate_key)
            return
        # 其次:小地图/大地图点击寻路(需已标定换算比例)
        if bindings.minimap_scale > 0:
            point_x = int(bindings.minimap_origin[0] + x / bindings.minimap_scale)
            point_y = int(bindings.minimap_origin[1] + y / bindings.minimap_scale)
            if bindings.map_shortcut:
                self._press(bindings.map_shortcut)
            self._click_window((point_x, point_y))
            if bindings.map_shortcut:
                self._press(bindings.map_shortcut)
            return
        raise AdapterError("未配置寻路方式(game.actions.navigate_key 或 minimap_scale)")

    def start_auto_combat(self) -> None:
        try:
            self._trigger(
                self.bindings.auto_combat_key,
                self.bindings.auto_combat_click,
                "start_auto_combat",
            )
        except AdapterError as exc:
            logger.warning("开启自动战斗失败: %s", exc)

    def local_revive(self) -> None:
        try:
            self._trigger(None, self.bindings.local_revive_click, "local_revive")
        except AdapterError as exc:
            logger.warning("原地复活失败: %s", exc)

    def safe_revive(self) -> None:
        try:
            self._trigger(None, self.bindings.safe_revive_click, "safe_revive")
        except AdapterError as exc:
            logger.warning("安全复活失败: %s", exc)

    def return_home(self) -> None:
        try:
            self._trigger(
                self.bindings.return_home_key,
                self.bindings.return_home_click,
                "return_home",
            )
        except AdapterError as exc:
            logger.warning("回城失败: %s", exc)

    def stop_combat(self) -> None:
        """停止战斗:专用快捷键 → 再次按自动战斗键(切换) → 点击按钮。"""
        bindings = self.bindings
        try:
            if bindings.stop_combat_key:
                self._press(bindings.stop_combat_key)
            elif bindings.auto_combat_key:
                self._press(bindings.auto_combat_key)
            elif bindings.auto_combat_click:
                self._click_window(bindings.auto_combat_click)
            else:
                logger.warning("未配置停止战斗动作(game.actions),跳过")
        except AdapterError as exc:
            logger.warning("停止战斗失败: %s", exc)
