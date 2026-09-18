"""挂机方案(Profile)数据模型。

对应 config/profiles/*.yaml,结构见 DESIGN.md 第 7.2 节。
所有字段均带默认值(必填项除外),校验失败抛出 ConfigValidationError。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from utils.validation import (
    ConfigValidationError,
    optional_bool,
    optional_int,
    reject_unknown_keys,
    require_int,
    require_str,
)


@dataclass
class Location:
    """挂机位置。"""

    map: str
    x: int
    y: int
    tolerance: int = 10

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "location") -> "Location":
        data = data or {}
        reject_unknown_keys(data, {"map", "x", "y", "tolerance"}, path)
        for key in ("map", "x", "y"):
            if key not in data:
                raise ConfigValidationError(f"{path}.{key}: 缺少必填字段")
        return cls(
            map=require_str(data["map"], f"{path}.map"),
            x=require_int(data["x"], f"{path}.x"),
            y=require_int(data["y"], f"{path}.y"),
            tolerance=optional_int(
                data.get("tolerance"), f"{path}.tolerance", default=10, minimum=1
            ),
        )


@dataclass
class Navigation:
    """寻路设置。"""

    enabled: bool = True
    timeout_seconds: int = 180
    retry_count: int = 3

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "navigation") -> "Navigation":
        data = data or {}
        reject_unknown_keys(data, {"enabled", "timeout_seconds", "retry_count"}, path)
        return cls(
            enabled=optional_bool(data.get("enabled"), f"{path}.enabled", True),
            timeout_seconds=optional_int(
                data.get("timeout_seconds"),
                f"{path}.timeout_seconds",
                default=180,
                minimum=1,
            ),
            retry_count=optional_int(
                data.get("retry_count"), f"{path}.retry_count", default=3, minimum=0
            ),
        )


@dataclass
class Combat:
    """自动战斗设置。"""

    enabled: bool = True
    auto_start: bool = True
    start_retry_count: int = 3

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "combat") -> "Combat":
        data = data or {}
        reject_unknown_keys(
            data, {"enabled", "auto_start", "start_retry_count"}, path
        )
        return cls(
            enabled=optional_bool(data.get("enabled"), f"{path}.enabled", True),
            auto_start=optional_bool(data.get("auto_start"), f"{path}.auto_start", True),
            start_retry_count=optional_int(
                data.get("start_retry_count"),
                f"{path}.start_retry_count",
                default=3,
                minimum=0,
            ),
        )


@dataclass
class Revive:
    """复活设置。"""

    enabled: bool = True
    max_local_revive: int = 5
    local_revive_wait_seconds: int = 3
    safe_revive_wait_seconds: int = 5

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "revive") -> "Revive":
        data = data or {}
        reject_unknown_keys(
            data,
            {
                "enabled",
                "max_local_revive",
                "local_revive_wait_seconds",
                "safe_revive_wait_seconds",
            },
            path,
        )
        return cls(
            enabled=optional_bool(data.get("enabled"), f"{path}.enabled", True),
            max_local_revive=optional_int(
                data.get("max_local_revive"),
                f"{path}.max_local_revive",
                default=5,
                minimum=0,
            ),
            local_revive_wait_seconds=optional_int(
                data.get("local_revive_wait_seconds"),
                f"{path}.local_revive_wait_seconds",
                default=3,
                minimum=1,
            ),
            safe_revive_wait_seconds=optional_int(
                data.get("safe_revive_wait_seconds"),
                f"{path}.safe_revive_wait_seconds",
                default=5,
                minimum=1,
            ),
        )


@dataclass
class ReturnHome:
    """回城设置。"""

    enabled: bool = True
    wait_after_return_seconds: int = 5

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "return_home") -> "ReturnHome":
        data = data or {}
        reject_unknown_keys(
            data, {"enabled", "wait_after_return_seconds"}, path
        )
        return cls(
            enabled=optional_bool(data.get("enabled"), f"{path}.enabled", True),
            wait_after_return_seconds=optional_int(
                data.get("wait_after_return_seconds"),
                f"{path}.wait_after_return_seconds",
                default=5,
                minimum=1,
            ),
        )


@dataclass
class Recovery:
    """恢复设置。"""

    enabled: bool = True
    max_recovery_count: int = 3

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "recovery") -> "Recovery":
        data = data or {}
        reject_unknown_keys(data, {"enabled", "max_recovery_count"}, path)
        return cls(
            enabled=optional_bool(data.get("enabled"), f"{path}.enabled", True),
            max_recovery_count=optional_int(
                data.get("max_recovery_count"),
                f"{path}.max_recovery_count",
                default=3,
                minimum=1,
            ),
        )


@dataclass
class Profile:
    """挂机方案(完整)。"""

    name: str
    location: Location
    navigation: Navigation = field(default_factory=Navigation)
    combat: Combat = field(default_factory=Combat)
    revive: Revive = field(default_factory=Revive)
    return_home: ReturnHome = field(default_factory=ReturnHome)
    recovery: Recovery = field(default_factory=Recovery)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Profile":
        data = data or {}
        reject_unknown_keys(
            data,
            {
                "name",
                "location",
                "navigation",
                "combat",
                "revive",
                "return_home",
                "recovery",
            },
            "profile",
        )
        if "name" not in data:
            raise ConfigValidationError("name: 缺少必填字段")
        if "location" not in data:
            raise ConfigValidationError("location: 缺少必填字段")
        location_raw = data["location"]
        if not isinstance(location_raw, dict):
            raise ConfigValidationError("location: 必须是映射结构")
        return cls(
            name=require_str(data["name"], "name"),
            location=Location.from_dict(location_raw),
            navigation=Navigation.from_dict(data.get("navigation")),
            combat=Combat.from_dict(data.get("combat")),
            revive=Revive.from_dict(data.get("revive")),
            return_home=ReturnHome.from_dict(data.get("return_home")),
            recovery=Recovery.from_dict(data.get("recovery")),
        )

    @property
    def max_local_revive(self) -> int:
        """DESIGN W1 验收字段:最大原地复活次数。"""
        return self.revive.max_local_revive
