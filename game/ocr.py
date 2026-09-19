"""OCR 接口(W4)。

对应 DESIGN.md 第 3 节:OCR 引擎选 PaddleOCR 或 Tesseract,按实际兼容性选择。
W4 只定义接口与测试用 Mock;真实引擎在 W6 阶段接入(需 Windows 环境验证)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from game.screen import ScreenImage
from models.recognition import RecognitionResult


class OcrEngine(ABC):
    """OCR 引擎接口。"""

    @abstractmethod
    def recognize(self, image: ScreenImage) -> RecognitionResult:
        """识别图像中的文本;成功时 value 为识别文本(str)。"""


class MockOcrEngine(OcrEngine):
    """可脚本化 OCR:按顺序返回预设文本。

    供 W4 单元测试与 W5 之前的联调使用;
    ``script`` 消费完后返回失败结果(无可识别文本)。
    """

    def __init__(self, confidence: float = 1.0) -> None:
        self.script: list[str | None] = []
        self.confidence = confidence
        # 记录每次识别收到的图像尺寸 (width, height)
        self.calls: list[tuple[int, int]] = []

    def recognize(self, image: ScreenImage) -> RecognitionResult:
        self.calls.append((image.width, image.height))
        text = self.script.pop(0) if self.script else None
        if text is None:
            return RecognitionResult(success=False, detail="无可识别文本")
        return RecognitionResult(success=True, value=text, confidence=self.confidence)
