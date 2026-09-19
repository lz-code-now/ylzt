"""模板匹配(W4,DESIGN 第 9 节识别优先级中的模板匹配层)。

依赖 OpenCV,提供:

- ScreenImage 与 numpy 数组互转(image_to_array / array_to_image)
- 模板加载与图像保存(load_template / save_image)
- 模板匹配接口 TemplateMatcher 与 OpenCV 实现

匹配算法为 TM_CCOEFF_NORMED(归一化相关系数);
常量图像会导致相关系数除零(NaN),已做防御处理。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

from game.screen import ScreenImage
from models.recognition import RecognitionResult

#: 默认匹配阈值
DEFAULT_THRESHOLD = 0.8


def image_to_array(image: ScreenImage) -> np.ndarray:
    """ScreenImage → numpy 数组;单通道为 (h, w),多通道为 (h, w, c)。"""
    array = np.frombuffer(image.data, dtype=np.uint8)
    if image.channels == 1:
        return array.reshape(image.height, image.width)
    return array.reshape(image.height, image.width, image.channels)


def array_to_image(array: np.ndarray, mode: str = "RGB") -> ScreenImage:
    """numpy 数组 → ScreenImage;接受 (h, w) 或 (h, w, c) 的 uint8 数组。"""
    if array.dtype != np.uint8:
        raise ValueError(f"数组 dtype 必须是 uint8,得到 {array.dtype}")
    if array.ndim == 2:
        height, width = array.shape
    elif array.ndim == 3:
        height, width, _ = array.shape
    else:
        raise ValueError(f"数组维度必须是 2 或 3,得到 {array.ndim}")
    return ScreenImage(width, height, mode, array.tobytes())


def load_template(path: Path | str) -> ScreenImage:
    """从图片文件加载模板,返回 RGB 格式的 ScreenImage。"""
    array = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if array is None:
        raise FileNotFoundError(f"模板图片无法读取: {path}")
    return array_to_image(array[:, :, ::-1], "RGB")  # BGR → RGB


def save_image(image: ScreenImage, path: Path | str) -> None:
    """把 ScreenImage 保存为 PNG(debug screenshot 用)。"""
    array = image_to_array(image)
    if image.mode in ("RGB", "RGBA"):
        array = array[:, :, ::-1]  # OpenCV 使用 BGR/BGRA 顺序
    elif image.mode not in ("BGR", "BGRA", "L"):
        raise ValueError(f"不支持的保存格式: {image.mode}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), array):
        raise OSError(f"图像写入失败: {path}")


class TemplateMatcher(ABC):
    """模板匹配接口。"""

    @abstractmethod
    def match(
        self, image: ScreenImage, template: ScreenImage, threshold: float = 0.8
    ) -> RecognitionResult:
        """在 image 中查找 template。

        Args:
            image: 待搜索图像。
            template: 模板图像。
            threshold: 置信度阈值,达到才算命中。

        Returns:
            命中时 value 为模板中心坐标 (x, y),未命中为 None。
        """


class OpenCVTemplateMatcher(TemplateMatcher):
    """基于 cv2.matchTemplate 的模板匹配实现。"""

    def match(
        self, image: ScreenImage, template: ScreenImage, threshold: float = 0.8
    ) -> RecognitionResult:
        if template.width > image.width or template.height > image.height:
            return RecognitionResult(
                success=False,
                detail=(
                    f"模板尺寸 ({template.width}x{template.height})"
                    f" 大于图像 ({image.width}x{image.height})"
                ),
            )
        if image.channels != template.channels:
            return RecognitionResult(
                success=False,
                detail=(
                    f"通道数不一致: image={image.channels},"
                    f" template={template.channels}"
                ),
            )
        image_array = image_to_array(image)
        template_array = image_to_array(template)
        result = cv2.matchTemplate(
            image_array, template_array, cv2.TM_CCOEFF_NORMED
        )
        # 常量图像会产生 NaN(除零),按 -1 处理后再截断
        result = np.nan_to_num(result, nan=-1.0)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        confidence = max(0.0, float(max_val))
        success = confidence >= threshold
        value = (
            (max_loc[0] + template.width // 2, max_loc[1] + template.height // 2)
            if success
            else None
        )
        return RecognitionResult(
            success=success,
            value=value,
            confidence=confidence,
            detail=None if success else (
                f"最高置信度 {confidence:.3f} 低于阈值 {threshold}"
            ),
        )
