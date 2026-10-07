# ComfyUI Controls Skill - API 参考文档

## 主控入口: ComfyControls

```python
from comfy_controls import ComfyControls, create_controls

cc = create_controls(comfyui_root="D:/Ai/ComfyUI", api_url="http://127.0.0.1:8188")
```

### 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| comfyui_root | str | None | ComfyUI根目录（用于模型管理） |
| api_url | str | http://127.0.0.1:8188 | ComfyUI API地址 |
| output_dir | str | ./output | 输出目录 |
| auto_evolve | bool | True | 是否启用自动进化 |

### 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `is_online()` | 检查ComfyUI是否在线 | bool |
| `list_models(model_type=None)` | 列出可用模型 | Dict[str, List[str]] |
| `list_workflows()` | 列出可用工作流 | List[str] |
| `run_workflow(name, params)` | 运行指定工作流 | Optional[Dict] |
| `batch_generate(workflow, prompts, quality_check)` | 批量生成 | Dict |
| `check_quality(image_path)` | 检查图片质量 | Dict |
| `get_evolution_stats()` | 获取进化统计 | Dict |
| `get_status()` | 获取完整状态 | Dict |

### 预设工作流 (PRESET_WORKFLOWS)

| 名称 | 说明 | 模型 | 默认参数 |
|------|------|------|---------|
| ltx_i2v | LTX图生视频 | ltx-video-2b-int8-distilled | steps=30, cfg=3.0, 768x512, 97帧 |
| hunyuan_i2v | 混元视频I2V | hunyuan-video-1.5-i2v | steps=30, cfg=6.0, 720x1280 |
| zimage_t2i | Z-Image文生图 | z-image-turbo | steps=6, cfg=1.0, 1024x1024 |

## 能力模块

### cap_api_wrapper - API封装

```python
from capabilities.cap_api_wrapper.comfy_api import ComfyAPI
api = ComfyAPI(base_url="http://127.0.0.1:8188")
api.is_online()           # 检查连接
api.get_system_stats()    # 系统状态
api.get_queue()           # 队列状态
api.submit_workflow(...)  # 提交工作流
```

### cap_workflow_manager - 工作流管理

```python
from capabilities.cap_workflow_manager.manager import WorkflowManager
wm = WorkflowManager()
wm.list_workflows()       # 列出工作流
wm.run(name, params, api) # 运行工作流
wm.optimize(name)         # 优化参数
```

### cap_model_manager - 模型管理

```python
from capabilities.cap_model_manager.manager import ModelManager
mm = ModelManager(comfyui_root="D:/Ai/ComfyUI")
mm.list_models(type)      # 列出模型
mm.check_updates()        # 检查更新
mm.auto_optimize()        # 自动优化
```

### cap_batch_generator - 批量生成

```python
from capabilities.cap_batch_generator.generator import BatchGenerator
bg = BatchGenerator(output_dir="./output", api=api)
bg.generate(workflow, prompts, quality_check)
```

### cap_quality_control - 质量控制

```python
from capabilities.cap_quality_control.controller import QualityController
qc = QualityController()
qc.check_image(path)      # 检查单张图片
qc.filter_batch(paths)    # 批量筛选
```

### cap_self_evolution - 自我进化

```python
from capabilities.cap_self_evolution.evolution import SelfEvolution
se = SelfEvolution()
se.record_result(name, params, result, score)  # 记录结果
se.get_best_params(name)                       # 获取最佳参数
se.get_learning_stats()                        # 学习统计
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| COMFYUI_ROOT | "" | ComfyUI根目录 |
| COMFY_OUTPUT_DIR | ./output | 输出目录 |
| COMFYUI_ADDRESS | 127.0.0.1:8188 | API地址 |
