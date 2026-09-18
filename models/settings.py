"""应用设置(Settings)数据模型。

对应 config/settings.yaml,结构见 DESIGN.md 第 7.1 节。
所有字段均带默认值,校验失败抛出 ConfigValidationError。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from utils.validation import (
    ConfigValidationError,
    optional_bool,
    optional_int,
    optional_str,
    reject_unknown_keys,
)

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass
class AppSection:
    """应用基础设置。"""

    language: str = "zh-CN"
    startup_delay_seconds: int = 5
    emergency_stop_key: str = "F10"
    pause_key: str = "F8"
    resume_key: str = "F9"

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "app") -> "AppSection":
        data = data or {}
        reject_unknown_keys(
            data,
            {
                "language",
                "startup_delay_seconds",
                "emergency_stop_key",
                "pause_key",
                "resume_key",
            },
            path,
        )
        return cls(
            language=optional_str(data.get("language"), f"{path}.language", "zh-CN"),
            startup_delay_seconds=optional_int(
                data.get("startup_delay_seconds"),
                f"{path}.startup_delay_seconds",
                default=5,
                minimum=0,
            ),
            emergency_stop_key=optional_str(
                data.get("emergency_stop_key"), f"{path}.emergency_stop_key", "F10"
            ),
            pause_key=optional_str(data.get("pause_key"), f"{path}.pause_key", "F8"),
            resume_key=optional_str(data.get("resume_key"), f"{path}.resume_key", "F9"),
        )


@dataclass
class GameSection:
    """游戏窗口设置。"""

    window_title_contains: str = "御龙在天"

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "game") -> "GameSection":
        data = data or {}
        reject_unknown_keys(data, {"window_title_contains"}, path)
        return cls(
            window_title_contains=optional_str(
                data.get("window_title_contains"),
                f"{path}.window_title_contains",
                "御龙在天",
            ),
        )


@dataclass
class RuntimeSection:
    """运行时设置。"""

    default_state_timeout_seconds: int = 120
    max_retries: int = 3
    loop_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "runtime") -> "RuntimeSection":
        data = data or {}
        reject_unknown_keys(
            data,
            {"default_state_timeout_seconds", "max_retries", "loop_enabled"},
            path,
        )
        return cls(
            default_state_timeout_seconds=optional_int(
                data.get("default_state_timeout_seconds"),
                f"{path}.default_state_timeout_seconds",
                default=120,
                minimum=1,
            ),
            max_retries=optional_int(
                data.get("max_retries"), f"{path}.max_retries", default=3, minimum=0
            ),
            loop_enabled=optional_bool(
                data.get("loop_enabled"), f"{path}.loop_enabled", True
            ),
        )


@dataclass
class LoggingSection:
    """日志设置。"""

    level: str = "INFO"
    file_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "logging") -> "LoggingSection":
        data = data or {}
        reject_unknown_keys(data, {"level", "file_enabled"}, path)
        level = optional_str(data.get("level"), f"{path}.level", "INFO").upper()
        if level not in VALID_LOG_LEVELS:
            raise ConfigValidationError(
                f"{path}.level: 必须是 {VALID_LOG_LEVELS} 之一,得到 {level!r}"
            )
        return cls(
            level=level,
            file_enabled=optional_bool(
                data.get("file_enabled"), f"{path}.file_enabled", True
            ),
        )


@dataclass
class AppSettings:
    """应用设置(完整)。"""

    app: AppSection = field(default_factory=AppSection)
    game: GameSection = field(default_factory=GameSection)
    runtime: RuntimeSection = field(default_factory=RuntimeSection)
    logging: LoggingSection = field(default_factory=LoggingSection)

    @classmethod
    def from_dict(cls, data: dict | None) -> "AppSettings":
        data = data or {}
        reject_unknown_keys(
            data, {"app", "game", "runtime", "logging"}, "settings"
        )
        return cls(
            app=AppSection.from_dict(data.get("app")),
            game=GameSection.from_dict(data.get("game")),
            runtime=RuntimeSection.from_dict(data.get("runtime")),
            logging=LoggingSection.from_dict(data.get("logging")),
        )
