"""测试公共工具:假时钟与默认挂机方案。"""

from __future__ import annotations

import pytest

from models.profile import Location, Profile


class FakeClock:
    """可手动推进的单调时钟,用于测试 Watchdog 超时。"""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def profile() -> Profile:
    """默认测试挂机方案:目标 (100, 200),容差 10,复活上限 5。"""
    return Profile(
        name="测试方案",
        location=Location(map="目标地图", x=100, y=200, tolerance=10),
    )
