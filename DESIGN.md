# 御龙挂机助手：纯规则 Windows 自动化脚本完整设计方案与实现计划

> 文档版本：v0.1  
> 目标：使用 Trae Work / Coding Agent 进行分阶段开发  
> 平台：Windows 10/11 x64  
> 核心原则：纯规则、配置驱动、状态机；不使用 AI/大模型，不读取或修改游戏进程内存，不注入客户端，不绕过反作弊机制。

---

## 1. 项目目标

开发一个 Windows 绿色版桌面程序，用于执行用户预先配置的、固定规则的游戏自动化流程。

第一阶段的核心闭环：

```text
启动程序
  ↓
检测游戏窗口
  ↓
读取挂机方案
  ↓
确认当前地图/状态
  ↓
前往指定挂机坐标
  ↓
开启游戏内自动战斗
  ↓
持续监控
  ↓
检测死亡
  ↓
原地复活次数 < 上限？
  ├─ 是 → 原地复活 → 回到挂机点
  └─ 否 → 安全复活 → 回城
                       ↓
                    重新寻路
                       ↓
                    开启自动战斗
                       ↓
                     循环
```

### 1.1 非目标

本项目第一阶段不做：

- AI Agent
- 大模型决策
- 自动理解复杂战场
- 游戏进程注入
- 内存读写
- DLL 注入
- 反作弊绕过
- 隐藏脚本进程/规避检测
- 修改游戏客户端
- 自动 PVP 决策
- 复杂国战策略

如果游戏或运营方禁止第三方自动化，应以其规则为准；开发时优先使用游戏自身提供的自动战斗、自动寻路、快捷键等能力。

---

# 2. 总体架构

```text
┌──────────────────────────────────────────┐
│                 Windows GUI              │
│                  PySide6                 │
│                                          │
│  挂机方案 / 状态 / 日志 / 开始 / 停止     │
└───────────────────┬──────────────────────┘
                    │
┌───────────────────▼──────────────────────┐
│              Script Engine               │
│                                          │
│              State Machine               │
│                                          │
│ INIT → CHECK_GAME → CHECK_MAP            │
│       → NAVIGATE → START_COMBAT          │
│       → COMBAT → DEAD                    │
│       → REVIVE / RETURN_HOME             │
│       → RECOVER → ...                    │
└───────────────────┬──────────────────────┘
                    │
┌───────────────────▼──────────────────────┐
│               Game Adapter               │
│                                          │
│ Screen / OCR / Image Recognition         │
│ Mouse / Keyboard / Window                │
└───────────────────┬──────────────────────┘
                    │
                    ▼
              游戏客户端
```

## 2.1 分层原则

### UI 层

只负责：

- 显示配置
- 显示状态
- 接收开始/暂停/停止
- 显示日志
- 修改挂机方案

不得直接操作鼠标或游戏。

### Engine 层

负责：

- 状态机
- 状态切换
- 超时
- 重试
- 运行计数
- 停止机制

### Behavior 层

负责：

- 寻路
- 自动战斗
- 死亡处理
- 回城
- 恢复

### Game Adapter 层

负责：

- 截图
- OCR
- 图像模板匹配
- 鼠标
- 键盘
- 游戏窗口检测

### Config 层

负责：

- YAML 配置
- 挂机方案
- 默认值
- 参数校验

---

# 3. 推荐技术栈

| 模块 | 技术 |
|---|---|
| 语言 | Python 3.11 |
| GUI | PySide6 |
| 虚拟环境 | venv |
| 鼠标键盘 | PyAutoGUI |
| 截图 | MSS |
| 图像识别 | OpenCV |
| OCR | PaddleOCR 或 Tesseract，按实际兼容性选择 |
| 配置 | PyYAML |
| 日志 | logging |
| 热键 | keyboard 或 Qt 全局热键方案 |
| 打包 | PyInstaller |
| 发布 | Portable ZIP |
| 测试 | pytest |

原则：

> 开发阶段 Python + venv；发布阶段 PyInstaller + onedir Portable。

---

# 4. 项目目录

建议最终目录：

```text
game-bot/
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── pyproject.toml
│
├── app/
│   ├── __init__.py
│   ├── bootstrap.py
│   └── constants.py
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── widgets/
│   │   ├── status_panel.py
│   │   ├── profile_panel.py
│   │   └── log_panel.py
│   └── resources/
│
├── engine/
│   ├── __init__.py
│   ├── state_machine.py
│   ├── states.py
│   ├── context.py
│   ├── scheduler.py
│   ├── watchdog.py
│   └── exceptions.py
│
├── behaviors/
│   ├── __init__.py
│   ├── navigation.py
│   ├── combat.py
│   ├── death.py
│   ├── revive.py
│   ├── return_home.py
│   └── recovery.py
│
├── game/
│   ├── __init__.py
│   ├── adapter.py
│   ├── window.py
│   ├── screen.py
│   ├── input.py
│   ├── image_match.py
│   ├── ocr.py
│   └── templates/
│       ├── README.md
│       └── .gitkeep
│
├── config/
│   ├── settings.yaml
│   └── profiles/
│       └── default.yaml
│
├── models/
│   ├── __init__.py
│   ├── state.py
│   ├── runtime.py
│   └── profile.py
│
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── timing.py
│   └── validation.py
│
├── tests/
│   ├── test_state_machine.py
│   ├── test_profile.py
│   ├── test_runtime.py
│   └── test_navigation.py
│
├── assets/
│   └── icons/
│
├── logs/
│
└── build/
```

---

# 5. 状态机设计

## 5.1 状态定义

```text
INIT
CHECK_GAME
CHECK_MAP
NAVIGATE
START_COMBAT
COMBAT
DEAD
LOCAL_REVIVE
SAFE_REVIVE
RETURN_HOME
RECOVER
STOP
ERROR
```

## 5.2 状态转换

```text
INIT
 ↓
CHECK_GAME
 ├─ 游戏不存在 → ERROR/等待
 └─ 游戏正常
      ↓
CHECK_MAP
 ├─ 地图正确 → NAVIGATE
 └─ 地图错误 → NAVIGATE

NAVIGATE
 ├─ 到达 → START_COMBAT
 ├─ 超时 → RECOVER
 └─ 停止 → STOP

START_COMBAT
 ├─ 成功 → COMBAT
 ├─ 重试失败 → RECOVER
 └─ 停止 → STOP

COMBAT
 ├─ 死亡 → DEAD
 ├─ 异常 → RECOVER
 └─ 正常 → COMBAT

DEAD
 ↓
判断 local_revive_count
 ├─ < max → LOCAL_REVIVE
 └─ >= max → SAFE_REVIVE

LOCAL_REVIVE
 ├─ 成功 → NAVIGATE
 └─ 失败 → RECOVER

SAFE_REVIVE
 ├─ 成功 → RETURN_HOME
 └─ 失败 → RECOVER

RETURN_HOME
 ├─ 成功 → NAVIGATE
 └─ 超时 → RECOVER

RECOVER
 ├─ 恢复成功 → CHECK_GAME
 ├─ 重试耗尽 → ERROR
 └─ STOP → STOP
```

---

# 6. Runtime Context

运行时上下文必须集中保存，不要散落在各个模块。

示例：

```python
RuntimeContext(
    state=State.COMBAT,
    map_name="目标地图",
    current_x=123,
    current_y=456,
    target_x=123,
    target_y=456,
    local_revive_count=2,
    return_count=1,
    error_count=0,
    started_at=...,
    last_state_change_at=...,
)
```

## 6.1 必须记录

- 当前状态
- 当前地图
- 当前坐标（如果可从允许的 UI 信息获得）
- 目标坐标
- 原地复活次数
- 回城次数
- 错误次数
- 当前状态开始时间
- 最后一次成功动作
- 最近一次死亡时间

---

# 7. 配置设计

## 7.1 settings.yaml

```yaml
app:
  language: zh-CN
  startup_delay_seconds: 5
  emergency_stop_key: F10
  pause_key: F8
  resume_key: F9

game:
  window_title_contains: "御龙在天"

runtime:
  default_state_timeout_seconds: 120
  max_retries: 3
  loop_enabled: true

logging:
  level: INFO
  file_enabled: true
```

## 7.2 挂机方案

`config/profiles/default.yaml`

```yaml
name: "默认挂机点"

location:
  map: "目标地图"
  x: 123
  y: 456
  tolerance: 10

navigation:
  enabled: true
  timeout_seconds: 180
  retry_count: 3

combat:
  enabled: true
  auto_start: true
  start_retry_count: 3

revive:
  enabled: true
  max_local_revive: 5
  local_revive_wait_seconds: 3
  safe_revive_wait_seconds: 5

return_home:
  enabled: true
  wait_after_return_seconds: 5

recovery:
  enabled: true
  max_recovery_count: 3
```

---

# 8. Game Adapter 接口

核心接口建议：

```python
class GameAdapter:

    def is_game_running(self) -> bool:
        ...

    def activate_game(self) -> None:
        ...

    def get_current_map(self) -> str | None:
        ...

    def get_position(self) -> tuple[int, int] | None:
        ...

    def is_dead(self) -> bool:
        ...

    def is_auto_combat_enabled(self) -> bool:
        ...

    def navigate_to(self, x: int, y: int) -> None:
        ...

    def start_auto_combat(self) -> None:
        ...

    def local_revive(self) -> None:
        ...

    def safe_revive(self) -> None:
        ...

    def return_home(self) -> None:
        ...

    def stop_combat(self) -> None:
        ...
```

业务逻辑只能依赖这个接口。

---

# 9. 屏幕识别设计

## 9.1 识别优先级

优先级：

```text
游戏内现有 UI / 快捷键
        ↓
固定 UI 区域
        ↓
模板匹配
        ↓
OCR
```

不要一开始就使用复杂视觉算法。

## 9.2 Region of Interest

不要每次扫描整个屏幕。

配置识别区域：

```yaml
regions:
  map_name:
    x: 0
    y: 0
    width: 300
    height: 100

  position:
    x: 0
    y: 0
    width: 300
    height: 150

  death_dialog:
    x: 500
    y: 300
    width: 500
    height: 300

  combat_button:
    x: 1000
    y: 600
    width: 300
    height: 200
```

实际坐标必须通过测试工具确定，不能凭空写死。

---

# 10. 坐标判断

目标：

```text
X = 123
Y = 456
```

容差：

```text
10
```

距离：

```text
distance = sqrt(
    (current_x - target_x)^2 +
    (current_y - target_y)^2
)
```

如果：

```text
distance <= tolerance
```

则：

```text
ARRIVED
```

必须允许一定误差，避免角色已经到达但脚本无限寻路。

---

# 11. 导航 Behavior

逻辑：

```text
NAVIGATE
 ↓
检查地图
 ↓
地图不正确
    ↓
执行游戏允许的地图/寻路操作
 ↓
检查坐标
 ↓
到达？
 ├─ YES → START_COMBAT
 └─ NO → 等待
```

超时：

```text
NAVIGATE > 180 秒
 ↓
停止当前导航
 ↓
重新执行导航
 ↓
达到 retry_count
 ↓
RECOVER
```

---

# 12. 自动战斗 Behavior

原则：

> 脚本只负责触发游戏已有的自动战斗，不自行实现战斗算法。

流程：

```text
START_COMBAT
 ↓
检测是否已经开启
 ├─ YES → COMBAT
 └─ NO
      ↓
    点击/快捷键
      ↓
    等待
      ↓
    再次检测
      ↓
    成功 → COMBAT
    失败 → 重试
```

避免：

```text
无限点击自动战斗按钮
```

---

# 13. 死亡处理

## 13.1 判断死亡

优先：

- 游戏明确的死亡 UI
- 复活按钮
- 游戏状态提示

避免只通过单个像素判断。

## 13.2 复活逻辑

```python
if local_revive_count < max_local_revive:
    local_revive()
    local_revive_count += 1
    state = NAVIGATE
else:
    safe_revive()
    local_revive_count = 0
    state = RETURN_HOME
```

重要：

> 计数器只有在确认复活成功后才增加。

---

# 14. 回城逻辑

```text
SAFE_REVIVE
 ↓
确认复活
 ↓
RETURN_HOME
 ↓
执行游戏允许的回城动作
 ↓
确认回城完成
 ↓
清理临时状态
 ↓
NAVIGATE
```

回城成功的判断必须通过：

- 地图名称
- UI 状态
- 坐标变化
- 游戏明确提示

中的一种或组合确认。

---

# 15. Watchdog

每个状态设置超时：

```yaml
timeout:
  check_game: 10
  check_map: 10
  navigate: 180
  start_combat: 10
  combat: 0
  local_revive: 20
  safe_revive: 20
  return_home: 60
```

`combat: 0` 表示没有固定超时，但仍需定期健康检查。

Watchdog 负责：

```text
状态开始
 ↓
记录 timestamp
 ↓
定期检查
 ↓
超过 timeout
 ↓
RECOVER
```

---

# 16. Recovery 设计

恢复策略必须有限，不允许无限重试。

```text
异常
 ↓
保存截图
 ↓
写日志
 ↓
停止当前动作
 ↓
等待
 ↓
重新检查游戏
 ↓
恢复成功 → CHECK_GAME
恢复失败 → retry + 1
 ↓
超过上限 → ERROR
```

每次恢复应该产生：

- 时间
- 当前状态
- 错误原因
- 截图文件
- 重试次数

---

# 17. 安全停止

必须实现三个层级：

### UI 停止

点击：

```text
[停止]
```

### 快捷键

例如：

```text
F10
```

### 自动安全停止

例如：

- 游戏窗口消失
- 无法确认游戏状态
- 连续异常达到阈值
- 关键操作连续失败
- 状态机进入 ERROR

停止后：

```text
停止所有脚本动作
↓
释放热键/鼠标状态
↓
记录日志
↓
状态 = STOP
```

不要在停止时强制关闭游戏客户端。

---

# 18. GUI 设计

建议使用 PySide6。

主窗口：

```text
┌──────────────────────────────────────────┐
│             御龙挂机助手                  │
├──────────────────────────────────────────┤
│ 挂机方案： [ 默认挂机点 ▼ ]              │
│                                          │
│ 地图：     目标地图                       │
│ 目标坐标： 123 , 456                      │
│                                          │
│ 最大原地复活： [ 5 ]                     │
│                                          │
│ 状态： 🟢 挂机战斗中                      │
│ 当前坐标：123 , 458                       │
│ 复活次数：2 / 5                           │
│ 运行时间：02:31:42                        │
│                                          │
│ [▶ 开始] [⏸ 暂停] [■ 停止]              │
├──────────────────────────────────────────┤
│ 运行日志                                  │
│ 16:41 到达挂机点                          │
│ 16:41 自动战斗开启                        │
│ 17:02 检测到死亡                          │
│ 17:02 原地复活 1/5                        │
└──────────────────────────────────────────┘
```

GUI 不允许阻塞状态机。

推荐：

```text
Qt 主线程
    ↓
Worker Thread
    ↓
Script Engine
```

通过 Qt Signal 更新 UI。

---

# 19. 日志

格式：

```text
[2026-09-18 16:41:02] [INFO] Script started
[2026-09-18 16:41:04] [INFO] Game window detected
[2026-09-18 16:41:05] [INFO] Current map: XXX
[2026-09-18 16:41:06] [INFO] Navigating to 123,456
[2026-09-18 16:42:10] [INFO] Target reached
[2026-09-18 16:42:12] [INFO] Auto combat enabled
[2026-09-18 17:02:31] [WARN] Player dead
[2026-09-18 17:02:34] [INFO] Local revive 1/5
```

同时保存：

```text
logs/
├── app.log
├── error.log
└── screenshots/
```

异常截图：

```text
screenshots/
└── 20260918_170231_dead.png
```

---

# 20. 测试策略

## 20.1 单元测试

必须测试：

- 配置加载
- 配置校验
- 状态转换
- 复活计数
- 达到复活上限后的行为
- 超时
- 重试
- STOP
- ERROR

重点测试：

```text
复活次数 0
复活次数 4
复活次数 5
复活次数 > 5
```

## 20.2 Mock GameAdapter

不要每次测试都启动真实游戏。

提供：

```python
MockGameAdapter
```

模拟：

```text
正常
死亡
复活成功
复活失败
导航成功
导航超时
游戏关闭
```

这样可以先把状态机完全跑通。

## 20.3 集成测试

最后才接真实游戏：

```text
游戏窗口
 ↓
GameAdapter
 ↓
真实截图
 ↓
真实识别
 ↓
真实操作
```

---

# 21. 开发顺序

不要让 Trae Work 一次性实现整个项目。

必须分阶段。

## W0：项目初始化

目标：

- 创建目录
- Python venv
- pyproject.toml
- requirements
- logging
- README
- 基础测试

验收：

```text
python main.py
pytest
```

均正常。

---

## W1：配置系统

实现：

- Profile 模型
- YAML 加载
- 默认配置
- 配置校验
- 配置错误提示

验收：

```text
读取 default.yaml
得到：
map
x
y
tolerance
max_local_revive
```

---

## W2：状态机

实现：

- State
- RuntimeContext
- StateMachine
- 状态转换
- STOP
- ERROR
- Watchdog

先使用 MockGameAdapter。

验收：

完整模拟：

```text
INIT
→ CHECK_GAME
→ NAVIGATE
→ START_COMBAT
→ COMBAT
→ DEAD
→ LOCAL_REVIVE
→ NAVIGATE
→ ...
→ 第5次死亡
→ SAFE_REVIVE
→ RETURN_HOME
→ NAVIGATE
```

---

## W3：Windows 游戏窗口层

实现：

- 查找目标窗口
- 激活窗口
- 截图
- 输入控制
- 安全停止

只做基础能力，不实现复杂识别。

验收：

能够：

- 找到游戏窗口
- 截取窗口
- 执行一个测试按键/点击
- 紧急停止

---

## W4：识别模块

实现：

- ROI 截图
- 模板匹配
- OCR 接口
- 地图识别
- 坐标识别
- 死亡识别
- 自动战斗状态识别

要求：

所有识别模块都有：

```text
confidence
timestamp
debug screenshot
```

不要返回简单 bool 后无法排查。

---

## W5：真实 GameAdapter

把：

```text
MockGameAdapter
```

替换为：

```text
WindowsGameAdapter
```

实现：

- `is_game_running`
- `get_current_map`
- `get_position`
- `is_dead`
- `is_auto_combat_enabled`
- `navigate_to`
- `start_auto_combat`
- `local_revive`
- `safe_revive`
- `return_home`

所有动作优先使用游戏自身提供的正常 UI/快捷键能力。

---

## W6：真实挂机闭环

完成：

```text
指定挂机点
→ 到达
→ 自动战斗
→ 死亡
→ 原地复活
→ 重新挂机
→ 达到上限
→ 安全复活
→ 回城
→ 再挂机
```

这是第一个真正 MVP。

---

## W7：GUI

实现：

- 主窗口
- Profile 下拉框
- 状态
- 坐标
- 复活次数
- 运行时间
- 开始
- 暂停
- 停止
- 日志

---

## W8：异常恢复

增加：

- 导航卡住
- 自动战斗启动失败
- 识别失败
- 游戏窗口丢失
- 状态超时
- 连续失败
- 自动截图
- Recovery

---

## W9：Portable 发布

使用 PyInstaller：

```text
PyInstaller
 ↓
onedir
 ↓
收集 DLL / OCR / templates
 ↓
生成 dist
 ↓
测试纯净 Windows
```

最终：

```text
御龙挂机助手/
├── 御龙挂机助手.exe
├── _internal/
├── config/
├── assets/
├── logs/
└── README.txt
```

压缩：

```text
御龙挂机助手_v1.0.0_Windows_x64.zip
```

---

# 22. PyInstaller 发布方案

推荐：

```text
--onedir
--windowed
```

不要第一版使用：

```text
--onefile
```

原因：

- 启动速度
- OCR 资源
- OpenCV DLL
- 模板文件
- 调试困难

发布时必须测试：

1. 无 Python 环境
2. 无 pip
3. 无开发环境
4. 全新 Windows 用户目录
5. 中文路径
6. 无管理员权限场景（如果依赖不要求）
7. 游戏窗口存在/不存在
8. 程序启动/停止

---

# 23. Portable 数据目录

不要把用户运行数据写入：

```text
C:\Program Files
```

Portable 模式建议：

```text
程序目录/
├── config/
├── logs/
├── data/
└── assets/
```

首次启动自动创建：

```text
config/
logs/
data/
```

---

# 24. Trae Work 开发规则

让 Trae Work 严格遵守：

### 每次只做一个阶段

不要一次性：

```text
“帮我把整个挂机助手全部写完”
```

而应该：

```text
W0
↓
验收
↓
W1
↓
验收
↓
W2
...
```

### 每个阶段结束必须：

```text
1. 运行测试
2. 检查 git diff
3. 检查 git diff --check
4. 更新 README / CHANGELOG
5. 总结修改文件
6. 总结测试结果
7. 不提前实现后续阶段
```

### 严禁范围漂移

例如 W2 状态机阶段：

不要提前实现：

- OCR
- OpenCV
- PyAutoGUI
- 游戏操作
- GUI
- PyInstaller

先用 Mock。

---

# 25. Trae Work 首个任务提示词

建议给 Trae Work：

```text
你现在接手“御龙挂机助手”项目。

请完整阅读项目根目录的 DESIGN.md。

当前只执行 W0：项目初始化。

目标：
1. 创建 Python 3.11 项目基础结构。
2. 创建 pyproject.toml。
3. 创建 requirements.txt 和 requirements-dev.txt。
4. 创建 app、engine、behaviors、game、models、utils、ui、tests 等目录。
5. 建立 logging 基础能力。
6. 创建 main.py，程序可以正常启动并输出版本信息。
7. 创建基础 pytest 测试。
8. 创建 README.md。
9. 创建 .gitignore。
10. 不实现游戏操作、不实现 OCR、不实现 OpenCV、不实现状态机、不实现 GUI。

严格要求：
- 只执行 W0。
- 不修改 W1 及后续功能。
- 所有代码保持可运行。
- 完成后执行 pytest。
- 执行 git diff --check。
- 最后汇报：
  1. 修改了哪些文件
  2. 做了什么
  3. 测试结果
  4. 是否存在问题
  5. 下一阶段建议

不要自行扩大任务范围。
```

---

# 26. 后续 Trae Work 任务模板

每次：

```text
你现在继续开发“御龙挂机助手”。

请阅读：
- DESIGN.md
- README.md
- 当前项目代码
- 当前 git status
- 最近的开发记录

当前任务：
W[X]

严格只执行 W[X]。

执行前：
1. 检查当前代码状态。
2. 阅读本阶段涉及的现有代码。
3. 明确本阶段验收标准。

执行中：
- 不实现后续阶段。
- 不修改无关模块。
- 保持现有功能正常。
- 所有新增逻辑必须可测试。

执行后：
1. 运行 pytest。
2. 执行 git diff --check。
3. 检查 git status。
4. 更新必要的文档。
5. 输出修改文件列表。
6. 输出测试结果。
7. 输出未完成事项。
8. 明确是否达到本阶段验收标准。
```

---

# 27. MVP 验收标准

V0.1 必须完整跑通：

```text
启动
 ↓
检测游戏
 ↓
读取配置
 ↓
到指定挂机点
 ↓
开启自动战斗
 ↓
检测死亡
 ↓
原地复活
 ↓
复活次数 +1
 ↓
重新挂机
 ↓
再次死亡
 ↓
...
 ↓
达到最大原地复活次数
 ↓
安全复活
 ↓
回城
 ↓
重新前往挂机点
 ↓
重新开启自动战斗
 ↓
进入下一轮
```

同时：

```text
F10
 ↓
立即停止脚本动作
```

必须可靠。

---

# 28. 最终产品形态

最终发布包：

```text
御龙挂机助手_v1.0.0_Windows_x64.zip
```

解压：

```text
御龙挂机助手/
│
├── 御龙挂机助手.exe       ← 用户唯一需要操作的入口
│
├── _internal/
├── config/
│   ├── settings.yaml
│   └── profiles/
│       ├── default.yaml
│       └── ...
│
├── assets/
│   └── templates/
│
├── data/
│
├── logs/
│
└── README.txt
```

用户：

```text
下载 ZIP
 ↓
解压
 ↓
双击 御龙挂机助手.exe
 ↓
选择挂机方案
 ↓
开始
```

不要求：

- Python
- pip
- venv
- IDE
- 命令行
- 手动安装依赖

---

# 29. 后续扩展路线

MVP 稳定后再考虑：

```text
V1.1
├── 多挂机点
├── HP/MP 补给
├── 背包检测
└── 装备耐久检测

V1.2
├── 回城补给
├── 自动卖物
└── 多方案定时调度

V1.3
├── 日常任务状态机
├── 固定规则任务链
└── 任务失败恢复

V2.0
├── 多任务调度
├── 更完善的异常恢复
└── 运行统计
```

所有扩展仍保持：

> 配置驱动 + 规则驱动 + 状态机。

---

# 30. 开发原则总结

1. **先状态机，后真实游戏。**
2. **先 Mock，后真实客户端。**
3. **先 MVP，后复杂功能。**
4. **所有游戏动作通过 GameAdapter 隔离。**
5. **所有参数配置化。**
6. **所有状态都有超时和恢复策略。**
7. **所有关键动作必须可停止。**
8. **所有异常必须记录日志并尽量保存截图。**
9. **不要依赖固定绝对屏幕坐标作为唯一识别方式。**
10. **不读取/修改游戏进程，不注入，不绕过反作弊。**
11. **GUI 与脚本引擎分离。**
12. **开发阶段 Python，发布阶段 PyInstaller Portable。**
13. **Trae Work 分阶段执行，不允许跨阶段开发。**
14. **每个阶段必须有明确验收标准。**

---

# 31. 推荐第一开发顺序

最终执行顺序固定为：

```text
W0 项目初始化
 ↓
W1 配置系统
 ↓
W2 状态机 + Mock
 ↓
W3 Windows 窗口/输入基础能力
 ↓
W4 屏幕识别
 ↓
W5 GameAdapter
 ↓
W6 真实挂机闭环
 ↓
W7 GUI
 ↓
W8 异常恢复
 ↓
W9 Portable 发布
```

其中：

> **W2 完成后，就已经可以证明整个“挂机 → 死亡 → 复活 N 次 → 回城 → 再挂机”的业务逻辑是正确的。**

后面的工作主要是把 Mock 接口逐步替换成 Windows 游戏实际可观察、且允许使用的 UI 操作。
