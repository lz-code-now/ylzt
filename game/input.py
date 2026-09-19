"""输入控制与全局热键接口(W3 基础能力)。

对应 DESIGN.md 21 节 W3:执行测试按键/点击、紧急停止(第 17 节)。
本文件只定义接口与测试用 Mock;真实实现
(PyAutoGUI / keyboard)在 W5 阶段提供,需要 Windows 环境。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class InputController(ABC):
    """鼠标与键盘输入接口。"""

    @abstractmethod
    def click(self, x: int, y: int) -> None:
        """在屏幕绝对坐标 (x, y) 单击。"""

    @abstractmethod
    def press_key(self, key: str) -> None:
        """按下并释放按键(如 'F1'、'tab')。"""


class MockInputController(InputController):
    """测试用 Mock:记录全部输入,可断言坐标与按键。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    # -- 断言辅助 --

    def called(self, name: str) -> int:
        """某接口方法被调用的次数。"""
        return sum(1 for call_name, _ in self.calls if call_name == name)

    def was_called_with(self, name: str, args: tuple) -> bool:
        """某接口方法是否以指定参数被调用过。"""
        return (name, args) in self.calls

    # -- InputController 接口实现 --

    def click(self, x: int, y: int) -> None:
        self.calls.append(("click", (x, y)))

    def press_key(self, key: str) -> None:
        self.calls.append(("press_key", (key,)))


class HotkeyManager(ABC):
    """全局热键接口(紧急停止,F10,DESIGN 第 17 节)。"""

    @abstractmethod
    def register(self, key: str, callback: Callable[[], None]) -> None:
        """注册全局热键;callback 在按键触发时调用。"""

    @abstractmethod
    def unregister_all(self) -> None:
        """注销全部热键(安全停止时释放热键状态)。"""


class MockHotkeyManager(HotkeyManager):
    """测试用 Mock:记录注册,通过 press() 模拟按下热键。"""

    def __init__(self) -> None:
        self._hotkeys: dict[str, Callable[[], None]] = {}
        self.calls: list[tuple[str, tuple]] = []

    # -- 场景编排 --

    def press(self, key: str) -> bool:
        """模拟按下热键;返回该热键是否已注册并触发。"""
        self.calls.append(("press", (key,)))
        callback = self._hotkeys.get(key)
        if callback is None:
            return False
        callback()
        return True

    # -- 断言辅助 --

    @property
    def registered_keys(self) -> list[str]:
        """当前已注册的热键列表。"""
        return list(self._hotkeys)

    # -- HotkeyManager 接口实现 --

    def register(self, key: str, callback: Callable[[], None]) -> None:
        self.calls.append(("register", (key,)))
        self._hotkeys[key] = callback

    def unregister_all(self) -> None:
        self.calls.append(("unregister_all", ()))
        self._hotkeys.clear()
