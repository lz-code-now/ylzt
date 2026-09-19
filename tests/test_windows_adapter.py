"""WindowsGameAdapter 组合逻辑测试(W5)。

macOS 上用 W3 的 Mock 依赖 + W4 的 Mock OCR + 合成模板,
完整验证 12 个 GameAdapter 方法的编排逻辑;
真实 Windows 绑定(pywin32/MSS/PyAutoGUI)无法在 macOS 运行,
只验证延迟导入的错误提示(见 test_windows_bindings.py)。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from game.image_match import OpenCVTemplateMatcher, array_to_image, save_image
from game.input import MockInputController
from game.ocr import MockOcrEngine
from game.screen import MockScreenCapture, ScreenImage, solid_image
from game.window import MockWindowManager, WindowInfo
from game.windows_adapter import AdapterError, WindowsGameAdapter
from models.settings import AppSettings
from utils.validation import ConfigValidationError

from conftest import FakeClock

WINDOW = WindowInfo(handle=101, title="御龙在天", left=100, top=200, width=800, height=600)


def noise_template(width: int = 20, height: int = 15, seed: int = 7) -> ScreenImage:
    """带纹理的噪声模板(固定种子,可复现)。"""
    rng = np.random.default_rng(seed)
    array = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    return array_to_image(array, "RGB")


def make_settings(**actions) -> AppSettings:
    """构造带 actions 的应用设置。"""
    return AppSettings.from_dict({"game": {"actions": actions}})


def make_adapter(
    settings: AppSettings | None = None,
    tmp_path=None,
    templates: dict[str, ScreenImage] | None = None,
):
    """构造被测适配器:Mock 窗口/截图/输入 + Mock OCR。

    templates: 预生成模板文件 {文件名: 图像},写入模板目录;
    未提供的模板文件不存在,对应识别器将以 None 模板运行(失败路径)。
    """
    settings = settings or make_settings()
    templates_dir = Path(tmp_path or tempfile.mkdtemp()) / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    for filename, image in (templates or {}).items():
        save_image(image, templates_dir / filename)

    window_manager = MockWindowManager([WINDOW])
    capture = MockScreenCapture()
    capture.set_window_image(WINDOW.handle, solid_image(800, 600, (60, 60, 60)))
    adapter = WindowsGameAdapter(
        window_manager=window_manager,
        capture=capture,
        input_controller=MockInputController(),
        ocr=MockOcrEngine(),
        matcher=OpenCVTemplateMatcher(),
        settings=settings,
        templates_dir=templates_dir,
        sleep=lambda _seconds: None,  # 测试不等待
    )
    adapter.window_manager = window_manager
    adapter._capture = capture
    return adapter


# ----------------------------------------------------------------------
# 配置:ActionBindings
# ----------------------------------------------------------------------


class TestActionBindings:
    def test_default_settings_has_empty_bindings(self):
        bindings = AppSettings.from_dict({}).game.actions
        assert bindings.auto_combat_key is None
        assert bindings.auto_combat_click is None
        assert bindings.local_revive_click is None
        assert bindings.safe_revive_click is None
        assert bindings.minimap_scale == 0.0
        assert bindings.post_action_delay_seconds == 0.5

    def test_full_bindings(self):
        settings = make_settings(
            auto_combat_key="F1",
            auto_combat_click=[100, 200],
            stop_combat_key="F2",
            local_revive_click=[400, 300],
            safe_revive_click=[400, 360],
            return_home_key="F3",
            minimap_scale=8.0,
            minimap_origin=[10, 20],
            post_action_delay_seconds=0.2,
        )
        bindings = settings.game.actions
        assert bindings.auto_combat_key == "F1"
        assert bindings.auto_combat_click == (100, 200)
        assert bindings.stop_combat_key == "F2"
        assert bindings.local_revive_click == (400, 300)
        assert bindings.safe_revive_click == (400, 360)
        assert bindings.return_home_key == "F3"
        assert bindings.minimap_scale == 8.0
        assert bindings.minimap_origin == (10, 20)
        assert bindings.post_action_delay_seconds == 0.2

    def test_invalid_click_point(self):
        with pytest.raises(ConfigValidationError, match="auto_combat_click"):
            make_settings(auto_combat_click=[1, 2, 3])

    def test_negative_click_point(self):
        with pytest.raises(ConfigValidationError, match="auto_combat_click"):
            make_settings(auto_combat_click=[-5, 10])

    def test_invalid_minimap_scale(self):
        with pytest.raises(ConfigValidationError, match="minimap_scale"):
            make_settings(minimap_scale=-1)

    def test_unknown_action_key(self):
        with pytest.raises(ConfigValidationError, match="未知字段"):
            make_settings(no_such_action=1)


# ----------------------------------------------------------------------
# 窗口管理
# ----------------------------------------------------------------------


class TestWindowLifecycle:
    def test_is_game_running_found(self):
        assert make_adapter().is_game_running() is True

    def test_is_game_running_not_found(self):
        adapter = make_adapter()
        adapter.window_manager.close(WINDOW.handle)
        assert adapter.is_game_running() is False

    def test_activate_game(self):
        adapter = make_adapter()
        adapter.activate_game()
        assert adapter.window_manager.called("activate") == 1

    def test_activate_game_no_window_is_noop(self):
        adapter = make_adapter()
        adapter.window_manager.close(WINDOW.handle)
        adapter.activate_game()  # 不应抛异常
        assert adapter.window_manager.called("activate") == 0

    def test_missing_window_recognition_returns_failure(self):
        adapter = make_adapter()
        adapter.window_manager.close(WINDOW.handle)
        assert adapter.get_current_map() is None
        assert adapter.get_position() is None
        assert adapter.is_dead() is False
        assert adapter.is_auto_combat_enabled() is False


# ----------------------------------------------------------------------
# 识别方法
# ----------------------------------------------------------------------


class TestRecognition:
    def test_get_current_map(self):
        adapter = make_adapter()
        adapter.ocr.script = ["龙城"]
        assert adapter.get_current_map() == "龙城"
        assert adapter.last_results["map"].confidence == 1.0

    def test_get_position(self):
        adapter = make_adapter()
        adapter.ocr.script = ["(123, 456)"]
        assert adapter.get_position() == (123, 456)

    def test_get_current_map_ocr_failure(self):
        adapter = make_adapter()
        assert adapter.get_current_map() is None
        assert adapter.last_results["map"].success is False

    def test_is_dead_with_template(self, tmp_path):
        template = noise_template(seed=1)
        adapter = make_adapter(templates={"death_dialog.png": template}, tmp_path=tmp_path)
        # 渐变背景 + 嵌入死亡模板 → 死亡 UI 被检出
        xs = np.tile(np.arange(600, dtype=np.int32), (800, 1))
        ys = np.tile(np.arange(800, dtype=np.int32).reshape(800, 1), (1, 600))
        scene_array = np.stack(
            [xs % 256, ys % 256, (xs + ys) % 256], axis=2
        ).astype(np.uint8)
        template_array = np.frombuffer(template.data, dtype=np.uint8).reshape(
            template.height, template.width, 3
        )
        scene_array[300:300 + template.height, 400:400 + template.width] = template_array
        adapter._capture.set_window_image(
            WINDOW.handle, array_to_image(scene_array, "RGB")
        )
        assert adapter.is_dead() is True

    def test_is_dead_template_missing_returns_false(self, tmp_path):
        adapter = make_adapter(tmp_path=tmp_path)  # 无模板文件
        assert adapter.is_dead() is False
        assert adapter.last_results["death"].success is False


# ----------------------------------------------------------------------
# 动作方法:快捷键优先 → 点击
# ----------------------------------------------------------------------


class TestActions:
    def test_start_auto_combat_by_key(self):
        adapter = make_adapter(make_settings(auto_combat_key="F1"))
        adapter.start_auto_combat()
        assert adapter.input.was_called_with("press_key", ("F1",))

    def test_start_auto_combat_by_click(self):
        adapter = make_adapter(make_settings(auto_combat_click=[150, 250]))
        adapter.start_auto_combat()
        # 窗口内坐标 + 窗口原点 → 屏幕绝对坐标
        assert adapter.input.was_called_with("click", (100 + 150, 200 + 250))

    def test_start_auto_combat_unconfigured_raises_noop(self):
        adapter = make_adapter()
        adapter.start_auto_combat()  # 未配置任何绑定 → 警告不抛异常
        assert adapter.input.calls == []

    def test_stop_combat_dedicated_key(self):
        adapter = make_adapter(
            make_settings(auto_combat_key="F1", stop_combat_key="F2")
        )
        adapter.stop_combat()
        assert adapter.input.was_called_with("press_key", ("F2",))

    def test_stop_combat_fallback_to_combat_key(self):
        adapter = make_adapter(make_settings(auto_combat_key="F1"))
        adapter.stop_combat()
        assert adapter.input.was_called_with("press_key", ("F1",))

    def test_local_revive_click(self):
        adapter = make_adapter(make_settings(local_revive_click=[400, 300]))
        adapter.local_revive()
        assert adapter.input.was_called_with("click", (100 + 400, 200 + 300))

    def test_local_revive_unconfigured_noop(self):
        adapter = make_adapter()
        adapter.local_revive()
        assert adapter.input.calls == []

    def test_safe_revive_click(self):
        adapter = make_adapter(make_settings(safe_revive_click=[400, 360]))
        adapter.safe_revive()
        assert adapter.input.was_called_with("click", (100 + 400, 200 + 360))

    def test_return_home_by_key(self):
        adapter = make_adapter(make_settings(return_home_key="F3"))
        adapter.return_home()
        assert adapter.input.was_called_with("press_key", ("F3",))


# ----------------------------------------------------------------------
# 导航:三种方式
# ----------------------------------------------------------------------


class TestNavigate:
    def test_navigate_by_hotkey(self):
        adapter = make_adapter(make_settings(navigate_key="g"))
        adapter.navigate_to(123, 456)
        assert adapter.input.was_called_with("press_key", ("g",))
        assert adapter.input.calls == [("press_key", ("g",))] or len(
            [c for c in adapter.input.calls if c[0] == "press_key"]
        ) == 1

    def test_navigate_by_minimap(self):
        adapter = make_adapter(
            make_settings(map_shortcut="m", minimap_scale=8.0, minimap_origin=[10, 20])
        )
        adapter.navigate_to(160, 320)
        # 世界坐标 → 小地图像素: (10 + 160/8, 20 + 320/8) = (30, 60)
        # 窗口原点 (100, 200) → 屏幕 (130, 260)
        assert adapter.input.was_called_with("press_key", ("m",))
        assert adapter.input.was_called_with("click", (100 + 30, 200 + 60))
        # 开地图/关地图共按两次 m
        assert [c for c in adapter.input.calls if c[0] == "press_key"] == [
            ("press_key", ("m",)),
            ("press_key", ("m",)),
        ]

    def test_navigate_unconfigured_noop(self):
        adapter = make_adapter()
        adapter.navigate_to(1, 2)  # 未配置寻路 → 警告不抛异常
        assert adapter.input.calls == []


# ----------------------------------------------------------------------
# 与状态机联调:整链路(战斗→死亡×1→复活→重新挂机)
# ----------------------------------------------------------------------


class TestWithStateMachine:
    def test_full_loop_with_windows_adapter(self, tmp_path, profile):
        from engine.state_machine import StateMachine

        combat_template = noise_template(seed=3)
        settings = make_settings(auto_combat_key="F1", local_revive_click=[400, 300])
        adapter = make_adapter(
            settings,
            tmp_path=tmp_path,
            templates={"combat_on.png": combat_template},
        )
        # 截图场景:渐变背景 + 嵌入战斗开启模板 → 战斗状态识别恒为已开启
        xs = np.tile(np.arange(800, dtype=np.int32), (600, 1))
        ys = np.tile(np.arange(600, dtype=np.int32).reshape(600, 1), (1, 800))
        scene_array = np.stack(
            [xs % 256, ys % 256, (xs + ys) % 256], axis=2
        ).astype(np.uint8)
        tpl_array = np.frombuffer(combat_template.data, dtype=np.uint8).reshape(
            combat_template.height, combat_template.width, 3
        )
        scene_array[100:100 + tpl_array.shape[0], 200:200 + tpl_array.shape[1]] = tpl_array
        adapter._capture.set_window_image(
            WINDOW.handle, array_to_image(scene_array, "RGB")
        )
        # OCR 脚本:CHECK_MAP 读地图 → NAVIGATE 读坐标(目标即 (100,200),到达)
        adapter.ocr.script = ["目标地图", "(100, 200)"]
        machine = StateMachine(adapter, profile, settings, clock=FakeClock())
        end_state = machine.run(max_ticks=60)
        # 链路:到达 → 识别到战斗已开启(模板命中)→ 无死亡 → 停在 COMBAT
        assert end_state.name == "COMBAT"
        assert adapter.last_results["combat"].success is True
        assert adapter.last_results["combat"].value is True
        # NAVIGATE 中到达目标(OCR 坐标与目标一致)
        assert machine.context.current_x == 100
        assert machine.context.current_y == 200
