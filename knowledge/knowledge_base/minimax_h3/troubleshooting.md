---
domain: minimax_h3
title: troubleshooting
source: learned
tags: minimax, h3, troubleshooting, errors, debugging
created_at: 2026-10-16
---

# MiniMax-H3 故障排除

> 基于 2026-10-16 实例任务中遇到的真实问题及解决方案

## 一、ComfyUI 运行时错误

### 1.1 `Error running sage attention: Unsupported head_dim: 160`

**现象**：控制台大量红色报错，使用 pytorch attention 回退，显存可能溢出。

**根因**：H3模型的 head_dim=160，默认 Sage Attention 不支持。

**解决方案**：在 UNETLoader 和 LoraLoader 之间插入 `MiniMaxH3MemoryEfficientSageAttentionPatch` 节点：
```
UNETLoader → MiniMaxH3MemoryEfficientSageAttentionPatch → LoraLoaderModelOnly
```

**验证**：插入后控制台不再报红色错误，显存占用稳定。

### 1.2 SaveVideo 节点无输出

**现象**：工作流执行完成但 SaveVideo 没有输出视频文件。

**根因**：H3 的 SaveVideo 节点输出字段名是 `images`，不是常见的 `videos`。

**解决方案**：API 调用时读取 `outputs[node_id]["images"]` 而非 `["videos"]`。

### 1.3 分辨率参数错误

**现象**：`ResolutionSelector` 节点报错或输出分辨率不符合预期。

**根因**：参数值必须与节点枚举完全匹配。

**解决方案**：
- 9:16 竖屏的值是 `9:16 (Portrait Widescreen)`，不是 `9:16 (Vertical)`
- 0.7MP 竖屏实际输出 640×1152（32倍数取整）
- 0.4MP 竖屏实际输出 480×864

### 1.4 显存溢出 (CUDA OOM)

**现象**：`CUDA out of memory`。

**解决方案（按优先级）**：
1. 确保 Sage Attention Patch 已添加
2. 降低分辨率（0.7MP → 0.4MP）
3. 减少帧数（缩短单镜时长）
4. 启用 VAE 分块解码（tile_size=512）
5. 关闭其他占用显存的程序（ComfyUI其他工作流、浏览器硬件加速）

## 二、Prompt 相关问题

### 2.1 生成画面与描述不符

**常见原因**：
- 风格未在 Shot 1 开头声明
- 运镜描述不规范（缺少幅度/速度维度）
- 主体描述不够具体
- 对话格式错误导致模型误解

**检查清单**：
- [ ] Shot 1 有 `Live-action, cinematic` 等风格声明
- [ ] 运镜包含类型+幅度+速度
- [ ] 说话人首次出现有身份描述+ID
- [ ] 对话用 `<d>[Language]...</d>` 包裹
- [ ] 时间格式为 `00:03.500`

### 2.2 角色跨镜头不一致

**原因**：T2V 纯文字模式无法保证角色一致性。

**解决方案**：
- 优先使用 I2V（首帧参考）或 FL2V（首尾帧）
- 多镜头复杂场景用 Ref2VA 全参考模式
- 在每个镜头的主体描述中重复关键外观特征（服装/发型/颜色）

### 2.3 音频缺失或质量差

**检查**：
- `overall_soundscape` 字段是否填写（不要全写 N/A）
- 对话是否用 `<d>` 正确标记
- `non_diegetic_music` 是否需要（不需要写 N/A）
- 说话人ID是否一致

## 三、后处理问题

### 3.1 ffmpeg 中文字幕乱码

**现象**：drawtext 渲染的中文字幕显示为方框或乱码。

**根因**：ffmpeg 默认字体不支持中文。

**解决方案**：指定中文字体文件：
```
ffmpeg -i input.mp4 -vf "drawtext=fontfile=C:/Windows/Fonts/msyh.ttc:text='字幕':fontsize=40:fontcolor=white" output.mp4
```

### 3.2 concat 拼接片段被跳过

**现象**：部分片段未出现在最终视频中。

**根因**：concat 要求所有片段编码参数完全一致，不一致的片段被静默跳过。

**解决方案**：
- 所有片段用相同编码器（libx264）、像素格式（yuv420p）、帧率（24fps）
- 或使用 concat filter 而非 concat demuxer：
  ```
  ffmpeg -i 1.mp4 -i 2.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" out.mp4
  ```

### 3.3 视频时长与预期不符

**原因**：H3 帧数必须为 `17n+5`，实际帧数可能多于 `seconds*24`。

**计算**：
```python
def actual_frames(seconds):
    base = max(5, round(seconds * 24))
    return base + (17 - base % 17) % 17
```
- 5秒 → 125帧 = 5.21秒
- 8秒 → 194帧 = 8.08秒

## 四、模型文件问题

### 4.1 模型文件缺失

**必需文件清单**：
```
models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (type=minimax)
models/vae/minimax_h3_video_vae_fp16.safetensors
models/vae/minimax_h3_audio_vae_fp32.safetensors
models/loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors
```

### 4.2 CLIP 类型错误

**现象**：CLIP 加载失败或 prompt 编码错误。

**解决方案**：CLIP 加载器的 `type` 参数必须设为 `minimax`（不是默认的 `stable_diffusion`）。

## 五、性能优化

### 5.1 单镜耗时过长

| 优化项 | 效果 |
|--------|------|
| Sage Attention Patch | 必须，否则可能OOM |
| Turbo 4step LoRA | 20步即可，无需50步 |
| 0.4MP预览 | 比0.7MP快约40% |
| 分块VAE解码 | 降低显存峰值 |
| 关闭预览 | 减少CPU/IO开销 |

### 5.2 批量生成策略
- 先用 0.4MP 快速预览全部镜头
- 确认效果后再用 0.7MP 正式生成
- 单镜失败不影响其他镜头，可单独重跑
