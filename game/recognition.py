"""识别器:地图 / 坐标 / 死亡 / 自动战斗状态(W4)。

对应 DESIGN.md 9.1 节识别优先级的后两层:
固定 UI 区域(ROI 裁剪)→ 模板匹配 / OCR。
所有识别器统一返回 RecognitionResult
(success / value / confidence / timestamp / debug screenshot)。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from game.image_match import TemplateMatcher, save_image
from game.ocr import OcrEngine
from game.screen import ScreenImage, crop
from models.recognition import RecognitionResult
from models.region import Region

# 坐标文本:支持括号、空格、全角/半角逗号,如 "(123, 456)"、"123,456"
_POSITION_PATTERN = re.compile(r"(\d+)\s*[,，]\s*(\d+)")


def parse_position(text: str | None) -> tuple[int, int] | None:
    """从 OCR 文本解析坐标;无法解析返回 None。"""
    if not text:
        return None
    match = _POSITION_PATTERN.search(text)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


class BaseRecognizer:
    """识别器基类:ROI 裁剪与调试截图。"""

    def __init__(
        self,
        region: Region | None = None,
        debug_dir: Path | str | None = None,
    ) -> None:
        self.region = region
        self.debug_dir = Path(debug_dir) if debug_dir else None

    def _prepare(self, image: ScreenImage) -> ScreenImage:
        """按配置的 ROI 裁剪;未配置时返回原图。"""
        if self.region is None:
            return image
        return crop(
            image, self.region.x, self.region.y, self.region.width, self.region.height
        )

    def _save_debug(self, image: ScreenImage, tag: str) -> str | None:
        """保存调试截图并返回路径;未配置调试目录时返回 None。"""
        if self.debug_dir is None:
            return None
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{tag}.png"
        save_image(image, path)
        return str(path)


class MapRecognizer(BaseRecognizer):
    """地图名识别:ROI + OCR。"""

    def __init__(
        self,
        ocr: OcrEngine,
        region: Region | None = None,
        debug_dir: Path | str | None = None,
    ) -> None:
        super().__init__(region=region, debug_dir=debug_dir)
        self.ocr = ocr

    def recognize(self, image: ScreenImage) -> RecognitionResult:
        roi = self._prepare(image)
        result = self.ocr.recognize(roi)
        if not result.success:
            debug_path = self._save_debug(roi, "map")
            return RecognitionResult(
                success=False,
                confidence=result.confidence,
                debug_screenshot_path=debug_path,
                detail=result.detail,
            )
        value = str(result.value).strip()
        return RecognitionResult(
            success=True,
            value=value,
            confidence=result.confidence,
        )


class PositionRecognizer(BaseRecognizer):
    """坐标识别:ROI + OCR + 文本解析(DESIGN 第 10 节的坐标来源)。"""

    def __init__(
        self,
        ocr: OcrEngine,
        region: Region | None = None,
        debug_dir: Path | str | None = None,
    ) -> None:
        super().__init__(region=region, debug_dir=debug_dir)
        self.ocr = ocr

    def recognize(self, image: ScreenImage) -> RecognitionResult:
        roi = self._prepare(image)
        ocr_result = self.ocr.recognize(roi)
        position = parse_position(ocr_result.value) if ocr_result.success else None
        if position is None:
            debug_path = self._save_debug(roi, "position")
            return RecognitionResult(
                success=False,
                confidence=ocr_result.confidence,
                debug_screenshot_path=debug_path,
                detail=f"无法从 OCR 文本解析坐标: {ocr_result.value!r}",
            )
        return RecognitionResult(
            success=True,
            value=position,
            confidence=ocr_result.confidence,
        )


class _TemplateRecognizer(BaseRecognizer):
    """模板识别器基类:ROI + 模板匹配。"""

    #: 调试截图文件名标签
    tag = "template"

    def __init__(
        self,
        matcher: TemplateMatcher,
        template: ScreenImage | None,
        threshold: float = 0.8,
        region: Region | None = None,
        debug_dir: Path | str | None = None,
    ) -> None:
        super().__init__(region=region, debug_dir=debug_dir)
        self.matcher = matcher
        self.template = template
        self.threshold = threshold

    def recognize(self, image: ScreenImage) -> RecognitionResult:
        if self.template is None:
            return RecognitionResult(
                success=False,
                detail="模板未就绪(文件缺失或无法读取)",
            )
        roi = self._prepare(image)
        match = self.matcher.match(roi, self.template, self.threshold)
        debug_path = self._save_debug(roi, self.tag) if not match.success else None
        return RecognitionResult(
            success=match.success,
            value=match.success,
            confidence=match.confidence,
            debug_screenshot_path=debug_path,
            detail=match.detail,
        )


class DeathRecognizer(_TemplateRecognizer):
    """死亡识别(DESIGN 13.1:匹配死亡 UI/复活按钮模板,避免单像素判断)。

    value 为 True 表示已死亡。
    """

    tag = "death"


class CombatStateRecognizer(_TemplateRecognizer):
    """自动战斗状态识别:匹配"已开启"状态图标模板。

    value 为 True 表示自动战斗已开启。
    """

    tag = "combat"
