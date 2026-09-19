"""状态机状态定义。

对应 DESIGN.md 第 5.1 节,共 13 个状态;
PAUSED 为 W8 异常恢复新增的运行控制状态(DESIGN 17 UI 暂停),
不属于业务状态转换表(5.2)。
"""

from __future__ import annotations

from enum import Enum


class State(Enum):
    """脚本引擎的全部状态。"""

    INIT = "INIT"
    CHECK_GAME = "CHECK_GAME"
    CHECK_MAP = "CHECK_MAP"
    NAVIGATE = "NAVIGATE"
    START_COMBAT = "START_COMBAT"
    COMBAT = "COMBAT"
    DEAD = "DEAD"
    LOCAL_REVIVE = "LOCAL_REVIVE"
    SAFE_REVIVE = "SAFE_REVIVE"
    RETURN_HOME = "RETURN_HOME"
    RECOVER = "RECOVER"
    PAUSED = "PAUSED"
    STOP = "STOP"
    ERROR = "ERROR"


# 终态:进入后状态机停止,不允许再驱动
TERMINAL_STATES = frozenset({State.STOP, State.ERROR})
