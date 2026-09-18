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
