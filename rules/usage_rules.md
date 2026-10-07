# ComfyUI Controls Skill - 使用规则

## AI调用规则

### 1. 初始化规则
- 必须先调用 `create_controls()` 或 `ComfyControls()` 创建实例
- 创建后必须检查 `is_online()`，离线时不得调用生成类方法
- comfyui_root 参数应从环境变量 COMFYUI_ROOT 读取，不得硬编码

### 2. 工作流调用规则
- 优先使用预设工作流（PRESET_WORKFLOWS中的名称）
- 自定义工作流必须先通过 WorkflowManager 注册
- 调用 run_workflow 前必须验证参数完整性（必填字段检查）

### 3. 批量生成规则
- 单次批量不超过 20 个 prompt
- 批量生成必须设置 output_dir，不得使用默认临时目录
- 大批量（>10）必须启用 quality_check 或分批执行

### 4. 错误处理规则
- API调用失败必须重试最多3次，间隔2秒
- 模型不存在时必须列出可用模型供选择
- 显存不足(OOM)时必须降低分辨率或批量大小后重试

### 5. 资源管理规则
- 生成完成后必须清理临时文件
- 长时间运行必须定期检查队列状态
- 不得在ComfyUI队列已满时继续提交

### 6. 与ai-video-editor集成规则
- ai-video-editor通过 ComfyControls 统一入口调用
- 不得直接 import comfy_api 绕过主控层
- 生成结果必须通过 quality_controller 验证后再交付
