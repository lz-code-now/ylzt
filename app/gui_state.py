"""GUI 状态桥接层(W7)——纯逻辑,无 UI 依赖,headless 可测。

架构(DESIGN 18"GUI 不允许阻塞状态机"):

    tkinter 主线程(GuiWindow,轮询)
        ↓ AppState 快照
    GuiBridge(线程安全读写)
        ↓ 更新快照
    Worker 线程(RuntimeRunner → StateMachine)

- ``AppState``:一份不可变的状态快照(状态/坐标/计数/运行时间),
  GUI 每帧只读它,不直接触碰 StateMachine。
- ``GuiBridge``:worker 线程调用 ``update_context()`` 写入,
  GUI 线程调用 ``snapshot()`` 读取;内部用锁保护。
- ``GuiLogHandler``:logging handler,把日志行推入有界队列,
  GUI 轮询取走显示(替代 Qt Signal)。
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from models.runtime import RuntimeContext
from models.state import State

# 状态的中文显示名(DESIGN 18 状态栏)
STATE_LABELS: dict[State, str] = {
    State.INIT: "初始化",
    State.CHECK_GAME: "检查游戏",
    State.CHECK_MAP: "检查地图",
    State.NAVIGATE: "寻路中",
    State.START_COMBAT: "开启战斗",
    State.COMBAT: "挂机战斗中",
    State.DEAD: "死亡",
    State.LOCAL_REVIVE: "原地复活",
    State.SAFE_REVIVE: "安全复活",
    State.RETURN_HOME: "回城",
    State.RECOVER: "恢复中",
    State.PAUSED: "已暂停",
    State.STOP: "已停止",
    State.ERROR: "出错",
}


def format_duration(seconds: int) -> str:
    """运行时长格式化:HH:MM:SS(DESIGN 18 示例 02:31:42)。"""
    seconds = max(0, seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True)
class AppState:
    """GUI 状态快照(不可变,DESIGN 18 主窗口字段)。"""

    state: State = State.INIT
    state_label: str = "初始化"
    profile_name: str = ""
    map_name: str | None = None
    target_x: int | None = None
    target_y: int | None = None
    current_x: int | None = None
    current_y: int | None = None
    max_local_revive: int = 0
    local_revive_count: int = 0
    return_count: int = 0
    error_count: int = 0
    running_seconds: int = 0
    finished: bool = False
    finished_state: str = ""
    started_at: datetime = field(default_factory=datetime.now)


class GuiBridge:
    """worker 线程 → GUI 线程 的状态桥(锁保护)。"""

    def __init__(self, profile_name: str = "", max_local_revive: int = 0) -> None:
        self._lock = threading.Lock()
        self._profile_name = profile_name
        self._max_local_revive = max_local_revive
        self._context: RuntimeContext | None = None
        self._finished = False
        self._finished_state = ""

    # -- worker 线程调用 --

    def update_context(self, context: RuntimeContext) -> None:
        """worker 每个状态更新后写入最新上下文。"""
        with self._lock:
            self._context = context

    def mark_finished(self, state_name: str) -> None:
        """worker 结束时记录终态。"""
        with self._lock:
            self._finished = True
            self._finished_state = state_name

    # -- GUI 线程调用 --

    def snapshot(self, now: datetime | None = None) -> AppState:
        """生成当前快照;无数据时返回默认快照。"""
        now = now or datetime.now()
        with self._lock:
            context = self._context
            finished = self._finished
            finished_state = self._finished_state
        if context is None:
            return AppState(
                profile_name=self._profile_name,
                max_local_revive=self._max_local_revive,
                finished=finished,
                finished_state=finished_state,
            )
        return AppState(
            state=context.state,
            state_label=STATE_LABELS.get(context.state, context.state.name),
            profile_name=self._profile_name,
            map_name=context.map_name,
            target_x=context.target_x,
            target_y=context.target_y,
            current_x=context.current_x,
            current_y=context.current_y,
            max_local_revive=self._max_local_revive,
            local_revive_count=context.local_revive_count,
            return_count=context.return_count,
            error_count=context.error_count,
            running_seconds=int((now - context.started_at).total_seconds()),
            finished=finished,
            finished_state=finished_state,
            started_at=context.started_at,
        )


class GuiLogHandler(logging.Handler):
    """日志桥:把日志行推入有界队列,GUI 轮询显示(DESIGN 18 运行日志)。"""

    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        self._lock = threading.Lock()
        self._lines: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        with self._lock:
            self._lines.append(line)

    def poll(self, limit: int = 50) -> list[str]:
        """取走队列中的行(至多 limit 条,最新的优先保留)。"""
        with self._lock:
            lines = list(self._lines)
            self._lines.clear()
        if len(lines) > limit:
            lines = lines[-limit:]
        return lines
