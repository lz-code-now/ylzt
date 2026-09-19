"""识别结果数据模型。

对应 DESIGN.md 21 节 W4 要求:所有识别模块都必须携带
confidence / timestamp / debug screenshot,不要返回简单 bool 后无法排查。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RecognitionResult:
    """统一识别结果。

    Attributes:
        success: 识别是否成功。
        value: 识别值,含义随识别器而定:
            地图名(str)、坐标 (x, y)、是否死亡(bool)、是否已开自动战斗(bool)等。
        confidence: 置信度,0.0 ~ 1.0。
        timestamp: 识别时间。
        debug_screenshot_path: 识别失败时保存的调试截图路径(未配置调试目录时为 None)。
        detail: 附加说明(如失败原因),便于排查。
    """

    success: bool
    value: object = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    debug_screenshot_path: str | None = None
    detail: str | None = None
