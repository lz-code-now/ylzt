"""图像工具与模板匹配测试(W4)。

使用合成图像(渐变背景/噪声块)验证,不依赖真实游戏截图。
"""

from __future__ import annotations

import numpy as np
import pytest

from game.image_match import (
    OpenCVTemplateMatcher,
    array_to_image,
    image_to_array,
    load_template,
    save_image,
)
from game.screen import ScreenImage, crop, solid_image


def gradient_image(width: int = 100, height: int = 100) -> ScreenImage:
    """渐变背景合成场景(非常量图像,避免 NCC 除零退化)。"""
    xs = np.tile(np.arange(width, dtype=np.int32), (height, 1))
    ys = np.tile(np.arange(height, dtype=np.int32).reshape(height, 1), (1, width))
    array = np.stack(
        [xs % 256, ys % 256, (xs + ys) % 256], axis=2
    ).astype(np.uint8)
    return array_to_image(array, "RGB")


def noise_template(width: int = 20, height: int = 15, seed: int = 7) -> ScreenImage:
    """带纹理的噪声模板(固定种子,可复现)。"""
    rng = np.random.default_rng(seed)
    array = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    return array_to_image(array, "RGB")


def embed_block(
    scene: ScreenImage, block: ScreenImage, x: int, y: int
) -> ScreenImage:
    """把 block 嵌入场景的指定位置。"""
    array = image_to_array(scene).copy()
    array[y : y + block.height, x : x + block.width] = image_to_array(block)
    return array_to_image(array, scene.mode)


# ----------------------------------------------------------------------
# ScreenImage 与 numpy 互转
# ----------------------------------------------------------------------


class TestImageConversion:
    def test_roundtrip_rgb(self):
        scene = gradient_image(16, 12)
        array = image_to_array(scene)
        assert array.shape == (12, 16, 3)
        restored = array_to_image(array, "RGB")
        assert restored.data == scene.data

    def test_grayscale_shape(self):
        image = solid_image(10, 8, (128,), mode="L")
        assert image_to_array(image).shape == (8, 10)

    def test_rejects_non_uint8_dtype(self):
        with pytest.raises(ValueError, match="uint8"):
            array_to_image(np.zeros((4, 4, 3), dtype=np.float64))

    def test_rejects_bad_ndim(self):
        with pytest.raises(ValueError, match="维度"):
            array_to_image(np.zeros((2, 2, 2, 3), dtype=np.uint8))


# ----------------------------------------------------------------------
# 裁剪
# ----------------------------------------------------------------------


class TestCrop:
    def test_crop_rect_and_pixels(self):
        scene = gradient_image(50, 40)
        part = crop(scene, 10, 5, 20, 10)
        assert (part.width, part.height) == (20, 10)
        assert part.mode == scene.mode
        # 裁剪按行拼接,各行在原字节流中不连续
        expected = b"".join(
            scene.data[row * 50 * 3 + 10 * 3 : row * 50 * 3 + 30 * 3]
            for row in range(5, 15)
        )
        assert part.data == expected

    def test_crop_out_of_bounds_raises(self):
        scene = solid_image(100, 100)
        with pytest.raises(ValueError, match="越界"):
            crop(scene, 90, 90, 20, 20)

    def test_crop_invalid_size_raises(self):
        scene = solid_image(100, 100)
        with pytest.raises(ValueError, match="尺寸"):
            crop(scene, 0, 0, 0, 10)


# ----------------------------------------------------------------------
# 保存与加载
# ----------------------------------------------------------------------


class TestSaveAndLoad:
    def test_save_then_load_roundtrip(self, tmp_path):
        image = solid_image(7, 5, (10, 200, 30))
        path = tmp_path / "tpl.png"
        save_image(image, path)
        assert path.exists()
        loaded = load_template(path)
        assert (loaded.width, loaded.height) == (7, 5)
        assert loaded.data == image.data

    def test_load_template_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_template(tmp_path / "missing.png")


# ----------------------------------------------------------------------
# 模板匹配
# ----------------------------------------------------------------------


class TestOpenCVTemplateMatcher:
    def test_match_found_returns_center(self):
        # 用渐变背景 + 嵌入唯一噪声块构造场景:
        # 纯渐变的 NCC pattern 平移不变,直接裁剪回匹配会得到多个并列最大值
        template = noise_template(width=20, height=15, seed=7)
        scene = embed_block(gradient_image(100, 100), template, 30, 40)
        result = OpenCVTemplateMatcher().match(scene, template, threshold=0.8)
        assert result.success is True
        assert result.value == (30 + 20 // 2, 40 + 15 // 2)
        assert result.confidence >= 0.99
        assert result.detail is None

    def test_match_not_found(self):
        scene = gradient_image(100, 100)
        template = noise_template(seed=99)
        result = OpenCVTemplateMatcher().match(scene, template, threshold=0.8)
        assert result.success is False
        assert result.value is None
        assert result.confidence < 0.8
        assert result.detail is not None

    def test_template_larger_than_image(self):
        scene = solid_image(10, 10)
        template = solid_image(20, 20)
        result = OpenCVTemplateMatcher().match(scene, template)
        assert result.success is False
        assert "大于图像" in result.detail

    def test_channels_mismatch(self):
        scene = solid_image(50, 50, (1, 2, 3))
        template = solid_image(10, 10, (1, 2, 3, 4), mode="BGRA")
        result = OpenCVTemplateMatcher().match(scene, template)
        assert result.success is False
        assert "通道数不一致" in result.detail

    def test_constant_image_does_not_crash(self):
        # 常量图像会让 NCC 分母为 0(NaN),必须防御而不是崩溃
        scene = solid_image(50, 50, (128, 128, 128))
        template = solid_image(10, 10, (128, 128, 128))
        result = OpenCVTemplateMatcher().match(scene, template)
        assert result.success is False
        assert result.value is None
