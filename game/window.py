"""窗口管理接口(W3 基础能力)。

对应 DESIGN.md 21 节 W3:查找目标窗口、激活窗口。
本文件只定义接口与测试用 Mock;真实 Windows 实现
(pywin32 / pywinauto)在 W5 阶段提供,需要 Windows 环境。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    """窗口信息。"""

    handle: int
    title: str
    left: int
    top: int
    width: int
    height: int

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """窗口矩形 (left, top, width, height)。"""
        return (self.left, self.top, self.width, self.height)


class WindowManager(ABC):
    """窗口查找与激活接口。"""

    @abstractmethod
    def find(self, title_contains: str) -> WindowInfo | None:
        """按标题模糊查找窗口;找不到返回 None。"""

    @abstractmethod
    def activate(self, window: WindowInfo) -> None:
        """把窗口带到前台。"""

    @abstractmethod
    def is_alive(self, window: WindowInfo) -> bool:
        """窗口是否仍存在(未被关闭)。"""


class MockWindowManager(WindowManager):
    """测试用 Mock:预编程窗口列表,支持模拟窗口关闭。"""

    def __init__(self, windows: list[WindowInfo] | None = None) -> None:
        self.windows: list[WindowInfo] = list(windows or [])
        self.dead_handles: set[int] = set()
        self.calls: list[tuple[str, tuple]] = []

    # -- 场景编排 --

    def add_window(self, window: WindowInfo) -> None:
        """添加一个虚拟窗口。"""
        self.windows.append(window)

    def close(self, handle: int) -> None:
        """模拟窗口关闭(此后 find/is_alive 均视为不存在)。"""
        self.dead_handles.add(handle)

    # -- 断言辅助 --

    def called(self, name: str) -> int:
        """某接口方法被调用的次数。"""
        return sum(1 for call_name, _ in self.calls if call_name == name)

    # -- WindowManager 接口实现 --

    def find(self, title_contains: str) -> WindowInfo | None:
        self.calls.append(("find", (title_contains,)))
        for window in self.windows:
            if window.handle in self.dead_handles:
                continue
            if title_contains in window.title:
                return window
        return None

    def activate(self, window: WindowInfo) -> None:
        self.calls.append(("activate", (window.handle,)))

    def is_alive(self, window: WindowInfo) -> bool:
        self.calls.append(("is_alive", (window.handle,)))
        if window.handle in self.dead_handles:
            return False
        return any(w.handle == window.handle for w in self.windows)
