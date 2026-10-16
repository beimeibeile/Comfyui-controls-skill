---
domain: minimax_h3
title: architecture
source: official
tags: minimax, h3, architecture, video-generation
created_at: 2026-10-16
---

# MiniMax-H3 系统架构

> 来源：https://github.com/MiniMax-AI/MiniMax-H3 官方 README

## 一、系统概览

MiniMax-H3 是 MiniMax 推出的开源视频生成基础模型，采用三模块流水线架构：

```
用户输入 → H3-Context-IR（预处理） → H3-Base（768p生成） → H3-Regenerate-2K（2K重生成）
```

| 模块 | 功能 | 输出 |
|------|------|------|
| **H3-Context-IR** | 将用户输入重写为标准化的 Context-IR 格式 | 结构化 prompt |
| **H3-Base** | 核心生成模型，输出 768p 视频+音频 | 768p MP4 |
| **H3-Regenerate-2K** | 将 768p 提升至 2K 分辨率 | 2K MP4 |

## 二、模型变体

H3-Base 提供两个模型变体：

| 变体 | 全称 | 参考模式 | 适用场景 |
|------|------|----------|----------|
| **FL2VA** | First-Last frame to Video and Audio | 首帧+尾帧 | 有明确起止画面的镜头 |
| **Ref2VA** | Reference to Video and Audio | 全参考（多素材） | 角色一致性、多参考素材 |

## 三、输出规格

| 参数 | 值 |
|------|-----|
| 时长 | 4-15 秒 |
| 帧率 | 24 fps |
| 音频 | 32 kHz 立体声 |
| 语言 | 11 种（含中文/英文） |
| Base 分辨率 | 768p |
| Regenerate 分辨率 | 2K |

## 四、ComfyUI 集成

官方提供 ComfyUI 工作流模板：
- 仓库内 `comfyui/` 目录
- 支持 FL2VA 和 Ref2VA 两种模式
- 需要对应模型权重文件

## 五、本地部署验证（RTX 3080 11GB）

| 参数 | 0.4MP | 0.7MP |
|------|-------|-------|
| 分辨率 | 480×864 | 640×1152 |
| 单镜耗时 | ~236秒 | ~431-445秒 |
| 显存占用 | 可运行 | 可运行（需Sage Attention优化） |

**关键优化**：UNETLoader → MiniMaxH3MemoryEfficientSageAttentionPatch → LoraLoaderModelOnly
