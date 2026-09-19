"""W8 测试:异常恢复。

- StuckDetector:采样间隔/位移判定/重置
- FailureTracker:计数/清零/阈值
- RecoveryJournal:事件五要素/截图保存/上限
- 状态机集成:暂停恢复、卡住→RECOVER、识别连续失败→自动安全停止、
  RECOVER 带截图与原因
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from engine.resilience import (
    FailureTracker,
    RecoveryJournal,
    StuckDetector,
)
from engine.state_machine import StateMachine
from game.adapter import GameAdapter
from game.screen import solid_image
from models.runtime import RuntimeContext
from models.state import State


# ----------------------------------------------------------------------
# StuckDetector
# ----------------------------------------------------------------------


class FakeClock:
    """可控单调时钟。"""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestStuckDetector:
    def test_first_sample_never_stuck(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        assert detector.check((100, 200)) is False

    def test_within_interval_not_checked(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        detector.check((100, 200))
        clock.advance(29)
        assert detector.check((100, 200)) is False  # 未到间隔

    def test_stuck_when_not_moving(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        detector.check((100, 200))
        clock.advance(30)
        assert detector.check((101, 201)) is True  # 位移 √2 < 5

    def test_not_stuck_when_moving(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        detector.check((100, 200))
        clock.advance(30)
        assert detector.check((150, 200)) is False  # 位移 50

    def test_none_position_ignored(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        assert detector.check(None) is False

    def test_reset(self):
        clock = FakeClock()
        detector = StuckDetector(30, 5, clock=clock)
        detector.check((100, 200))
        detector.reset()
        clock.advance(100)
        # 重置后重新采样,不判定
        assert detector.check((100, 200)) is False

    def test_invalid_interval(self):
        with pytest.raises(ValueError):
            StuckDetector(0, 5)


# ----------------------------------------------------------------------
# FailureTracker
# ----------------------------------------------------------------------


class TestFailureTracker:
    def test_count_and_threshold(self):
        tracker = FailureTracker(3)
        assert tracker.record_failure() == 1
        assert tracker.record_failure() == 2
        assert tracker.exceeded is False
        assert tracker.record_failure() == 3
        assert tracker.exceeded is True

    def test_success_resets(self):
        tracker = FailureTracker(3)
        tracker.record_failure()
        tracker.record_failure()
        tracker.record_success()
        assert tracker.count == 0
        assert tracker.exceeded is False

    def test_invalid_threshold(self):
        with pytest.raises(ValueError):
            FailureTracker(0)


# ----------------------------------------------------------------------
# RecoveryJournal
# ----------------------------------------------------------------------


class TestRecoveryJournal:
    def test_event_recorded_with_five_elements(self, tmp_path):
        journal = RecoveryJournal(tmp_path, max_screenshots=5)
        event = journal.record(
            state=State.RECOVER, reason="导航卡住", retry_index=1
        )
        assert event.state == State.RECOVER
        assert event.reason == "导航卡住"
        assert event.retry_index == 1
        assert event.screenshot_path is None  # 无截图入参
        assert event.at is not None
        assert len(journal.events) == 1

    def test_screenshot_saved(self, tmp_path):
        journal = RecoveryJournal(tmp_path, max_screenshots=5)
        image = solid_image(40, 30, (10, 20, 30))
        event = journal.record(State.RECOVER, "原因", 1, screenshot=image)
        assert event.screenshot_path is not None
        assert Path(event.screenshot_path).exists()

    def test_screenshot_limit(self, tmp_path):
        journal = RecoveryJournal(tmp_path, max_screenshots=2)
        image = solid_image(10, 10, (0, 0, 0))
        for i in range(4):
            journal.record(State.RECOVER, "r", i + 1, screenshot=image)
        # 只保存前 2 张
        saved = [e for e in journal.events if e.screenshot_path is not None]
        assert len(saved) == 2


# ----------------------------------------------------------------------
# 状态机集成:暂停/恢复 + 卡住 + 自动安全停止 + RECOVER 事件
# ----------------------------------------------------------------------


class ScriptedAdapter(GameAdapter):
    """脚本化适配器:可编程各接口返回值与调用记录(W8 专用)。"""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.game_running = True
        self.map_name: str | None = "龙城"
        self.position: tuple[int, int] | None = (100, 200)
        self.dead = False
        self.auto_combat = True
        self.screenshot = None

    def is_game_running(self) -> bool:
        self.calls.append("is_game_running")
        return self.game_running

    def activate_game(self) -> None:
        self.calls.append("activate_game")

    def get_current_map(self):
        self.calls.append("get_current_map")
        return self.map_name

    def get_position(self):
        self.calls.append("get_position")
        return self.position

    def is_dead(self) -> bool:
        self.calls.append("is_dead")
        return self.dead

    def is_auto_combat_enabled(self) -> bool:
        self.calls.append("is_auto_combat_enabled")
        return self.auto_combat

    def navigate_to(self, x: int, y: int) -> None:
        self.calls.append("navigate_to")

    def start_auto_combat(self) -> None:
        self.calls.append("start_auto_combat")

    def local_revive(self) -> None:
        self.calls.append("local_revive")

    def safe_revive(self) -> None:
        self.calls.append("safe_revive")

    def return_home(self) -> None:
        self.calls.append("return_home")

    def stop_combat(self) -> None:
        self.calls.append("stop_combat")

    def capture_screenshot(self):
        return self.screenshot


def make_machine(**kwargs) -> tuple[StateMachine, ScriptedAdapter]:
    from app.bootstrap import load_profile
    from models.settings import AppSettings

    settings = AppSettings.from_dict(
        {
            "runtime": {
                "stuck_check_interval_seconds": kwargs.pop("stuck_interval", 30),
                "stuck_min_distance": 5,
                "max_consecutive_failures": kwargs.pop("max_failures", 5),
                "debug_dir": str(kwargs.pop("debug_dir", "debug_w8")),
            }
        }
    )
    adapter = ScriptedAdapter()
    machine = StateMachine(
        adapter, load_profile(), settings, clock=(kwargs.pop("clock", None) or FakeClock())
    )
    return machine, adapter


class TestPauseResume:
    def test_pause_and_resume(self):
        machine, _ = make_machine()
        machine.run(max_ticks=1)  # INIT → CHECK_GAME
        machine.pause()
        machine.step()
        assert machine.context.state == State.PAUSED
        # 暂停中停留
        machine.step()
        machine.step()
        assert machine.context.state == State.PAUSED
        machine.resume()
        machine.step()
        assert machine.context.state == State.CHECK_GAME

    def test_stop_during_pause_wins(self):
        machine, _ = make_machine()
        machine.pause()
        machine.step()
        assert machine.context.state == State.PAUSED
        machine.request_stop()
        machine.step()
        assert machine.context.state == State.STOP


class TestStuckDetection:
    def test_stuck_navigate_triggers_recover_with_reason(self):
        clock = FakeClock()
        machine, adapter = make_machine(stuck_interval=30, clock=clock)
        # 快进到 NAVIGATE:INIT → CHECK_GAME → CHECK_MAP → NAVIGATE
        machine.run(max_ticks=3)
        assert machine.context.state == State.NAVIGATE
        adapter.position = (100, 200)  # 未到达目标(100,200 是目标本身)
        # 目标 (100,200) 容差 10 → 已到达,改目标外位置
        adapter.position = (200, 300)
        machine.step()
        # 第一次采样不判定
        assert machine.context.state == State.NAVIGATE
        clock.advance(30)
        machine.step()  # 位置不动 → 卡住 → RECOVER
        assert machine.context.state == State.RECOVER
        assert "导航卡住" in machine._recover_reason
        assert len(machine.recovery_journal.events) == 0  # 尚未执行恢复


class TestAutoSafeStop:
    def test_consecutive_identify_failures_trigger_stop(self):
        machine, adapter = make_machine(max_failures=3)
        machine.run(max_ticks=2)  # → CHECK_MAP
        adapter.map_name = None  # CHECK_MAP 识别失败
        for _ in range(12):
            if machine.context.state in (State.STOP, State.ERROR):
                break
            # CHECK_GAME 成功,但随后 CHECK_MAP 始终失败(模拟持续识别故障)
            if machine.context.state == State.RECOVER:
                machine.step()
                continue
            machine.step()
        # 连续失败 3 次(每次 CHECK_MAP)→ 第 3 次触发自动安全停止
        assert machine.context.state == State.STOP
        assert machine.failure_tracker.count >= 3

    def test_recovery_with_screenshot_and_event(self, tmp_path):
        machine, adapter = make_machine(max_failures=5, debug_dir=tmp_path)
        machine.run(max_ticks=2)
        adapter.map_name = None
        adapter.screenshot = solid_image(20, 20, (1, 2, 3))
        machine.step()  # 失败 → RECOVER
        machine.step()  # 执行恢复 → 记录事件 + 截图
        events = machine.recovery_journal.events
        assert len(events) == 1
        assert events[0].screenshot_path is not None
        assert Path(events[0].screenshot_path).exists()
        assert events[0].retry_index == 1


class TestCaptureScreenshot:
    def test_default_adapter_returns_none(self):
        class Minimal(GameAdapter):
            def is_game_running(self): return True
            def activate_game(self): pass
            def get_current_map(self): return None
            def get_position(self): return None
            def is_dead(self): return False
            def is_auto_combat_enabled(self): return False
            def navigate_to(self, x, y): pass
            def start_auto_combat(self): pass
            def local_revive(self): pass
            def safe_revive(self): pass
            def return_home(self): pass
            def stop_combat(self): pass

        assert Minimal().capture_screenshot() is None

    def test_scripted_adapter_screenshot(self):
        adapter = ScriptedAdapter()
        adapter.screenshot = solid_image(5, 5, (0, 0, 0))
        assert adapter.capture_screenshot() is adapter.screenshot


class TestRuntimeSettings:
    def test_new_runtime_defaults(self):
        from models.settings import AppSettings

        runtime = AppSettings.from_dict({}).runtime
        assert runtime.stuck_check_interval_seconds == 30
        assert runtime.stuck_min_distance == 5
        assert runtime.max_consecutive_failures == 5
        assert runtime.max_recovery_screenshot == 20
        assert runtime.debug_dir == "debug"

    def test_invalid_stuck_interval(self):
        from models.settings import AppSettings
        from utils.validation import ConfigValidationError

        with pytest.raises(ConfigValidationError, match="stuck_check_interval_seconds"):
            AppSettings.from_dict({"runtime": {"stuck_check_interval_seconds": 0}})
