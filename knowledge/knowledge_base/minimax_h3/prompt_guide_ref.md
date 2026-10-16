---
domain: minimax_h3
title: prompt_guide_ref
source: official
tags: minimax, h3, prompt, ref2va, full-reference
created_at: 2026-10-16
---

# H3 Prompt 写作指南 — Ref2VA 全参考模式

> 来源：MiniMax-H3 官方 `skills/h3-prompt-writing/references/ref-en.txt`

## 一、六段结构

Ref2VA 输出由六个部分按顺序组成：

| 序号 | 字段 | 用途 |
|------|------|------|
| 1 | `subject_definitions` | 定义参考内容及其标签 |
| 2 | `summary` | 任务类型+目标视频+主要参考关系 |
| 3 | `retention_analysis` | 参考内容如何被保留/转移/复用 |
| 4 | `detailed_description` | 按播放顺序的视觉/动作/镜头/声音/对话 |
| 5 | `overall_soundscape` | 环境音与物理动作音 |
| 6 | `non_diegetic_music` | 仅观众可闻的背景音乐 |

## 二、四种参考标签

| 标签 | 含义 | 示例 |
|------|------|------|
| `<Subject N>` | 可复用/修改的可见内容（人物/场景/服装/道具/风格） | `<Subject 1> is the young woman in <Picture 1>` |
| `<Picture N>` | 作为具体帧锚点的参考图（首帧/关键帧/尾帧） | `<Picture 2> is the first frame of [Shot 1]` |
| `<Video N>` | 提供编辑源/延续起点/时间结构的参考视频 | `<Video 1> is the source video for editing` |
| `<Audio N>` | 复制或参考的音频信号 | `<Audio 1> is the voice-timbre reference for <Subject 1> (S1)` |

> 标签一旦分配，在所有六段中保持同一含义。

## 三、任务类型标记

summary 首行用方括号标记任务类型，多类型用 ` + ` 连接：

| 类型 | 适用场景 |
|------|----------|
| `keyframe completion` | 图片作为首帧/关键帧/尾帧锚点 |
| `reference generation` | 图片/视频/音频提供生成指导（角色/场景/风格/运镜） |
| `video editing` | 直接编辑现有源视频 |
| `video continuation` | 从现有视频延续/扩展 |
| `audio reuse` | 同一音频信号全部/部分复用 |
| `audio reference` | 仅参考音频风格/音色/节奏，不直接复制 |

## 四、保留关系标记

### 视觉内容（Subject/Picture/Video）

| 标记 | 含义 |
|------|------|
| `fully_preserved` | 参考内容的定义角色完全保留 |
| `partially_preserved` | 仍使用，但部分特征改变或仅部分保留 |
| `attribute_transfer` | 参考特征转移到不同的可识别目标主体 |
| `weak_reference` | 仅保留风格/类别/构图/氛围的大致相似 |

### 音频内容（Audio）

| 标记 | 含义 |
|------|------|
| `fully_copy` | 完整源音频作为目标视频的完整最终音轨 |
| `partially_copy` | 仅部分时间线或选定音频层被复制 |
| `reference` | 不直接复制，仅参考音色/节奏/风格 |
| `weak_reference` | 仅保留类别/氛围的大致相似 |

格式：
```
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - 保留细节说明
<Audio 1>: reference - 目标说话人遵循 <Audio 1> 的音色和节奏
```

## 五、detailed_description 与 base 模式的差异

| 维度 | Base 模式 | Ref2VA 模式 |
|------|-----------|-------------|
| 主字段名 | `integrated_multimodal_description` | `detailed_description` |
| 风格开头 | 写在 `[Shot 1]` 之后 | 在 `[Shot 1]` 之前用1-2句英文建立 |
| 参考信息 | 不使用全参考标签 | 在首次出现和角色生效处插入 `<Subject N>` 等标签 |
| 音频关系 | 描述目标视频自身声音 | 在对应镜头引用 `<Audio N>` 并说明复制/参考关系 |

## 六、说话人规则

- 参考主体说话时同时保留视觉标签和说话人ID：`<Subject 2> (S1) turns and says, <d>[English] ...</d>`
- `<Subject N>` 标识参考主体，`(Sx)` 标识实际说话人
- 旁白/画外音保持相同形式并标记 `off-screen`
- 对话/歌词从参考音频直接复用时，逐字保留原文在 `<d>` 内
- 听不清的片段用 `[unclear]` 而非猜测

## 七、完整示例

```
subject_definitions:
<Subject 1> is the coffee-shop environment in <Picture 1>, featuring an exposed brick wall and orange sofa.
<Subject 2> is the fluffy white Samoyed in <Picture 2>, with thick white fur and pointed ears.
<Subject 3> is the young blonde woman in <Video 1>, with long blonde hair and a light-pink shirt.
<Audio 1> is the voice-timbre reference for <Subject 3> (S1).

summary:
[reference generation + audio reference] The target video shows <Subject 3> eating a cookie in <Subject 1>. <Subject 2> lunges toward the cookie.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - the brick wall, sofa, and coffee table are retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - the Samoyed's fur, ears, nose, and tail are retained.
<Audio 1>: reference - its vocal timbre guides the dialogue delivery without copying the signal.

detailed_description:
The target video uses a realistic multi-camera sitcom style with warm indoor lighting.
[Shot 1] A medium shot establishes <Subject 1>. <Subject 3> (S1) sits holding a cookie. <Subject 2> lunges toward the cookie. <Subject 3> (S1) exclaims, <d>[English] Hey! Watch your dog!</d>
[Shot 2] At 00:03.000, the shot cuts to a close-up. <Subject 3> (S1) replies, <d>[English] Well, he has good taste at least.</d>

overall_soundscape:
Soft indoor coffee-shop room tone continues throughout.

non_diegetic_music:
N/A
```
