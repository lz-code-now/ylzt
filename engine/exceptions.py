"""Engine 层异常。"""

from __future__ import annotations


class EngineError(RuntimeError):
    """引擎层基础异常。"""


class StateTransitionError(EngineError):
    """非法状态转换(如在终态上继续驱动状态机)。"""
