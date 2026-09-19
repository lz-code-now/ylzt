"""运行时上下文。

对应 DESIGN.md 第 6 节:状态机运行数据必须集中保存在 RuntimeContext,
不要散落在各个模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.state import State


@dataclass
class RuntimeContext:
    """状态机运行时上下文。

    字段对应 DESIGN.md 6.1 节"必须记录"清单,
    另含 recovery_count(连续恢复次数,DESIGN 第 16 节)。
    """

    # 当前状态
    state: State = State.INIT

    # 地图与坐标
    map_name: str | None = None
    current_x: int | None = None
    current_y: int | None = None
    target_x: int | None = None
    target_y: int | None = None

    # 计数器
    local_revive_count: int = 0
    return_count: int = 0
    error_count: int = 0
    recovery_count: int = 0

    # 时间与最近事件
    started_at: datetime = field(default_factory=datetime.now)
    last_state_change_at: datetime = field(default_factory=datetime.now)
    last_successful_action: str | None = None
    last_death_at: datetime | None = None

    def transit_to(self, state: State) -> None:
        """切换到目标状态并记录状态变更时间。"""
        self.state = state
        self.last_state_change_at = datetime.now()
