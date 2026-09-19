"""Game Adapter 层:游戏适配器。

- adapter.py:GameAdapter 抽象接口(W2)
- mock_adapter.py:MockGameAdapter 行为模拟(W2)
- window.py / screen.py / input.py:窗口/截图/输入/热键基础能力接口与 Mock(W3)
- image_match.py:ScreenImage↔numpy 互转、模板加载/保存、OpenCV 模板匹配(W4)
- ocr.py:OcrEngine 抽象接口 + MockOcrEngine(W4)
- ocr_tesseract.py:TesseractOcrEngine 真实 OCR 引擎(W6)
- recognition.py:地图/坐标/死亡/自动战斗状态识别器(W4)
- templates/:模板图片目录(坐标需真实游戏实测)
- windows_adapter.py:WindowsGameAdapter 组合逻辑(平台无关,依赖注入,W5)
- windows_bindings.py:Windows 绑定(pywin32/MSS/PyAutoGUI/keyboard,仅 Windows,W5)
"""
