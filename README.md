# 御龙挂机助手

纯规则、配置驱动、状态机的 Windows 游戏挂机自动化脚本。

完整设计方案见 [DESIGN.md](DESIGN.md)。

## 当前阶段

**W1:配置系统(已完成)**

已包含:

- W0:项目基础结构、venv、`pyproject.toml` / requirements、logging、`main.py` 入口、基础测试
- W1:配置系统
  - `models/profile.py`:挂机方案数据模型(位置/寻路/战斗/复活/回城/恢复)
  - `models/settings.py`:应用设置数据模型
  - `app/bootstrap.py`:YAML 加载器(文件/语法/结构错误统一提示)
  - `utils/validation.py`:参数校验工具(字段路径 + 范围校验 + 未知字段提示)
  - `config/settings.yaml` 与 `config/profiles/default.yaml`

尚未实现(按 DESIGN.md 开发顺序):

- W2 状态机 + Mock
- W3 Windows 窗口/输入基础能力
- W4 屏幕识别
- W5 GameAdapter
- W6 真实挂机闭环
- W7 GUI
- W8 异常恢复
- W9 Portable 发布

## 环境要求

- Python >= 3.11
- 运行依赖:PyYAML
- 开发测试:pytest

## 快速开始

```bash
# 创建虚拟环境(如尚未创建)
python3 -m venv .venv

# 安装运行依赖与开发依赖
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 运行程序(加载配置并输出挂机方案摘要)
.venv/bin/python main.py

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
├── engine/                 # Engine 层:状态机(W2)
├── behaviors/              # Behavior 层:寻路/战斗/复活等(后续阶段)
├── game/                   # Game Adapter 层:截图/OCR/输入(后续阶段)
├── models/                 # Models 层:Profile、Settings(W1);State、Runtime(W2)
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
