---
domain: minimax_h3
title: prompt_guide_base
source: official
tags: minimax, h3, prompt, t2va, i2va, fl2va, l2va
created_at: 2026-10-16
---

# H3 Prompt 写作指南 — Base 模式 (T2VA / I2VA / FL2VA / L2VA)

> 来源：MiniMax-H3 官方 `skills/h3-prompt-writing/references/base-en.txt`

## 一、四种模式

| 模式 | 全称 | 参考 | 首行指令 |
|------|------|------|----------|
| **T2VA** | Text to Video and Audio | 无 | 无，直接三字段 |
| **I2VA** | Image to Video and Audio | 首帧 | 固定对齐指令 |
| **FL2VA** | First-Last to Video and Audio | 首帧+尾帧 | 首尾帧对齐指令 |
| **L2VA** | Last to Video and Audio | 尾帧 | 尾帧对齐指令 |

## 二、最终 Prompt 结构

### Part One: 指令（仅 I2VA/FL2VA/L2VA）

**I2VA 固定首行：**
```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

**FL2VA 固定首行：**
```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

**L2VA 固定首行：**
```
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

### Part Two: 三个核心字段

```
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

| 字段 | 内容 |
|------|------|
| `integrated_multimodal_description` | 视觉、动作、镜头、说话人、对话、唱歌、画内音效，沿时间线展开 |
| `overall_soundscape` | 全片环境音、物理动作音、非语言人声（1-4句） |
| `non_diegetic_music` | 角色听不到、仅观众听到的背景音乐（1-3句，N/A表示无） |

## 三、镜头与切换

- **Shot 1** 无时间戳：`[Shot 1] Live-action, cinematic, ...`
- **后续镜头** 带切换时间：`[Shot 2] At 00:03.500, the camera cuts to ...`
- 时间格式严格为 `MM:SS.mmm`（如 `00:03.500`）
- 切换引入新信息（主体/空间/状态/视角/时间），仅距离或角度变化用运镜

## 四、运镜三维度

完整运镜 = **Motion type** + **Amplitude** + **Speed**，作为自然英语嵌入镜头：

```
The camera pushes in with small amplitude at slow speed toward the letter.
The camera pans right with large amplitude at fast speed, revealing the doorway.
The camera holds a static shot as the runner exits the frame.
```

| 维度 | 可选值 |
|------|--------|
| 类型 | Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll Clockwise/Counterclockwise |
| 幅度 | with small amplitude / with large amplitude（中等省略） |
| 速度 | at slow speed / at fast speed（正常省略） |

## 五、说话人与对话

- 说话人用稳定 ID：`(S1)`, `(S2)`，多人用 `(S1,S2)`
- 首次出现时提供身份信息（年龄/性别/音色/语速）
- 对话格式：`<d>[Language]原始台词</d>`，**逐字保留不翻译**
- 旁白用 `says in an off-screen voiceover`，并说明对应角色嘴唇闭合
- 跨切对话用 `<scenetrans>` 标记

## 六、画内文字

屏幕上可见的文字（招牌/字幕/标签）用英文双引号，保留原文：
```
A red neon sign reading "营业中" glows above the doorway.
```

## 七、完整示例（T2VA）

```
integrated_multimodal_description: [Shot 1] Live-action, cinematic, a medium-wide shot frames a baker opening the shutters before sunrise. The camera pushes in with small amplitude at slow speed as the middle-aged baker with a calm, slightly raspy voice (S1) places a fresh loaf on the counter and says: <d>[English] First batch of the morning.</d> [Shot 2] At 00:05.000, the camera cuts to a close-up of steam rising from the sliced bread.
overall_soundscape: Wooden shutters scrape open over a quiet street as trays clink softly. The doorbell rings once, followed by light footsteps and bread being sliced.
non_diegetic_music: A soft acoustic-guitar pattern at a moderate tempo, joined by sparse upright-bass notes.
```
