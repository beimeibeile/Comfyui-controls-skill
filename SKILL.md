---
name: Comfyui-controls-skill
version: 1.0.0
description: |
  ComfyUI 智能管理与控制技能。核心能力：工作流智能管理、模型自动进化、批量出产品、
  质量门控制、API统一封装、自我学习进化。与 ai-video-editor、anysearch-skill 为姊妹项目，
  三项目更新须同步。
  Use when asked to 管理ComfyUI、控制ComfyUI、ComfyUI工作流、批量生成、模型管理、ComfyUI自动化。
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
triggers:
  - comfyui
  - ComfyUI
  - 工作流
  - 批量生成
  - 模型管理
  - comfyui控制
  - comfyui管理
metadata:
  license: MIT
  requires:
    bins:
      - python
      - git
    services:
      - ComfyUI (http://127.0.0.1:8188)
---

# ComfyUI Controls Skill

> **ComfyUI 智能管理与控制框架** —— 让 ComfyUI 从工具变成自动出产品的智能体。工作流管理 + 模型进化 + 批量生成 + 质量控制，全链路自动化。

## 姊妹项目

| 项目 | 定位 | 状态 |
|------|------|------|
| **ai-video-editor** | AI视频剪辑框架（ComfyUI算力 + 剪映合成 + Blender特效） | ✅ 活跃 |
| **anysearch-skill** | 深度搜索技能（23垂类领域 + 结构化输出） | ✅ 活跃 |
| **Comfyui-controls-skill** | ComfyUI智能管理与控制（本项目） | 🚀 建设中 |

> 三项目更新须同步，核心能力可互相调用。

## 核心能力

| 能力 | 说明 |
|------|------|
| **工作流智能管理** | 工作流模板库、版本控制、参数优化、一键运行 |
| **模型自动进化** | 模型下载、更新、版本管理、自动测试、性能评估 |
| **批量出产品** | 批量生成、队列管理、进度监控、结果归档 |
| **质量门控制** | 生成结果质量检测、自动筛选、不合格重生成 |
| **API统一封装** | 统一接口调用ComfyUI，屏蔽版本差异 |
| **自我学习进化** | 从生成结果中学习优化参数、积累最佳实践 |
| **算力监控** | GPU使用监控、队列管理、资源调度 |
| **环境自适应** | 自动检测ComfyUI版本、可用模型、插件状态 |

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/beimeibeile/Comfyui-controls-skill.git
cd Comfyui-controls-skill

# 2. 配置环境
cp .env.example .env
# 编辑 .env，填入 ComfyUI 地址和 API Key

# 3. 验证连接
python -c "from capabilities.cap_api_wrapper import ComfyAPI; api = ComfyAPI(); print(api.get_system_stats())"
```

## 环境要求

| 组件 | 必需？ | 说明 |
|------|--------|------|
| **Python** | ✅ 必需 | ≥ 3.10 |
| **ComfyUI** | ✅ 必需 | 运行中，默认 http://127.0.0.1:8188 |
| **GPU** | ⚡ 推荐 | NVIDIA CUDA，显存 ≥ 8GB |
| **FFmpeg** | 可选 | 视频后处理 |

## 项目架构

```
Comfyui-controls-skill/
├── capabilities/              # 能力模块（可插拔）
│   ├── cap_workflow_manager/      # 工作流管理
│   ├── cap_model_manager/         # 模型管理
│   ├── cap_batch_generator/       # 批量生成
│   ├── cap_quality_control/       # 质量控制
│   ├── cap_api_wrapper/           # API封装
│   └── cap_self_evolution/        # 自我进化
├── workflows/                 # 工作流模板库
├── knowledge/                 # 知识库（自学习）
├── scripts/                   # 工具脚本
├── utils/                     # 工具函数
├── SKILL.md                   # 本文件
└── README.md                  # 项目说明
```

## 使用示例

### 1. 批量生成图片

```python
from capabilities.cap_batch_generator import BatchGenerator

generator = BatchGenerator()
results = generator.generate(
    workflow="text_to_image",
    prompts=["一只猫", "一只狗", "一只鸟"],
    output_dir="./output",
    quality_check=True,
)
print(f"生成完成: {len(results['success'])}成功, {len(results['failed'])}失败")
```

### 2. 模型管理

```python
from capabilities.cap_model_manager import ModelManager

manager = ModelManager()
manager.list_models()          # 列出所有模型
manager.check_updates()        # 检查更新
manager.auto_optimize()        # 自动优化模型配置
```

### 3. 工作流管理

```python
from capabilities.cap_workflow_manager import WorkflowManager

wm = WorkflowManager()
wm.list_workflows()            # 列出工作流
wm.run("text_to_image", {"prompt": "一只猫"})
wm.optimize("text_to_image")   # 自动优化工作流参数
```

## 配置说明

复制 `.env.example` 为 `.env` 并配置：

```env
# ComfyUI 连接
COMFYUI_ADDRESS=127.0.0.1:8188
COMFYUI_API_KEY=

# 生成配置
DEFAULT_OUTPUT_DIR=./output
MAX_QUEUE_SIZE=10
QUALITY_CHECK_ENABLED=true

# 模型管理
AUTO_UPDATE_MODELS=false
MODEL_CACHE_SIZE=5

# 自我进化
SELF_LEARNING_ENABLED=true
LEARNING_RATE=0.1
```

## License

[MIT](LICENSE)
