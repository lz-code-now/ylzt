# 御龙挂机助手

纯规则、配置驱动、状态机的 Windows 游戏挂机自动化脚本。

完整设计方案见 [DESIGN.md](DESIGN.md)。

## 当前阶段

**W9:Portable 发布(打包脚本已完成,Windows 真机验证待做)**

已包含:

- W0:项目基础结构、venv、`pyproject.toml` / requirements、logging、`main.py` 入口、基础测试
- W1:配置系统
  - `models/profile.py`:挂机方案数据模型(位置/寻路/战斗/复活/回城/恢复)
  - `models/settings.py`:应用设置数据模型
  - `app/bootstrap.py`:YAML 加载器(文件/语法/结构错误统一提示)
  - `utils/validation.py`:参数校验工具(字段路径 + 范围校验 + 未知字段提示)
  - `config/settings.yaml` 与 `config/profiles/default.yaml`
- W2:状态机
  - `models/state.py`:13 个状态定义(DESIGN 5.1),STOP/ERROR 为终态
  - `models/runtime.py`:RuntimeContext 运行时上下文(DESIGN 6.1)
  - `game/adapter.py`:GameAdapter 抽象接口,12 个方法(DESIGN 8)
  - `game/mock_adapter.py`:MockGameAdapter 可脚本化模拟(DESIGN 20.2)
  - `engine/state_machine.py`:状态机(转换表 DESIGN 5.2、复活逻辑 13.2、恢复 DESIGN 16、安全停止 DESIGN 17)
  - `engine/watchdog.py`:状态超时看门狗(DESIGN 15 超时表)
  - `engine/exceptions.py`:EngineError / StateTransitionError
  - 完整模拟验收:战斗 → 死亡×5(原地复活)→ 安全复活 → 回城 → 重新挂机
- W3:窗口/截图/输入层(接口与 Mock 已完成,真实 Windows 实现待 Windows 环境)
  - `game/window.py`:WindowManager 接口 + Mock(查找/激活/存活检查)
  - `game/screen.py`:ScreenCapture 接口 + ScreenImage 图像容器 + Mock
  - `game/input.py`:InputController / HotkeyManager 接口 + Mock(紧急停止热键)
  - 紧急停止链路已验证:F10 → request_stop → 停止战斗动作 → STOP
- W4:识别模块(DESIGN 9/10/13.1)
  - `models/region.py`:ROI 区域数据模型(DESIGN 9.2)
  - `models/recognition.py`:RecognitionResult(含 confidence / timestamp / debug 截图路径)
  - `game/image_match.py`:ScreenImage↔numpy 互转、模板加载/保存、OpenCV 模板匹配(TM_CCOEFF_NORMED,常量图像 NaN 防御)
  - `game/ocr.py`:OcrEngine 抽象接口 + MockOcrEngine(真实 OCR 引擎待 W6)
  - `game/recognition.py`:四大识别器——地图名 / 坐标(DESIGN 10 容差输入)/ 死亡对话框 / 自动战斗状态,均支持 ROI 裁剪与失败时 debug 截图
  - `game/templates/`:模板图片目录(占位,坐标与模板需真实游戏实测)
  - `config/settings.yaml` 新增 `game.regions` 四个 ROI(占位坐标)
- W5:真实 GameAdapter(DESIGN 21-W5)
  - `game/windows_adapter.py`:WindowsGameAdapter 组合逻辑——窗口/截图/识别/输入编排,依赖注入,平台无关,macOS 可完整测试
  - `game/windows_bindings.py`:Windows 绑定(Win32WindowManager / MssScreenCapture / PyAutoGuiInput / KeyboardHotkeyManager),延迟导入,仅 Windows 可实例化
  - `models/settings.py` 新增 `ActionBindings`(`game.actions`):快捷键/点击坐标/小地图换算配置驱动,动作优先使用游戏自身 UI/快捷键
  - 12 个 GameAdapter 方法全部实现;窗口丢失时动作 no-op + 警告,由状态机 RECOVER 链路兜底
  - 与状态机联调验证:CHECK_MAP → NAVIGATE(OCR 坐标到达)→ START_COMBAT(模板命中)→ COMBAT
- W6:真实挂机闭环(DESIGN 21-W6,第一个 MVP)
  - `game/ocr_tesseract.py`:TesseractOcrEngine——真实 OCR 引擎(灰度→放大→OTSU 二值化→反色预处理;置信度阈值;引擎级失败转失败结果不中断循环)
  - `models/settings.py` 新增 `OcrSection`(`game.ocr`):engine(mock/tesseract)/ tesseract_cmd / lang / psm / min_confidence
  - `app/runner.py`:RuntimeRunner 组装器——配置→OCR→适配器→状态机→热键→主循环;mock 模式任何平台可运行,real 模式 Windows 真机运行
  - `main.py` 升级为闭环入口:默认 mock 演示(完整死亡复活回城剧本),`--real` 真实模式,`--profile` 指定方案
  - F10 紧急停止热键 + Ctrl+C 安全停止(DESIGN 17)
  - 全闭环验收(mock):挂机 → 死亡×6 → 5 次原地复活 → 安全复活 → 回城 → 再挂机 ✓
- W7:GUI(DESIGN 18)
  - `app/gui_state.py`:纯逻辑桥接层——AppState 不可变快照、GuiBridge 线程安全读写、GuiLogHandler 有界日志队列(headless 可测)
  - `app/gui.py`:tkinter 主窗口——方案下拉、状态/坐标/复活次数/回城/异常/运行时长、开始/停止按钮、滚动日志区
  - 线程模型:tkinter 主线程 200ms 轮询快照刷新;worker 线程跑 RuntimeRunner,互不阻塞
  - 停止按钮走状态机安全停止链路(DESIGN 17 UI 停止层);关窗自动触发停止
  - 暂停/恢复按钮(W8 起接入 PAUSED 状态)
  - 技术选型:tkinter 标准库(零新增依赖);`--gui` 启动
- W8:异常恢复(DESIGN 15/16/17)
  - `engine/resilience.py`:StuckDetector 卡住检测(间隔采样+位移阈值)、FailureTracker 连续失败计数、RecoveryJournal 恢复事件五要素(时间/状态/原因/截图/重试)
  - 状态机新增 **PAUSED 暂停状态**(pause/resume;恢复走 CHECK_GAME 重新确认游戏)
  - NAVIGATE 卡住检测(未超时但位置不动也进 RECOVER);识别失败改为**连续失败计数**,达到阈值触发**自动安全停止**(DESIGN 17)
  - RECOVER 记录恢复事件并自动保存现场截图(`runtime.debug_dir`,数量上限防磁盘膨胀)
  - `GameAdapter.capture_screenshot()` 恢复现场截图能力(Windows 适配器已实现)
  - GUI 暂停/恢复按钮启用;F8 暂停 / F9 恢复热键接入 runner
  - 配置新增:`runtime.stuck_check_interval_seconds / stuck_min_distance / max_consecutive_failures / max_recovery_screenshot / debug_dir`
- W9:Portable 发布(DESIGN 21-W9)
  - `ylzt.spec`:PyInstaller onedir 配置(Windows 绑定隐藏导入;保留控制台;排除无关大模块)
  - `scripts/build.py`:一键打包脚本——环境检查 → 全量测试 → 清理 → 构建 → 复制外置资源(config/profiles/templates)→ 写部署说明 → 产物冒烟
  - 资源策略:config/ 与 game/templates/ **外置**于产物目录(用户可编辑配置、可实测替换模板),`app/bootstrap.py` 兼容源码/onedir/onefile 三种运行形态
  - macOS 验证:产物完整跑通 mock 演示闭环;159MB(含 OpenCV/numpy)
  - Windows 真机部署:整个 `dist/ylzt/` 复制过去,装 Tesseract + 中文包后按 `使用说明.txt` 配置 `game.ocr.engine=tesseract`,管理员运行 `ylzt.exe --real`

尚未实现:

- Windows 真机验证:regions/templates/actions 标定、`--real` 真实闭环、打包产物真机运行

## 环境要求

- Python >= 3.11(需含 tkinter;Homebrew 安装:`brew install python-tk@3.12`)
- 运行依赖:PyYAML、opencv-python、pytesseract、Pillow
- 系统依赖:Tesseract OCR(OCR 真实引擎;macOS `brew install tesseract tesseract-lang`,Windows 安装后配置 `game.ocr.tesseract_cmd`)
- 开发测试:pytest

## 快速开始

```bash
# 创建虚拟环境(如尚未创建)
python3 -m venv .venv

# 安装运行依赖与开发依赖
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# (仅 Windows 真机)安装游戏自动化依赖组
# .venv/bin/pip install -e .[windows]

# 运行程序(命令行演示:完整死亡复活回城闭环)
.venv/bin/python main.py

# 启动图形界面(方案选择/状态/开始/停止/日志)
.venv/bin/python main.py --gui

# 运行测试
.venv/bin/pytest
```

## 项目结构

```text
ylzt/
├── main.py                 # 程序入口
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── app/                    # 应用层:常量、启动引导(配置加载)
├── engine/                 # Engine 层:状态机、看门狗(W2)
├── behaviors/              # Behavior 层:寻路/战斗/复活等(后续阶段)
├── game/                   # Game Adapter 层:接口 + Mock(W2/W3);识别(W4);真实适配器(W5)
├── models/                 # Models 层:Profile、Settings(W1);State、Runtime(W2);Region、Recognition(W4)
├── utils/                  # Utils 层:日志、校验
├── ui/                     # UI 层:PySide6 GUI(W7)
├── config/                 # 配置:settings.yaml + profiles/default.yaml
├── tests/                  # pytest 测试
└── logs/                   # 运行日志(app.log / error.log)
```

## 开发规则

- 每次只做一个阶段(W0~W9),完成后验收再进入下一阶段
- 每阶段结束运行 `pytest` 并检查 `git diff --check`
- 严禁范围漂移,详见 DESIGN.md 第 24、26 节
