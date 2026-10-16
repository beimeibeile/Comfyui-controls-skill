---
domain: minimax_h3
title: best_practices
source: learned
tags: minimax, h3, best-practices, optimization, experience
created_at: 2026-10-16
---

# MiniMax-H3 最佳实践

> 综合官方规范 + 2026-10-16《三打白骨精》第一集实例验证经验

## 一、Prompt 写作最佳实践

### 1.1 风格定调（Shot 1 必须）
- Shot 1 开头明确风格：`Live-action, cinematic` / `2D-animated` / `3D CG` / `watercolor` / `vintage film`
- 影视剧级真实风格用 `Live-action, cinematic`
- 不要在后续镜头重复风格声明

### 1.2 运镜写法
- 必须三维度：类型 + 幅度 + 速度
- 作为自然英语嵌入句子，不要堆在句末
- 静帧用 `The camera holds a static shot as ...`
- 影视剧常用：`pushes in with small amplitude at slow speed`（缓慢推近）

### 1.3 对话写法
- 说话人首次出现必须带身份描述：`the young woman with a quiet, breathy voice (S1)`
- 对话逐字保留，用 `<d>[Chinese]台词</d>`
- 台词后加动作：`She closes her lips and ...`
- 跨镜头连续对话用 `<scenetrans>` 标记

### 1.4 音景分离
- `overall_soundscape`：环境音+物理动作音（风/雨/脚步/布料/撞击/呼吸）
- `non_diegetic_music`：仅观众听到的BGM，描述乐器/速度/节奏/动态变化，不用抽象情绪词
- 无BGM写 `N/A`

## 二、ComfyUI 工作流最佳实践

### 2.1 显存优化（RTX 3080 11GB 必做）
```
UNETLoader → MiniMaxH3MemoryEfficientSageAttentionPatch → LoraLoaderModelOnly
```
- 不加 Sage Attention Patch 会报 `Unsupported head_dim: 160` 且显存溢出
- Patch 放在 UNETLoader 和 LoraLoader 之间

### 2.2 分辨率选择
| 模式 | 分辨率 | 单镜耗时 | 适用 |
|------|--------|----------|------|
| 0.4MP | 480×864 | ~4分钟 | 测试/预览 |
| 0.7MP | 640×1152 | ~7分钟 | 正式产出（竖屏） |

- 分辨率必须是32的倍数
- 0.7MP竖屏实际为 640×1152（非文档中的768p）

### 2.3 帧数计算
```python
def calc_frames(seconds):
    base = max(5, round(seconds * 24))
    remainder = base % 17
    if remainder != 0:
        base += (17 - remainder)
    return base
```
- H3要求帧数为17的倍数+5
- 5秒 = 125帧，8秒 = 194帧

### 2.4 采样参数（Turbo 4step LoRA）
- 采样器：`res_multistep`
- 调度器：`simple`
- 步数：20
- 降噪：1.00

### 2.5 VAE 解码
- 视频VAE：`minimax_h3_video_vae_fp16.safetensors`
- 音频VAE：`minimax_h3_audio_vae_fp32.safetensors`
- 分块解码：tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8
- CreateVideo：fps=24, bit_depth=8

### 2.6 SaveVideo 输出字段
- **输出字段是 `images`，不是 `videos`**
- 这是 ComfyUI H3 节点的常见坑

## 三、角色一致性最佳实践

### 3.1 三视图工作流（Qwen Image Edit）
1. 先用 majicmix 生成正面参考图
2. 用 Qwen Image Edit 图生图生成4视角（正/侧/背/半身）
3. 模型：`qwen_image_edit_2511_fp8` + Lightning 4step LoRA
4. 参数：最大尺寸1536，裁剪上方100，裁剪两侧100

### 3.2 H3 中的角色一致性
- T2V 模式角色由 prompt 文字描述控制，一致性依赖描述精度
- I2V/FL2V 模式用首帧参考图锁定角色形象
- Ref2VA 模式用 `<Subject N>` 标签 + 保留关系标记实现多镜头一致性

## 四、影视剧制作流程最佳实践

### 4.1 标准流程
```
剧本润色 → 角色性格凝练 → 分镜表 → 素材准备（三视图+场景）
→ H3分镜视频生成 → 剪辑合成 → 质检 → 交付
```

### 4.2 分镜表字段（必须）
每个镜头包含：景别、运镜、主体、动作、环境、对话、音效、时长

### 4.3 批量生成
- 逐镜头生成，每镜独立prompt
- 生成后用 ffprobe 验证参数
- 抽帧检查画面质量
- 全部完成后用 ffmpeg concat 拼接

## 五、常见错误与规避

| 错误 | 原因 | 规避 |
|------|------|------|
| `Unsupported head_dim: 160` | 缺少 Sage Attention Patch | UNETLoader后加Patch节点 |
| SaveVideo无输出 | 字段名写错 | 用 `images` 而非 `videos` |
| 分辨率报错 | 非32倍数 | 用ResolutionSelector节点 |
| 角色不一致 | T2V纯文字描述 | 用I2V首帧参考或Ref2VA |
| 中文乱码 | ffmpeg drawtext默认字体 | 指定 `fontfile=msyh.ttc` |
| concat片段被跳过 | 参数不一致 | 所有片段统一编码参数 |
