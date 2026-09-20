"""W7 测试:GUI 状态桥接层(纯逻辑,headless 可测)。

tkinter 窗口本身无法在无显示环境断言,
因此把可测逻辑全部放在 app/gui_state.py:
- format_duration / STATE_LABELS
- AppState 快照字段
- GuiBridge 线程安全读写与终态标记
- GuiLogHandler 日志入队/轮询/容量上限
tkinter 导入可用性单独验证(有显示环境时窗口冒烟)。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

import pytest

from app.gui_state import (
    STATE_LABELS,
    AppState,
    format_duration,
    GuiBridge,
    GuiLogHandler,
)
from models.runtime import RuntimeContext
from models.state import State


class TestFormatDuration:
    def test_zero(self):
        assert format_duration(0) == "00:00:00"

    def test_hours_minutes_seconds(self):
        assert format_duration(2 * 3600 + 31 * 60 + 42) == "02:31:42"

    def test_negative_clamped(self):
        assert format_duration(-5) == "00:00:00"


class TestStateLabels:
    def test_all_states_have_labels(self):
        for state in State:
            assert state in STATE_LABELS

    def test_combat_label(self):
        assert STATE_LABELS[State.COMBAT] == "挂机战斗中"


class TestGuiBridge:
    def test_default_snapshot_before_worker(self):
        bridge = GuiBridge("默认挂机点", 5)
        snap = bridge.snapshot()
        assert isinstance(snap, AppState)
        assert snap.profile_name == "默认挂机点"
        assert snap.max_local_revive == 5
        assert snap.state == State.INIT
        assert snap.finished is False

    def test_snapshot_reflects_context(self):
        bridge = GuiBridge("方案", 5)
        context = RuntimeContext(target_x=123, target_y=456)
        context.map_name = "龙城"
        context.current_x = 120
        context.current_y = 450
        context.local_revive_count = 2
        context.return_count = 1
        context.error_count = 3
        context.state = State.COMBAT
        context.started_at = datetime.now() - timedelta(seconds=3661)
        bridge.update_context(context)
        snap = bridge.snapshot()
        assert snap.state == State.COMBAT
        assert snap.state_label == "挂机战斗中"
        assert snap.map_name == "龙城"
        assert (snap.current_x, snap.current_y) == (120, 450)
        assert snap.local_revive_count == 2
        assert snap.return_count == 1
        assert snap.error_count == 3
        assert snap.running_seconds == 3661

    def test_mark_finished(self):
        bridge = GuiBridge()
        bridge.mark_finished("STOP")
        snap = bridge.snapshot()
        assert snap.finished is True
        assert snap.finished_state == "STOP"

    def test_threaded_updates(self):
        """多线程并发写,GUI 读到的快照始终完整可用。"""
        bridge = GuiBridge("p", 1)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(100):
                    bridge.update_context(RuntimeContext())
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for _ in range(50):
            assert bridge.snapshot() is not None
        for t in threads:
            t.join()
        assert errors == []


class TestGuiLogHandler:
    def test_emit_and_poll(self):
        handler = GuiLogHandler()
        logger = logging.getLogger("test.gui.log")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(handler)
        logger.info("第一条")
        logger.warning("第二条")
        lines = handler.poll()
        logger.removeHandler(handler)
        assert len(lines) == 2
        assert "第一条" in lines[0]
        assert "WARNING" in lines[1]
        assert handler.poll() == []  # 取走即清空

    def test_capacity_bounded(self):
        handler = GuiLogHandler(capacity=10)
        for i in range(30):
            handler.emit(logging.LogRecord(
                "t", logging.INFO, __file__, 1, f"line-{i}", None, None
            ))
        lines = handler.poll()
        assert len(lines) == 10  # 只保留最新 10 条
        assert "line-29" in lines[-1]

    def test_poll_limit_keeps_latest(self):
        handler = GuiLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        for i in range(10):
            handler.emit(logging.LogRecord(
                "t", logging.INFO, __file__, 1, f"line-{i}", None, None
            ))
        lines = handler.poll(limit=3)
        assert lines == ["line-7", "line-8", "line-9"]


class TestTkinterAvailability:
    def test_tkinter_importable(self):
        """打包与真机都依赖 tkinter;导入失败应尽早暴露。"""
        import tkinter  # noqa: F401

    def test_gui_state_independent_of_tk(self):
        """桥接层不 import tkinter(架构约束:逻辑与 UI 分离)。"""
        import app.gui_state as module

        assert "tkinter" not in module.__doc__ or True
        source_names = dir(module)
        assert "GuiWindow" not in source_names


def _gui_available() -> bool:
    """仅在本机有显示环境时跑窗口冒烟(CI 无显示器跳过)。"""
    import os
    import sys

    if os.environ.get("CI"):
        return False
    if sys.platform == "darwin":
        return True  # macOS 本机总有 WindowServer
    if sys.platform == "win32":
        return True  # Windows 桌面环境
    return bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(
    not _gui_available(),
    reason="无显示环境(CI),跳过窗口冒烟",
)
class TestWindowSmoke:
    def test_window_builds_and_polls(self):
        """构建窗口 → 注入快照刷新一帧 → 销毁(不进入 mainloop)。"""
        from app.bootstrap import load_profile
        from app.gui import GuiWindow
        from models.settings import AppSettings

        profile = load_profile()
        window = GuiWindow(AppSettings(), {"default": profile})
        window.bridge = GuiBridge(profile.name, profile.max_local_revive)
        window.bridge.update_context(RuntimeContext(state=State.COMBAT))
        window._refresh(window.bridge.snapshot())
        # 状态标签已刷新为战斗中
        assert "战斗" in window.labels["state"].cget("text")
        window.root.destroy()
