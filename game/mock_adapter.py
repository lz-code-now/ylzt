"""MockGameAdapter:可脚本化的模拟游戏适配器。

对应 DESIGN.md 20.2 节,用于在不启动真实游戏的情况下跑通状态机。
通过预设属性模拟场景:

- 正常:默认配置即可
- 死亡:``planned_deaths = N``(战斗中计划死亡 N 次)
- 复活成功:``revive_script`` 缺省(默认成功)
- 复活失败:``revive_script = [False, ...]``
- 导航成功:``navigate_script`` 缺省(立即到达目标点)
- 导航超时:``navigate_script = [远处坐标, ...]``
- 游戏关闭:``game_running = False`` 或 ``game_running_script = [False, ...]``
- 自动战斗开启失败:``auto_combat_script = [False, ...]``

所有接口调用都会记录到 ``calls``,供测试断言。
"""

from __future__ import annotations

from game.adapter import GameAdapter


class MockGameAdapter(GameAdapter):
    """可脚本化的模拟 GameAdapter(DESIGN 20.2)。"""

    def __init__(
        self,
        *,
        map_name: str = "目标地图",
        position: tuple[int, int] = (0, 0),
        home_position: tuple[int, int] = (50, 50),
    ) -> None:
        # 虚拟游戏状态
        self.game_running = True
        self.map_name = map_name
        self.position = tuple(position)
        self.home_position = tuple(home_position)
        self.dead = False
        self.auto_combat_enabled = False

        # 脚本化响应(队列,消费完后回落到虚拟状态)
        self.game_running_script: list[bool] = []
        self.planned_deaths = 0
        self.revive_script: list[bool] = []
        self.navigate_script: list[tuple[int, int]] = []
        self.auto_combat_script: list[bool] = []

        # 调用历史: (方法名, 参数)
        self.calls: list[tuple[str, tuple]] = []

    # ------------------------------------------------------------------
    # 断言辅助
    # ------------------------------------------------------------------

    def called(self, name: str) -> int:
        """某接口方法被调用的次数。"""
        return sum(1 for call_name, _ in self.calls if call_name == name)

    def was_called_with(self, name: str, args: tuple) -> bool:
        """某接口方法是否以指定参数被调用过。"""
        return (name, args) in self.calls

    # ------------------------------------------------------------------
    # GameAdapter 接口实现
    # ------------------------------------------------------------------

    def is_game_running(self) -> bool:
        self.calls.append(("is_game_running", ()))
        if self.game_running_script:
            self.game_running = self.game_running_script.pop(0)
        return self.game_running

    def activate_game(self) -> None:
        self.calls.append(("activate_game", ()))

    def get_current_map(self) -> str | None:
        self.calls.append(("get_current_map", ()))
        return self.map_name if self.game_running else None

    def get_position(self) -> tuple[int, int] | None:
        self.calls.append(("get_position", ()))
        return self.position if self.game_running else None

    def is_dead(self) -> bool:
        self.calls.append(("is_dead", ()))
        # 计划死亡只在自动战斗进行中触发,避免复活确认时误触发
        if not self.dead and self.planned_deaths > 0 and self.auto_combat_enabled:
            self.planned_deaths -= 1
            self.dead = True
        return self.dead

    def is_auto_combat_enabled(self) -> bool:
        self.calls.append(("is_auto_combat_enabled", ()))
        return self.auto_combat_enabled

    def navigate_to(self, x: int, y: int) -> None:
        self.calls.append(("navigate_to", (x, y)))
        if self.navigate_script:
            self.position = tuple(self.navigate_script.pop(0))
        else:
            # 默认:立即到达目标点
            self.position = (x, y)

    def start_auto_combat(self) -> None:
        self.calls.append(("start_auto_combat", ()))
        if self.auto_combat_script:
            self.auto_combat_enabled = self.auto_combat_script.pop(0)
        else:
            self.auto_combat_enabled = True

    def local_revive(self) -> None:
        self.calls.append(("local_revive", ()))
        success = self.revive_script.pop(0) if self.revive_script else True
        if success:
            self.dead = False

    def safe_revive(self) -> None:
        self.calls.append(("safe_revive", ()))
        self.auto_combat_enabled = False
        success = self.revive_script.pop(0) if self.revive_script else True
        if success:
            self.dead = False
            self.position = self.home_position

    def return_home(self) -> None:
        self.calls.append(("return_home", ()))
        self.position = self.home_position

    def stop_combat(self) -> None:
        self.calls.append(("stop_combat", ()))
        self.auto_combat_enabled = False
