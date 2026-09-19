"""识别区域(ROI)数据模型。

对应 DESIGN.md 9.2 节:不要每次扫描整个屏幕,识别区域通过配置指定;
实际坐标必须通过测试工具在真实游戏中确定,不能凭空写死。
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.validation import (
    ConfigValidationError,
    reject_unknown_keys,
    require_int,
)


@dataclass(frozen=True)
class Region:
    """屏幕识别区域(左上角坐标 + 宽高)。"""

    x: int
    y: int
    width: int
    height: int

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """(x, y, width, height)。"""
        return (self.x, self.y, self.width, self.height)

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "region") -> "Region":
        """从配置字典构建;字段名即 settings.game.regions 中的键。"""
        data = data or {}
        reject_unknown_keys(data, {"x", "y", "width", "height"}, path)
        for key in ("x", "y", "width", "height"):
            if key not in data:
                raise ConfigValidationError(f"{path}.{key}: 缺少必填字段")
        return cls(
            x=require_int(data["x"], f"{path}.x", minimum=0),
            y=require_int(data["y"], f"{path}.y", minimum=0),
            width=require_int(data["width"], f"{path}.width", minimum=1),
            height=require_int(data["height"], f"{path}.height", minimum=1),
        )
