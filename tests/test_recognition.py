"""识别器与 ROI 配置测试(W4,DESIGN 9、10、13.1、21-W4)。

覆盖:坐标文本解析、Region 校验、settings.regions 加载、
四大识别器(地图/坐标/死亡/战斗状态)与调试截图。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.bootstrap import load_settings
from game.image_match import (
    OpenCVTemplateMatcher,
    array_to_image,
    image_to_array,
)
from game.ocr import MockOcrEngine
from game.recognition import (
    CombatStateRecognizer,
    DeathRecognizer,
    MapRecognizer,
    PositionRecognizer,
    parse_position,
)
from game.screen import ScreenImage, crop, solid_image
from models.recognition import RecognitionResult
from models.region import Region
from models.settings import AppSettings
from utils.validation import ConfigValidationError


def gradient_image(width: int = 100, height: int = 100) -> ScreenImage:
    """渐变背景合成场景。"""
    xs = np.tile(np.arange(width, dtype=np.int32), (height, 1))
    ys = np.tile(np.arange(height, dtype=np.int32).reshape(height, 1), (1, width))
    array = np.stack([xs % 256, ys % 256, (xs + ys) % 256], axis=2).astype(np.uint8)
    return array_to_image(array, "RGB")


def noise_template(width: int = 20, height: int = 15, seed: int = 7) -> ScreenImage:
    """带纹理的噪声模板(固定种子,可复现)。"""
    rng = np.random.default_rng(seed)
    array = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    return array_to_image(array, "RGB")


def embed_block(
    scene: ScreenImage, block: ScreenImage, x: int, y: int
) -> ScreenImage:
    array = image_to_array(scene).copy()
    array[y : y + block.height, x : x + block.width] = image_to_array(block)
    return array_to_image(array, scene.mode)


# ----------------------------------------------------------------------
# 坐标文本解析
# ----------------------------------------------------------------------


class TestParsePosition:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("(123, 456)", (123, 456)),
            ("(123,456)", (123, 456)),
            ("123,456", (123, 456)),
            ("123,456", (123, 456)),
            ("坐标: 123 , 456", (123, 456)),
            ("(0, 0)", (0, 0)),
        ],
    )
    def test_valid(self, text, expected):
        assert parse_position(text) == expected

    @pytest.mark.parametrize("text", [None, "", "abc", "(12,)", "没有坐标"])
    def test_invalid(self, text):
        assert parse_position(text) is None


# ----------------------------------------------------------------------
# Region 与 settings.regions
# ----------------------------------------------------------------------


class TestRegion:
    def test_from_dict(self):
        region = Region.from_dict({"x": 1, "y": 2, "width": 300, "height": 100})
        assert region.rect == (1, 2, 300, 100)

    def test_missing_field(self):
        with pytest.raises(ConfigValidationError, match="缺少必填字段"):
            Region.from_dict({"x": 1, "y": 2, "width": 3})

    def test_invalid_width(self):
        with pytest.raises(ConfigValidationError, match="width"):
            Region.from_dict({"x": 0, "y": 0, "width": 0, "height": 4})

    def test_negative_x(self):
        with pytest.raises(ConfigValidationError, match="x"):
            Region.from_dict({"x": -1, "y": 0, "width": 1, "height": 4})

    def test_unknown_field(self):
        with pytest.raises(ConfigValidationError, match="未知字段"):
            Region.from_dict({"x": 0, "y": 0, "width": 1, "height": 1, "z": 1})


class TestSettingsRegions:
    def test_default_settings_load_four_regions(self):
        settings = load_settings()
        assert set(settings.game.regions) == {
            "map_name",
            "position",
            "death_dialog",
            "combat_button",
        }
        assert settings.game.regions["map_name"].rect == (0, 0, 300, 100)
        assert settings.game.regions["combat_button"].rect == (1000, 600, 300, 200)

    def test_regions_default_empty(self):
        assert AppSettings.from_dict({}).game.regions == {}

    def test_regions_not_mapping(self):
        with pytest.raises(ConfigValidationError, match="regions"):
            AppSettings.from_dict({"game": {"regions": "not-a-map"}})

    def test_region_item_not_mapping(self):
        with pytest.raises(ConfigValidationError, match="regions.map_name"):
            AppSettings.from_dict({"game": {"regions": {"map_name": "bad"}}})

    def test_region_item_invalid_field(self):
        with pytest.raises(ConfigValidationError, match="regions.map_name.width"):
            AppSettings.from_dict(
                {"game": {"regions": {"map_name": {"x": 0, "y": 0, "width": -1, "height": 1}}}}
            )


# ----------------------------------------------------------------------
# 地图识别
# ----------------------------------------------------------------------


class TestMapRecognizer:
    def test_success(self):
        ocr = MockOcrEngine(confidence=0.95)
        ocr.script = ["目标地图"]
        result = MapRecognizer(ocr).recognize(solid_image(300, 100))
        assert result.success is True
        assert result.value == "目标地图"
        assert result.confidence == 0.95
        assert result.timestamp is not None

    def test_roi_crop(self):
        ocr = MockOcrEngine()
        ocr.script = ["目标地图"]
        region = Region(x=10, y=20, width=300, height=100)
        recognizer = MapRecognizer(ocr, region=region)
        recognizer.recognize(solid_image(1920, 1080))
        # OCR 收到的应是裁剪后的 ROI
        assert ocr.calls == [(300, 100)]

    def test_failure_saves_debug_screenshot(self, tmp_path):
        ocr = MockOcrEngine()  # script 为空 → 无文本
        recognizer = MapRecognizer(ocr, debug_dir=tmp_path)
        result = recognizer.recognize(solid_image(300, 100))
        assert result.success is False
        assert result.detail is not None
        assert result.debug_screenshot_path is not None
        assert Path(result.debug_screenshot_path).exists()

    def test_failure_without_debug_dir(self):
        ocr = MockOcrEngine()
        result = MapRecognizer(ocr).recognize(solid_image(300, 100))
        assert result.success is False
        assert result.debug_screenshot_path is None


# ----------------------------------------------------------------------
# 坐标识别
# ----------------------------------------------------------------------


class TestPositionRecognizer:
    def test_success(self):
        ocr = MockOcrEngine(confidence=0.9)
        ocr.script = ["(123, 456)"]
        result = PositionRecognizer(ocr).recognize(solid_image(300, 150))
        assert result.success is True
        assert result.value == (123, 456)
        assert result.confidence == 0.9

    def test_unparseable_text_fails_with_debug(self, tmp_path):
        ocr = MockOcrEngine()
        ocr.script = ["乱码文本"]
        recognizer = PositionRecognizer(ocr, debug_dir=tmp_path)
        result = recognizer.recognize(solid_image(300, 150))
        assert result.success is False
        assert result.value is None
        assert "无法从 OCR 文本解析坐标" in result.detail
        assert Path(result.debug_screenshot_path).exists()


# ----------------------------------------------------------------------
# 死亡识别(DESIGN 13.1)
# ----------------------------------------------------------------------


class TestDeathRecognizer:
    def test_dead_detected(self):
        template = noise_template(seed=1)
        scene = embed_block(gradient_image(), template, x=50, y=60)
        recognizer = DeathRecognizer(OpenCVTemplateMatcher(), template)
        result = recognizer.recognize(scene)
        assert result.success is True
        assert result.value is True
        assert result.confidence >= 0.8

    def test_alive_not_detected_with_debug(self, tmp_path):
        template = noise_template(seed=1)
        scene = gradient_image()  # 场景中没有死亡块
        recognizer = DeathRecognizer(
            OpenCVTemplateMatcher(), template, debug_dir=tmp_path
        )
        result = recognizer.recognize(scene)
        assert result.success is False
        assert result.value is False
        assert result.debug_screenshot_path is not None
        assert Path(result.debug_screenshot_path).exists()

    def test_roi_region(self):
        template = noise_template(seed=2)
        scene = embed_block(gradient_image(200, 150), template, x=120, y=80)
        # 只在死亡对话框区域内查找
        region = Region(x=100, y=60, width=100, height=60)
        recognizer = DeathRecognizer(OpenCVTemplateMatcher(), template, region=region)
        result = recognizer.recognize(scene)
        assert result.success is True


# ----------------------------------------------------------------------
# 自动战斗状态识别
# ----------------------------------------------------------------------


class TestCombatStateRecognizer:
    def test_enabled_detected(self):
        template = noise_template(seed=3)
        scene = embed_block(gradient_image(), template, x=20, y=30)
        recognizer = CombatStateRecognizer(OpenCVTemplateMatcher(), template)
        result = recognizer.recognize(scene)
        assert result.success is True
        assert result.value is True

    def test_disabled_not_detected(self):
        template = noise_template(seed=3)
        recognizer = CombatStateRecognizer(OpenCVTemplateMatcher(), template)
        result = recognizer.recognize(gradient_image())
        assert result.success is False
        assert result.value is False


# ----------------------------------------------------------------------
# RecognitionResult 结构(W4 要求:不返回简单 bool)
# ----------------------------------------------------------------------


class TestRecognitionResult:
    def test_carries_confidence_and_timestamp(self):
        result = RecognitionResult(success=True, value=(1, 2), confidence=0.87)
        assert result.confidence == 0.87
        assert result.timestamp is not None
        assert result.debug_screenshot_path is None
        assert result.detail is None
