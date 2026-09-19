"""GameAdapter 抽象接口。

对应 DESIGN.md 第 8 节:业务逻辑(状态机/Behavior)只能依赖这个接口,
不得直接接触真实游戏。真实 Windows 实现计划在 W5 提供,
W2 阶段使用 game/mock_adapter.py 的 MockGameAdapter 驱动状态机。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class GameAdapter(ABC):
    """游戏适配器接口(DESIGN 第 8 节的 12 个方法)。"""

    @abstractmethod
    def is_game_running(self) -> bool:
        """游戏窗口是否存在且可交互。"""

    @abstractmethod
    def activate_game(self) -> None:
        """把游戏窗口带到前台。"""

    @abstractmethod
    def get_current_map(self) -> str | None:
        """读取当前地图名;无法确认时返回 None。"""

    @abstractmethod
    def get_position(self) -> tuple[int, int] | None:
        """读取当前角色坐标;无法确认时返回 None。"""

    @abstractmethod
    def is_dead(self) -> bool:
        """判断角色是否处于死亡状态。"""

    @abstractmethod
    def is_auto_combat_enabled(self) -> bool:
        """判断游戏内自动战斗是否已开启。"""

    @abstractmethod
    def navigate_to(self, x: int, y: int) -> None:
        """使用游戏允许的寻路能力前往目标坐标。"""

    @abstractmethod
    def start_auto_combat(self) -> None:
        """触发游戏内自动战斗。"""

    @abstractmethod
    def local_revive(self) -> None:
        """原地复活。"""

    @abstractmethod
    def safe_revive(self) -> None:
        """安全复活(回城复活)。"""

    @abstractmethod
    def return_home(self) -> None:
        """执行回城动作。"""

    def capture_screenshot(self):
        """截取当前游戏画面(DESIGN 16 恢复现场截图)。

        返回 ScreenImage;适配器不支持截图时返回 None。
        默认实现返回 None,真实适配器与 Mock 按需覆盖。
        """
        return None

    @abstractmethod
    def stop_combat(self) -> None:
        """停止战斗相关动作(安全停止时调用)。"""
