"""W3 窗口/截图/输入/热键接口与 Mock 测试。

对应 DESIGN.md 21 节 W3(查找窗口、截取窗口、测试按键/点击、紧急停止)
与第 17 节(安全停止)。真实 Windows 实现需要 Windows 环境,
本文件验证接口契约与 Mock 行为,以及紧急停止热键与状态机(W2)的联动。
"""

from __future__ import annotations

import pytest

from engine.state_machine import StateMachine
from game.input import MockHotkeyManager, MockInputController
from game.mock_adapter import MockGameAdapter
from game.screen import MockScreenCapture, ScreenImage, solid_image
from game.window import MockWindowManager, WindowInfo
from models.state import State

GAME_WINDOW = WindowInfo(
    handle=1001,
    title="御龙在天 - 正式版",
    left=0,
    top=0,
    width=1920,
    height=1080,
)


# ----------------------------------------------------------------------
# 窗口管理
# ----------------------------------------------------------------------


class TestWindowInfo:
    def test_rect(self):
        assert GAME_WINDOW.rect == (0, 0, 1920, 1080)


class TestWindowManager:
    def test_find_by_title_contains(self):
        manager = MockWindowManager([GAME_WINDOW])
        assert manager.find("御龙在天") is GAME_WINDOW

    def test_find_no_match_returns_none(self):
        manager = MockWindowManager([GAME_WINDOW])
        assert manager.find("不存在的窗口") is None

    def test_find_empty_manager_returns_none(self):
        assert MockWindowManager().find("御龙在天") is None

    def test_closed_window_not_found_and_not_alive(self):
        manager = MockWindowManager([GAME_WINDOW])
        manager.close(GAME_WINDOW.handle)
        assert manager.find("御龙在天") is None
        assert manager.is_alive(GAME_WINDOW) is False

    def test_is_alive_false_for_unknown_window(self):
        manager = MockWindowManager([GAME_WINDOW])
        unknown = WindowInfo(handle=9999, title="其他", left=0, top=0, width=10, height=10)
        assert manager.is_alive(GAME_WINDOW) is True
        assert manager.is_alive(unknown) is False

    def test_activate_is_recorded(self):
        manager = MockWindowManager([GAME_WINDOW])
        manager.activate(GAME_WINDOW)
        assert manager.called("activate") == 1
        assert manager.called("find") == 0


# ----------------------------------------------------------------------
# 截图与图像容器
# ----------------------------------------------------------------------


class TestScreenImage:
    def test_valid_image(self):
        image = ScreenImage(2, 2, "RGB", b"\x00" * 12)
        assert image.channels == 3
        assert len(image.data) == 12

    @pytest.mark.parametrize(
        ("width", "height"), [(0, 10), (10, 0), (-1, -1)]
    )
    def test_invalid_size_raises(self, width, height):
        with pytest.raises(ValueError):
            ScreenImage(width, height, "RGB", b"")

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ScreenImage(1, 1, "CMYK", b"\x00")

    def test_data_length_mismatch_raises(self):
        # 2x2 RGB 期望 12 字节,给 11 字节
        with pytest.raises(ValueError):
            ScreenImage(2, 2, "RGB", b"\x00" * 11)

    def test_solid_image(self):
        image = solid_image(3, 2, (255, 0, 0))
        assert (image.width, image.height) == (3, 2)
        assert image.mode == "RGB"
        assert image.data == b"\xff\x00\x00" * 6

    def test_solid_image_color_channel_mismatch_raises(self):
        with pytest.raises(ValueError):
            solid_image(1, 1, (255, 0, 0), mode="BGRA")

    def test_bgra_mode_supported(self):
        # MSS 原生输出格式,供 W5 使用
        image = solid_image(1, 1, (255, 0, 0, 255), mode="BGRA")
        assert image.channels == 4


class TestScreenCapture:
    def test_capture_window_defaults_to_window_size(self):
        capture = MockScreenCapture()
        image = capture.capture_window(GAME_WINDOW)
        assert (image.width, image.height) == (1920, 1080)

    def test_capture_window_preset_image(self):
        capture = MockScreenCapture()
        preset = solid_image(10, 10, (1, 2, 3))
        capture.set_window_image(GAME_WINDOW.handle, preset)
        assert capture.capture_window(GAME_WINDOW) is preset

    def test_capture_region_defaults_to_region_size(self):
        capture = MockScreenCapture()
        image = capture.capture_region(0, 0, 300, 150)
        assert (image.width, image.height) == (300, 150)

    def test_capture_region_preset_image(self):
        capture = MockScreenCapture()
        preset = solid_image(5, 5)
        capture.set_region_image(preset)
        assert capture.capture_region(0, 0, 1, 1) is preset

    def test_calls_are_recorded(self):
        capture = MockScreenCapture()
        capture.capture_window(GAME_WINDOW)
        capture.capture_region(0, 0, 10, 10)
        assert capture.called("capture_window") == 1
        assert capture.called("capture_region") == 1


# ----------------------------------------------------------------------
# 输入控制
# ----------------------------------------------------------------------


class TestInputController:
    def test_click_and_press_key_are_recorded(self):
        controller = MockInputController()
        controller.click(100, 200)
        controller.press_key("F1")
        assert controller.called("click") == 1
        assert controller.called("press_key") == 1
        assert controller.was_called_with("click", (100, 200))
        assert controller.was_called_with("press_key", ("F1",))


# ----------------------------------------------------------------------
# 全局热键与紧急停止
# ----------------------------------------------------------------------


class TestHotkeyManager:
    def test_register_and_press_triggers_callback(self):
        hotkeys = MockHotkeyManager()
        triggered: list[bool] = []
        hotkeys.register("F10", lambda: triggered.append(True))
        assert hotkeys.registered_keys == ["F10"]
        assert hotkeys.press("F10") is True
        assert triggered == [True]

    def test_press_unregistered_key_returns_false(self):
        hotkeys = MockHotkeyManager()
        assert hotkeys.press("F10") is False

    def test_unregister_all_clears_hotkeys(self):
        hotkeys = MockHotkeyManager()
        triggered: list[bool] = []
        hotkeys.register("F10", lambda: triggered.append(True))
        hotkeys.unregister_all()
        assert hotkeys.registered_keys == []
        assert hotkeys.press("F10") is False
        assert triggered == []


class TestEmergencyStopIntegration:
    def test_hotkey_stops_state_machine_safely(self, profile):
        """紧急停止链路:热键 F10 → request_stop → 停止战斗动作 → STOP(DESIGN 17)。"""
        adapter = MockGameAdapter()
        hotkeys = MockHotkeyManager()
        sm = StateMachine(adapter, profile)
        hotkeys.register("F10", sm.request_stop)

        # 跑到 COMBAT
        for _ in range(20):
            if sm.context.state is State.COMBAT:
                break
            sm.step()
        assert sm.context.state is State.COMBAT

        assert hotkeys.press("F10") is True
        assert sm.run(max_ticks=5) is State.STOP
        # 安全停止先停止游戏内战斗动作
        assert adapter.called("stop_combat") >= 1
        assert adapter.auto_combat_enabled is False
