"""应用设置(Settings)数据模型。

对应 config/settings.yaml,结构见 DESIGN.md 第 7.1 节。
所有字段均带默认值,校验失败抛出 ConfigValidationError。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.region import Region
from utils.validation import (
    ConfigValidationError,
    optional_bool,
    optional_float,
    optional_int,
    optional_point,
    optional_str,
    optional_str_or_none,
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
class ActionBindings:
    """游戏动作绑定(W5):优先使用游戏自身 UI/快捷键(DESIGN W5)。

    Attributes:
        auto_combat_key: 自动战斗快捷键;None 表示用鼠标点击按钮坐标。
        auto_combat_click: 自动战斗按钮的窗口内相对坐标;None 表示不点击。
        stop_combat_key: 停止战斗快捷键;None 表示仅再次切换快捷键。
        navigate_key: 游戏内寻路快捷键(可选)。
        map_shortcut: 打开大地图的快捷键(可选)。
        local_revive_click: 死亡对话框"原地复活"按钮坐标(窗口内)。
        safe_revive_click: 死亡对话框"安全复活"按钮坐标(窗口内)。
        return_home_key: 回城快捷键(可选)。
        return_home_click: 回城按钮坐标(窗口内,可选)。
        minimap_scale: 小地图坐标 → 世界坐标的换算比例(0 表示未标定)。
        minimap_origin: 小地图左上角的窗口内相对坐标 (x, y)。
        post_action_delay_seconds: 动作触发后的固定等待(给游戏反应时间)。
    """

    auto_combat_key: str | None = None
    auto_combat_click: tuple[int, int] | None = None
    stop_combat_key: str | None = None
    navigate_key: str | None = None
    map_shortcut: str | None = None
    local_revive_click: tuple[int, int] | None = None
    safe_revive_click: tuple[int, int] | None = None
    return_home_key: str | None = None
    return_home_click: tuple[int, int] | None = None
    minimap_scale: float = 0.0
    minimap_origin: tuple[int, int] = (0, 0)
    post_action_delay_seconds: float = 0.5

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "game.actions") -> "ActionBindings":
        data = data or {}
        reject_unknown_keys(
            data,
            {
                "auto_combat_key",
                "auto_combat_click",
                "stop_combat_key",
                "navigate_key",
                "map_shortcut",
                "local_revive_click",
                "safe_revive_click",
                "return_home_key",
                "return_home_click",
                "minimap_scale",
                "minimap_origin",
                "post_action_delay_seconds",
            },
            path,
        )
        return cls(
            auto_combat_key=optional_str_or_none(
                data.get("auto_combat_key"), f"{path}.auto_combat_key"
            ),
            auto_combat_click=optional_point(
                data.get("auto_combat_click"), f"{path}.auto_combat_click"
            ),
            stop_combat_key=optional_str_or_none(
                data.get("stop_combat_key"), f"{path}.stop_combat_key"
            ),
            navigate_key=optional_str_or_none(
                data.get("navigate_key"), f"{path}.navigate_key"
            ),
            map_shortcut=optional_str_or_none(
                data.get("map_shortcut"), f"{path}.map_shortcut"
            ),
            local_revive_click=optional_point(
                data.get("local_revive_click"), f"{path}.local_revive_click"
            ),
            safe_revive_click=optional_point(
                data.get("safe_revive_click"), f"{path}.safe_revive_click"
            ),
            return_home_key=optional_str_or_none(
                data.get("return_home_key"), f"{path}.return_home_key"
            ),
            return_home_click=optional_point(
                data.get("return_home_click"), f"{path}.return_home_click"
            ),
            minimap_scale=optional_float(
                data.get("minimap_scale"), f"{path}.minimap_scale", default=0.0, minimum=0.0
            ),
            minimap_origin=optional_point(
                data.get("minimap_origin"), f"{path}.minimap_origin", default=(0, 0)
            ),
            post_action_delay_seconds=optional_float(
                data.get("post_action_delay_seconds"),
                f"{path}.post_action_delay_seconds",
                default=0.5,
                minimum=0.0,
            ),
        )


@dataclass
class OcrSection:
    """OCR 引擎配置(W6)。

    Attributes:
        engine: 引擎类型;"mock" 用可脚本化 Mock,"tesseract" 用真实引擎。
        tesseract_cmd: tesseract 可执行文件路径;None 用系统 PATH。
        lang: Tesseract 语言包(如 "chi_sim+eng")。
        psm: Tesseract 页面分割模式(7=单行文本,适合地图名/坐标条)。
        min_confidence: 识别置信度低于该值视为失败(0~100)。
    """

    engine: str = "mock"
    tesseract_cmd: str | None = None
    lang: str = "chi_sim+eng"
    psm: int = 7
    min_confidence: float = 60.0

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "game.ocr") -> "OcrSection":
        data = data or {}
        reject_unknown_keys(
            data,
            {"engine", "tesseract_cmd", "lang", "psm", "min_confidence"},
            path,
        )
        engine = optional_str(data.get("engine"), f"{path}.engine", "mock").lower()
        if engine not in {"mock", "tesseract"}:
            raise ConfigValidationError(
                f"{path}.engine: 必须是 mock 或 tesseract,得到 {engine!r}"
            )
        cmd = optional_str_or_none(data.get("tesseract_cmd"), f"{path}.tesseract_cmd")
        return cls(
            engine=engine,
            tesseract_cmd=cmd,
            lang=optional_str(data.get("lang"), f"{path}.lang", "chi_sim+eng"),
            psm=optional_int(data.get("psm"), f"{path}.psm", default=7, minimum=0),
            min_confidence=optional_float(
                data.get("min_confidence"),
                f"{path}.min_confidence",
                default=60.0,
                minimum=0.0,
            ),
        )


@dataclass
class GameSection:
    """游戏窗口设置。

    regions:识别区域(ROI,DESIGN 9.2),键为区域名
    (map_name / position / death_dialog / combat_button)。
    actions:动作绑定(快捷键/点击/小地图换算,DESIGN W5)。
    ocr:OCR 引擎配置(W6)。
    实际坐标必须通过测试工具在真实游戏中确定。
    """

    window_title_contains: str = "御龙在天"
    regions: dict[str, Region] = field(default_factory=dict)
    actions: ActionBindings = field(default_factory=ActionBindings)
    ocr: OcrSection = field(default_factory=OcrSection)

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "game") -> "GameSection":
        data = data or {}
        reject_unknown_keys(
            data, {"window_title_contains", "regions", "actions", "ocr"}, path
        )
        regions_raw = data.get("regions") or {}
        if not isinstance(regions_raw, dict):
            raise ConfigValidationError(f"{path}.regions: 必须是映射结构")
        regions: dict[str, Region] = {}
        for name, raw in regions_raw.items():
            if not isinstance(raw, dict):
                raise ConfigValidationError(
                    f"{path}.regions.{name}: 必须是映射结构"
                )
            regions[name] = Region.from_dict(raw, f"{path}.regions.{name}")
        return cls(
            window_title_contains=optional_str(
                data.get("window_title_contains"),
                f"{path}.window_title_contains",
                "御龙在天",
            ),
            regions=regions,
            actions=ActionBindings.from_dict(data.get("actions"), f"{path}.actions"),
            ocr=OcrSection.from_dict(data.get("ocr"), f"{path}.ocr"),
        )


@dataclass
class RuntimeSection:
    """运行时设置(W8 扩展异常恢复参数)。"""

    default_state_timeout_seconds: int = 120
    max_retries: int = 3
    loop_enabled: bool = True
    # W8 异常恢复
    stuck_check_interval_seconds: int = 30
    stuck_min_distance: int = 5
    max_consecutive_failures: int = 5
    max_recovery_screenshot: int = 20
    debug_dir: str = "debug"

    @classmethod
    def from_dict(cls, data: dict | None, path: str = "runtime") -> "RuntimeSection":
        data = data or {}
        reject_unknown_keys(
            data,
            {
                "default_state_timeout_seconds",
                "max_retries",
                "loop_enabled",
                "stuck_check_interval_seconds",
                "stuck_min_distance",
                "max_consecutive_failures",
                "max_recovery_screenshot",
                "debug_dir",
            },
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
            stuck_check_interval_seconds=optional_int(
                data.get("stuck_check_interval_seconds"),
                f"{path}.stuck_check_interval_seconds",
                default=30,
                minimum=1,
            ),
            stuck_min_distance=optional_int(
                data.get("stuck_min_distance"),
                f"{path}.stuck_min_distance",
                default=5,
                minimum=0,
            ),
            max_consecutive_failures=optional_int(
                data.get("max_consecutive_failures"),
                f"{path}.max_consecutive_failures",
                default=5,
                minimum=1,
            ),
            max_recovery_screenshot=optional_int(
                data.get("max_recovery_screenshot"),
                f"{path}.max_recovery_screenshot",
                default=20,
                minimum=0,
            ),
            debug_dir=optional_str(data.get("debug_dir"), f"{path}.debug_dir", "debug"),
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
