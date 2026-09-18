# 御龙挂机助手

纯规则、配置驱动、状态机的 Windows 游戏挂机自动化脚本。

完整设计方案见 [DESIGN.md](DESIGN.md)。

## 当前阶段

**W0:项目初始化(已完成)**

已包含:

- Python 项目基础结构与虚拟环境
- `pyproject.toml` / `requirements.txt` / `requirements-dev.txt`
- `app` / `engine` / `behaviors` / `game` / `models` / `utils` / `ui` / `tests` 目录骨架
- logging 基础能力(控制台 + `logs/app.log` + `logs/error.log`)
- `main.py` 入口(启动并输出版本信息)
- 基础 pytest 测试

尚未实现(按 DESIGN.md 开发顺序):

- W1 配置系统
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
- 开发测试:pytest

## 快速开始

```bash
# 创建虚拟环境(如尚未创建)
python3 -m venv .venv

# 安装开发依赖
.venv/bin/pip install -r requirements-dev.txt

# 运行程序
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
├── app/                    # 应用层:常量、启动引导
├── engine/                 # Engine 层:状态机(W2)
├── behaviors/              # Behavior 层:寻路/战斗/复活等(后续阶段)
├── game/                   # Game Adapter 层:截图/OCR/输入(后续阶段)
├── models/                 # Models 层:数据模型(后续阶段)
├── utils/                  # Utils 层:日志等通用工具
├── ui/                     # UI 层:PySide6 GUI(W7)
├── tests/                  # pytest 测试
└── logs/                   # 运行日志(app.log / error.log)
```

## 开发规则

- 每次只做一个阶段(W0~W9),完成后验收再进入下一阶段
- 每阶段结束运行 `pytest` 并检查 `git diff --check`
- 严禁范围漂移,详见 DESIGN.md 第 24、26 节
