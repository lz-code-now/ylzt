"""异常恢复辅助模块(W8)。

对应 DESIGN.md:

- 第 15 节:导航卡住检测(位置在间隔内几乎不动 → 视为卡住)
- 第 16 节:Recovery 事件记录(时间/状态/原因/截图/重试次数)
- 第 17 节:自动安全停止(连续异常达到阈值 → 请求停止)

全部为纯逻辑组件(注入 clock),不依赖平台与 UI,headless 可测。
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from game.image_match import save_image
from game.screen import ScreenImage
from models.state import State
from utils.logger import get_logger

logger = get_logger("engine")


# ----------------------------------------------------------------------
# 卡住检测(DESIGN 15:导航超时的补充,未超时但位置不动也应恢复)
# ----------------------------------------------------------------------


class StuckDetector:
    """导航卡住检测:按固定间隔采样位置,位移过小说明卡住。

    Args:
        interval_seconds: 采样间隔(如 30 秒)。
        min_distance: 间隔内位移小于该值(欧氏距离)判定卡住。
        clock: 单调时钟;测试可注入。
    """

    def __init__(
        self,
        interval_seconds: int,
        min_distance: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须 > 0")
        self.interval_seconds = interval_seconds
        self.min_distance = min_distance
        self._clock = clock
        self._last_sample_at: float | None = None
        self._last_position: tuple[int, int] | None = None

    def reset(self) -> None:
        """离开导航场景时清空采样状态。"""
        self._last_sample_at = None
        self._last_position = None

    def check(self, position: tuple[int, int] | None) -> bool:
        """报告当前位置;到达检测间隔时判断是否卡住。

        Returns:
            True 表示判定卡住;None 位置(识别失败)不参与判定。
        """
        if position is None:
            return False
        now = self._clock()
        if self._last_sample_at is None:
            self._sample(now, position)
            return False
        if now - self._last_sample_at < self.interval_seconds:
            return False
        assert self._last_position is not None
        moved = math.hypot(
            position[0] - self._last_position[0],
            position[1] - self._last_position[1],
        )
        self._sample(now, position)
        if moved < self.min_distance:
            logger.warning(
                "导航疑似卡住: %ds 内仅移动 %.1f(< %s)", self.interval_seconds, moved, self.min_distance
            )
            return True
        return False

    def _sample(self, now: float, position: tuple[int, int]) -> None:
        self._last_sample_at = now
        self._last_position = position


# ----------------------------------------------------------------------
# 连续失败计数(DESIGN 17 自动安全停止的依据)
# ----------------------------------------------------------------------


class FailureTracker:
    """连续失败计数:成功即清零;达到阈值触发自动安全停止。"""

    def __init__(self, threshold: int) -> None:
        if threshold <= 0:
            raise ValueError("threshold 必须 > 0")
        self.threshold = threshold
        self.count = 0

    def record_failure(self) -> int:
        """记录一次失败,返回当前计数。"""
        self.count += 1
        if self.count >= self.threshold:
            logger.error(
                "连续失败 %d 次达到阈值 %d,触发自动安全停止", self.count, self.threshold
            )
        return self.count

    def record_success(self) -> None:
        """任一关键动作成功即清零。"""
        self.count = 0

    @property
    def exceeded(self) -> bool:
        return self.count >= self.threshold


# ----------------------------------------------------------------------
# Recovery 事件(DESIGN 16 五要素)与截图
# ----------------------------------------------------------------------


@dataclass
class RecoveryEvent:
    """一次恢复事件:时间/状态/原因/截图/重试次数(DESIGN 16)。"""

    at: datetime
    state: State
    reason: str
    screenshot_path: str | None = None
    retry_index: int = 0


class RecoveryJournal:
    """恢复事件日志:记录每次恢复并保存现场截图。"""

    def __init__(
        self,
        debug_dir: Path | str | None = None,
        max_screenshots: int = 20,
    ) -> None:
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self.max_screenshots = max_screenshots
        self.events: list[RecoveryEvent] = []

    def record(
        self,
        state: State,
        reason: str,
        retry_index: int,
        screenshot: ScreenImage | None = None,
    ) -> RecoveryEvent:
        """记录事件;screenshot 非 None 且未超上限时保存 PNG。"""
        path: str | None = None
        if screenshot is not None and self.debug_dir is not None and len(self.events) < self.max_screenshots:
            try:
                self.debug_dir.mkdir(parents=True, exist_ok=True)
                filename = f"recover_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                target = self.debug_dir / filename
                save_image(screenshot, target)
                path = str(target)
            except OSError as exc:
                logger.warning("恢复截图保存失败: %s", exc)
        event = RecoveryEvent(
            at=datetime.now(),
            state=state,
            reason=reason,
            screenshot_path=path,
            retry_index=retry_index,
        )
        self.events.append(event)
        logger.warning(
            "Recovery #%d: state=%s reason=%s screenshot=%s",
            retry_index,
            state.value,
            reason,
            path or "无",
        )
        return event
