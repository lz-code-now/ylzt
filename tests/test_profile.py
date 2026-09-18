"""W1 测试:挂机方案(Profile)加载、默认值、校验、错误提示。"""

import pytest

from app.bootstrap import load_profile
from models.profile import Profile
from utils.validation import ConfigValidationError


def test_load_default_profile():
    """W1 验收:读取 default.yaml 得到 map/x/y/tolerance/max_local_revive。"""
    profile = load_profile("default")
    assert profile.name == "默认挂机点"
    assert profile.location.map == "目标地图"
    assert profile.location.x == 123
    assert profile.location.y == 456
    assert profile.location.tolerance == 10
    assert profile.max_local_revive == 5


def test_profile_defaults():
    """缺少可选字段时使用默认值。"""
    profile = Profile.from_dict(
        {"name": "测试方案", "location": {"map": "地图A", "x": 1, "y": 2}}
    )
    assert profile.location.tolerance == 10
    assert profile.navigation.enabled is True
    assert profile.navigation.timeout_seconds == 180
    assert profile.navigation.retry_count == 3
    assert profile.combat.auto_start is True
    assert profile.combat.start_retry_count == 3
    assert profile.revive.max_local_revive == 5
    assert profile.revive.local_revive_wait_seconds == 3
    assert profile.revive.safe_revive_wait_seconds == 5
    assert profile.return_home.wait_after_return_seconds == 5
    assert profile.recovery.max_recovery_count == 3


def test_profile_missing_name():
    with pytest.raises(ConfigValidationError, match="name"):
        Profile.from_dict({"location": {"map": "m", "x": 1, "y": 2}})


def test_profile_missing_location():
    with pytest.raises(ConfigValidationError, match="location"):
        Profile.from_dict({"name": "n"})


def test_profile_missing_location_map():
    with pytest.raises(ConfigValidationError, match=r"location\.map"):
        Profile.from_dict({"name": "n", "location": {"x": 1, "y": 2}})


def test_profile_invalid_x_type():
    with pytest.raises(ConfigValidationError, match=r"location\.x"):
        Profile.from_dict(
            {"name": "n", "location": {"map": "m", "x": "abc", "y": 2}}
        )


def test_profile_invalid_tolerance():
    with pytest.raises(ConfigValidationError, match="tolerance"):
        Profile.from_dict(
            {
                "name": "n",
                "location": {"map": "m", "x": 1, "y": 2, "tolerance": 0},
            }
        )


def test_profile_invalid_max_local_revive():
    with pytest.raises(ConfigValidationError, match="max_local_revive"):
        Profile.from_dict(
            {
                "name": "n",
                "location": {"map": "m", "x": 1, "y": 2},
                "revive": {"max_local_revive": -1},
            }
        )


def test_profile_unknown_field():
    with pytest.raises(ConfigValidationError, match="未知字段"):
        Profile.from_dict(
            {
                "name": "n",
                "location": {"map": "m", "x": 1, "y": 2},
                "no_such_section": {},
            }
        )


def test_load_profile_file_not_found():
    with pytest.raises(ConfigValidationError, match="不存在"):
        load_profile("no_such_profile")


def test_load_profile_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigValidationError, match="YAML"):
        load_profile(path=bad)


def test_load_profile_top_level_not_mapping(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigValidationError, match="映射"):
        load_profile(path=bad)
