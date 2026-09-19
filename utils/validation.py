"""参数校验工具(配置层使用)。

所有校验失败统一抛出 ConfigValidationError,
错误消息包含字段路径,便于用户定位配置问题。
"""

from __future__ import annotations


class ConfigValidationError(ValueError):
    """配置数据校验失败。"""


def reject_unknown_keys(data: dict, known_keys: set[str], path: str) -> None:
    """拒绝未知字段,用于配置错误提示。"""
    unknown = set(data) - known_keys
    if unknown:
        raise ConfigValidationError(
            f"{path}: 存在未知字段: {', '.join(sorted(unknown))}"
        )


def require_str(value: object, path: str) -> str:
    """校验必填非空字符串。"""
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{path}: 必须是非空字符串,得到 {value!r}")
    return value


def require_int(
    value: object,
    path: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """校验必填整数(可选范围)。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigValidationError(f"{path}: 必须是整数,得到 {value!r}")
    return _check_int_range(value, path, minimum, maximum)


def require_bool(value: object, path: str) -> bool:
    """校验必填布尔值。"""
    if not isinstance(value, bool):
        raise ConfigValidationError(f"{path}: 必须是布尔值,得到 {value!r}")
    return value


def optional_str(value: object, path: str, default: str) -> str:
    """可选字符串,缺省时返回默认值。"""
    if value is None:
        return default
    return require_str(value, path)


def optional_int(
    value: object,
    path: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """可选整数,缺省时返回默认值。"""
    if value is None:
        return default
    return require_int(value, path, minimum, maximum)


def optional_bool(value: object, path: str, default: bool) -> bool:
    """可选布尔值,缺省时返回默认值。"""
    if value is None:
        return default
    return require_bool(value, path)


def optional_str_or_none(value: object, path: str) -> str | None:
    """可选字符串,缺省(null/省略)时返回 None。"""
    if value is None:
        return None
    return require_str(value, path)


def optional_float(
    value: object,
    path: str,
    default: float,
    minimum: float | None = None,
) -> float:
    """可选浮点数,缺省时返回默认值(接受 int/float,拒绝 bool)。"""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigValidationError(f"{path}: 必须是数字,得到 {value!r}")
    value = float(value)
    if minimum is not None and value < minimum:
        raise ConfigValidationError(f"{path}: 必须 >= {minimum},得到 {value}")
    return value


def optional_point(
    value: object,
    path: str,
    default: tuple[int, int] | None = None,
) -> tuple[int, int] | None:
    """可选坐标点 [x, y];必须恰好两个非负整数。"""
    if value is None:
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigValidationError(
            f"{path}: 必须是 [x, y] 两元素序列,得到 {value!r}"
        )
    x = require_int(value[0], f"{path}[0]")
    y = require_int(value[1], f"{path}[1]")
    if x < 0 or y < 0:
        raise ConfigValidationError(f"{path}: 坐标必须非负,得到 [{x}, {y}]")
    return (x, y)


def _check_int_range(
    value: int,
    path: str,
    minimum: int | None,
    maximum: int | None,
) -> int:
    if minimum is not None and value < minimum:
        raise ConfigValidationError(f"{path}: 必须 >= {minimum},得到 {value}")
    if maximum is not None and value > maximum:
        raise ConfigValidationError(f"{path}: 必须 <= {maximum},得到 {value}")
    return value
