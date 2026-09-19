"""状态超时看门狗。

对应 DESIGN.md 第 15 节:每个状态设置超时,超过后由状态机转入 RECOVER。
超时值为 0(如 COMBAT)表示没有固定超时,但仍需状态机做健康检查。
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from models.state import State


class Watchdog:
    """按状态超时表检查当前状态是否超时。"""

    #: DESIGN.md 第 15 节的默认超时表(秒);<= 0 表示不检查固定超时。
    DEFAULT_TIMEOUTS: Mapping[State, int] = {
        State.CHECK_GAME: 10,
        State.CHECK_MAP: 10,
        State.NAVIGATE: 180,
        State.START_COMBAT: 10,
        State.COMBAT: 0,
        State.LOCAL_REVIVE: 20,
        State.SAFE_REVIVE: 20,
        State.RETURN_HOME: 60,
        State.RECOVER: 0,
    }

    def __init__(
        self,
        timeouts: Mapping[State, int] | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Args:
            timeouts: 覆盖默认超时表的映射(如 NAVIGATE 用挂机方案的寻路超时)。
            clock: 单调时钟函数,默认 time.monotonic;测试可注入假时钟。
        """
        self._timeouts: dict[State, int] = dict(self.DEFAULT_TIMEOUTS)
        if timeouts:
            self._timeouts.update(timeouts)
        self._clock = clock
        self._entered_at: float | None = None

    def on_state_entered(self, state: State) -> None:
        """记录状态进入时间(每次状态切换后调用)。"""
        self._entered_at = self._clock()

    def check(self, state: State) -> bool:
        """检查状态是否超时;超时返回 True。

        超时值 <= 0 的状态(如 COMBAT、RECOVER)不做固定超时检查。
        """
        timeout = self._timeouts.get(state, 0)
        if timeout <= 0 or self._entered_at is None:
            return False
        return (self._clock() - self._entered_at) >= timeout
