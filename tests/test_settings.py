"""W1 测试:应用设置(Settings)加载与校验。"""

import pytest

from app.bootstrap import load_settings
from models.settings import AppSettings
from utils.validation import ConfigValidationError


def test_load_default_settings():
    settings = load_settings()
    assert settings.app.language == "zh-CN"
    assert settings.app.startup_delay_seconds == 5
    assert settings.app.emergency_stop_key == "F10"
    assert settings.app.pause_key == "F8"
    assert settings.app.resume_key == "F9"
    assert settings.game.window_title_contains == "御龙在天"
    assert settings.runtime.default_state_timeout_seconds == 120
    assert settings.runtime.max_retries == 3
    assert settings.runtime.loop_enabled is True
    assert settings.logging.level == "INFO"
    assert settings.logging.file_enabled is True


def test_settings_defaults():
    settings = AppSettings.from_dict({})
    assert settings.app.language == "zh-CN"
    assert settings.app.startup_delay_seconds == 5
    assert settings.game.window_title_contains == "御龙在天"
    assert settings.runtime.default_state_timeout_seconds == 120
    assert settings.runtime.max_retries == 3
    assert settings.runtime.loop_enabled is True
    assert settings.logging.level == "INFO"
    assert settings.logging.file_enabled is True


def test_settings_log_level_normalized():
    settings = AppSettings.from_dict({"logging": {"level": "debug"}})
    assert settings.logging.level == "DEBUG"


def test_settings_invalid_log_level():
    with pytest.raises(ConfigValidationError, match="level"):
        AppSettings.from_dict({"logging": {"level": "INVALID"}})


def test_settings_invalid_startup_delay():
    with pytest.raises(ConfigValidationError, match="startup_delay_seconds"):
        AppSettings.from_dict({"app": {"startup_delay_seconds": -1}})


def test_settings_unknown_section():
    with pytest.raises(ConfigValidationError, match="未知字段"):
        AppSettings.from_dict({"no_such_section": {}})


def test_load_settings_file_not_found(tmp_path):
    with pytest.raises(ConfigValidationError, match="不存在"):
        load_settings(path=tmp_path / "missing.yaml")
