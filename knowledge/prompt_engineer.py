#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H3 Prompt 生成引擎 (H3PromptEngineer)
将 MiniMax-H3 官方 Prompt Writing Skill 转化为可调用的 Python 能力。

支持模式：
- T2VA: 文生视频+音频（纯文本）
- I2VA: 图生视频+音频（首帧参考）
- FL2VA: 首尾帧视频+音频（首帧+尾帧参考）
- L2VA: 尾帧视频+音频（尾帧参考）
- Ref2VA: 全参考模式（多参考素材，六段结构）

官方规范来源：https://github.com/MiniMax-AI/MiniMax-H3
- base-en.txt: T2VA/I2VA/FL2VA/L2VA 四模式
- ref-en.txt: Ref2VA 全参考模式
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Shot:
    """单个镜头描述"""
    shot_num: int                    # 镜头序号（从1开始）
    cut_time: Optional[str] = None   # 切换时间，格式 "00:03.500"，Shot1为None
    style: str = "Live-action, cinematic"  # 画面风格
    shot_size: str = ""              # 景别（medium-wide shot, close-up等）
    camera_motion: str = ""          # 运镜（含类型+幅度+速度）
    subjects: str = ""               # 主体描述
    action: str = ""                 # 动作描述
    environment: str = ""            # 环境/灯光
    dialogue: Optional[Dict] = None  # 对话 {"speaker_id": "S1", "voice_desc": "...", "language": "Chinese", "text": "..."}
    diegetic_sound: str = ""         # 画内音效
    reference_labels: str = ""       # Ref2VA模式的参考标签（如 <Subject 1>, <Picture 1>）

    def to_text(self, mode: str = "base") -> str:
        """转换为H3规范的镜头文本"""
        parts = []

        # 镜头标记
        if self.shot_num == 1:
            parts.append(f"[Shot 1]")
        else:
            time_str = self.cut_time or "00:03.000"
            parts.append(f"[Shot {self.shot_num}] At {time_str}, the camera cuts to")

        # 风格（仅Shot1在base模式下需要）
        if self.shot_num == 1 and mode == "base" and self.style:
            parts.append(f"{self.style},")

        # 景别
        if self.shot_size:
            parts.append(f"a {self.shot_size} frames")

        # 参考标签（Ref2VA）
        if self.reference_labels:
            parts.append(self.reference_labels)

        # 主体
        if self.subjects:
            parts.append(self.subjects)

        # 环境
        if self.environment:
            parts.append(self.environment)

        # 运镜（自然英语嵌入）
        if self.camera_motion:
            parts.append(self.camera_motion)

        # 动作
        if self.action:
            parts.append(self.action)

        # 对话
        if self.dialogue:
            d = self.dialogue
            speaker = d.get("speaker_id", "S1")
            voice = d.get("voice_desc", "")
            lang = d.get("language", "English")
            text = d.get("text", "")
            if voice:
                parts.append(f"The {voice} ({speaker}) says: <d>[{lang}] {text}</d>")
            else:
                parts.append(f"({speaker}) says: <d>[{lang}] {text}</d>")

        # 画内音效
        if self.diegetic_sound:
            parts.append(self.diegetic_sound)

        return " ".join(parts)


@dataclass
class SubjectDefinition:
    """Ref2VA 参考主体定义"""
    label: str            # <Subject 1>, <Picture 1>, <Video 1>, <Audio 1>
    description: str      # 描述
    source: str = ""      # 来源资产


@dataclass
class RetentionEntry:
    """Ref2VA 保留关系条目"""
    label: str                       # 参考标签
    appearances: str                 # 出现位置（如 [Shot 1], [Shot 3]）
    relationship: str                # fully_preserved/partially_preserved/attribute_transfer/weak_reference
    detail: str                      # 保留细节说明


# ============================================================
# H3 Prompt 生成引擎
# ============================================================

class H3PromptEngineer:
    """H3 Prompt 生成引擎

    将分镜表、角色定义、场景描述等结构化输入，转化为符合 MiniMax-H3 官方
    Prompt Writing Skill 规范的完整 prompt。

    使用示例：
        engine = H3PromptEngineer()
        prompt = engine.generate_t2va(
            shots=[...],
            overall_soundscape="...",
            non_diegetic_music="..."
        )
    """

    # 运镜词汇表（官方规范）
    CAMERA_MOTIONS = {
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "push_in": "Push In",
        "pull_out": "Pull Out",
        "pan_left": "Pan Left",
        "pan_right": "Pan Right",
        "truck_left": "Truck Left",
        "truck_right": "Truck Right",
        "tilt_up": "Tilt Up",
        "tilt_down": "Tilt Down",
        "pedestal_up": "Pedestal Up",
        "pedestal_down": "Pedestal Down",
        "arc": "Arc Shot",
        "tracking": "Tracking Shot",
        "static": "Static Shot",
        "shake_slight": "Shake Slightly",
        "shake_strong": "Shake Strongly",
        "pov": "POV",
        "roll_cw": "Roll Clockwise",
        "roll_ccw": "Roll Counterclockwise",
    }

    # 景别词汇表
    SHOT_SIZES = {
        "extreme_wide": "extreme wide shot",
        "wide": "wide shot",
        "medium_wide": "medium-wide shot",
        "medium": "medium shot",
        "medium_closeup": "medium close-up",
        "closeup": "close-up",
        "extreme_closeup": "extreme close-up",
        "over_shoulder": "over-the-shoulder shot",
        "aerial": "aerial shot",
        "low_angle": "low-angle shot",
        "high_angle": "high-angle shot",
    }

    # 保留关系标记（官方固定值）
    RETENTION_VISUAL = ["fully_preserved", "partially_preserved",
                        "attribute_transfer", "weak_reference"]
    RETENTION_AUDIO = ["fully_copy", "partially_copy", "reference", "weak_reference"]

    def __init__(self):
        self.version = "1.0.0"
        self.spec_source = "https://github.com/MiniMax-AI/MiniMax-H3"

    # --------------------------------------------------------
    # 工具方法
    # --------------------------------------------------------

    def build_camera_motion(self, motion_type: str, amplitude: str = "",
                            speed: str = "") -> str:
        """构建符合官方规范的运镜表达

        官方要求：Motion type + Amplitude + Speed，作为自然英语嵌入镜头描述。

        Args:
            motion_type: 运镜类型（见CAMERA_MOTIONS键或直接英文）
            amplitude: 幅度（small/large，空则省略）
            speed: 速度（slow/fast，空则省略）

        Returns:
            运镜描述字符串，如 "The camera pushes in with small amplitude at slow speed toward..."
        """
        motion = self.CAMERA_MOTIONS.get(motion_type.lower(), motion_type)
        parts = [f"The camera {motion.lower()}"]
        if amplitude:
            parts.append(f"with {amplitude} amplitude")
        if speed:
            parts.append(f"at {speed} speed")
        return " ".join(parts)

    def build_shot(self, shot_num: int, **kwargs) -> Shot:
        """快速构建镜头对象"""
        return Shot(shot_num=shot_num, **kwargs)

    def format_time(self, seconds: float) -> str:
        """秒数转H3时间格式 00:03.500"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"

    # --------------------------------------------------------
    # T2VA: 文生视频+音频
    # --------------------------------------------------------

    def generate_t2va(self, shots: List[Shot],
                      overall_soundscape: str = "",
                      non_diegetic_music: str = "N/A") -> str:
        """生成 T2VA 模式 prompt

        T2VA 无图片对齐指令，直接以三个核心字段开始。

        Args:
            shots: 镜头列表
            overall_soundscape: 整体音景（环境音+物理动作音+非语言人声）
            non_diegetic_music: 非画内音乐（N/A表示无）

        Returns:
            完整的 H3 T2VA prompt
        """
        # integrated_multimodal_description
        desc_parts = []
        for shot in shots:
            desc_parts.append(shot.to_text(mode="base"))
        description = " ".join(desc_parts)

        prompt = (
            f"integrated_multimodal_description: {description}\n"
            f"overall_soundscape: {overall_soundscape or 'N/A'}\n"
            f"non_diegetic_music: {non_diegetic_music}"
        )
        return prompt

    # --------------------------------------------------------
    # I2VA: 图生视频+音频（首帧参考）
    # --------------------------------------------------------

    def generate_i2va(self, shots: List[Shot],
                      overall_soundscape: str = "",
                      non_diegetic_music: str = "N/A",
                      first_shot_ref: str = "[Shot 1]") -> str:
        """生成 I2VA 模式 prompt

        I2VA 首行必须是固定的图片对齐指令。

        Args:
            shots: 镜头列表（Shot1应描述从参考图开始的发展）
            overall_soundscape: 整体音景
            non_diegetic_music: 非画内音乐
            first_shot_ref: 首帧参考标记，默认 [Shot 1]

        Returns:
            完整的 H3 I2VA prompt
        """
        instruction = (
            f"For the target video, at 0.00 seconds into the target video, "
            f"<Picture 1> (from {first_shot_ref}) is fully referenced."
        )

        desc_parts = []
        for shot in shots:
            desc_parts.append(shot.to_text(mode="base"))
        description = " ".join(desc_parts)

        prompt = (
            f"{instruction}\n\n"
            f"integrated_multimodal_description: {description}\n"
            f"overall_soundscape: {overall_soundscape or 'N/A'}\n"
            f"non_diegetic_music: {non_diegetic_music}"
        )
        return prompt

    # --------------------------------------------------------
    # FL2VA: 首尾帧视频+音频
    # --------------------------------------------------------

    def generate_fl2va(self, shots: List[Shot],
                       duration_seconds: float,
                       overall_soundscape: str = "",
                       non_diegetic_music: str = "N/A",
                       last_shot_num: Optional[int] = None) -> str:
        """生成 FL2VA 模式 prompt

        FL2VA 首行是首尾帧对齐指令。通常单镜头，让模型在首尾帧间连续插值。

        Args:
            shots: 镜头列表
            duration_seconds: 视频时长（秒），用于尾帧时间标记
            overall_soundscape: 整体音景
            non_diegetic_music: 非画内音乐
            last_shot_num: 尾帧所在镜头序号，默认最后一个

        Returns:
            完整的 H3 FL2VA prompt
        """
        if last_shot_num is None:
            last_shot_num = shots[-1].shot_num if shots else 1

        time_str = f"{duration_seconds:.2f}"
        instruction = (
            f"How the reference pictures align with the target video — "
            f"Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {last_shot_num}) aligns with the {time_str}-second mark of the target video."
        )

        desc_parts = []
        for shot in shots:
            desc_parts.append(shot.to_text(mode="base"))
        description = " ".join(desc_parts)

        prompt = (
            f"{instruction}\n\n"
            f"integrated_multimodal_description: {description}\n"
            f"overall_soundscape: {overall_soundscape or 'N/A'}\n"
            f"non_diegetic_music: {non_diegetic_music}"
        )
        return prompt

    # --------------------------------------------------------
    # L2VA: 尾帧视频+音频
    # --------------------------------------------------------

    def generate_l2va(self, shots: List[Shot],
                      duration_seconds: float,
                      overall_soundscape: str = "",
                      non_diegetic_music: str = "N/A",
                      last_shot_num: Optional[int] = None) -> str:
        """生成 L2VA 模式 prompt

        L2VA 仅尾帧参考，描述从合理的前序状态逐渐收敛到参考图。

        Args:
            shots: 镜头列表
            duration_seconds: 视频时长
            overall_soundscape: 整体音景
            non_diegetic_music: 非画内音乐
            last_shot_num: 尾帧所在镜头序号

        Returns:
            完整的 H3 L2VA prompt
        """
        if last_shot_num is None:
            last_shot_num = shots[-1].shot_num if shots else 1

        time_str = f"{duration_seconds:.2f}"
        instruction = (
            f"How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot {last_shot_num}]) aligns with the {time_str}-second mark of the target video."
        )

        desc_parts = []
        for shot in shots:
            desc_parts.append(shot.to_text(mode="base"))
        description = " ".join(desc_parts)

        prompt = (
            f"{instruction}\n\n"
            f"integrated_multimodal_description: {description}\n"
            f"overall_soundscape: {overall_soundscape or 'N/A'}\n"
            f"non_diegetic_music: {non_diegetic_music}"
        )
        return prompt

    # --------------------------------------------------------
    # Ref2VA: 全参考模式（六段结构）
    # --------------------------------------------------------

    def generate_ref2va(self,
                        subject_definitions: List[SubjectDefinition],
                        task_types: List[str],
                        summary: str,
                        retention_analysis: List[RetentionEntry],
                        shots: List[Shot],
                        overall_soundscape: str = "",
                        non_diegetic_music: str = "N/A",
                        opening_style: str = "") -> str:
        """生成 Ref2VA 全参考模式 prompt

        六段结构：
        1. subject_definitions - 参考内容定义
        2. summary - 任务摘要
        3. retention_analysis - 保留关系分析
        4. detailed_description - 详细描述
        5. overall_soundscape
        6. non_diegetic_music

        Args:
            subject_definitions: 参考主体定义列表
            task_types: 任务类型列表（keyframe completion/reference generation/
                       video editing/video continuation/audio reuse/audio reference）
            summary: 任务摘要（使用参考标签描述）
            retention_analysis: 保留关系条目列表
            shots: 镜头列表（使用 reference_labels 字段标注参考标签）
            overall_soundscape: 整体音景
            non_diegetic_music: 非画内音乐
            opening_style: 开头风格描述（在Shot1之前的1-2句）

        Returns:
            完整的 H3 Ref2VA prompt
        """
        # 1. subject_definitions
        sd_lines = ["subject_definitions:"]
        for sd in subject_definitions:
            line = f"{sd.label} is {sd.description}"
            if sd.source:
                line += f" (from {sd.source})"
            sd_lines.append(line)
        sd_text = "\n".join(sd_lines)

        # 2. summary
        task_prefix = " + ".join(task_types)
        summary_text = f"summary:\n[{task_prefix}] {summary}"

        # 3. retention_analysis
        ra_lines = ["retention_analysis:"]
        for ra in retention_analysis:
            ra_lines.append(
                f"{ra.label} ({ra.appearances}): {ra.relationship} - {ra.detail}"
            )
        ra_text = "\n".join(ra_lines)

        # 4. detailed_description
        dd_parts = ["detailed_description:"]
        if opening_style:
            dd_parts.append(opening_style)
        for shot in shots:
            dd_parts.append(shot.to_text(mode="ref"))
        description = "\n".join(dd_parts)

        # 5 & 6. 音频
        sound_text = f"overall_soundscape:\n{overall_soundscape or 'N/A'}"
        music_text = f"non_diegetic_music:\n{non_diegetic_music}"

        prompt = (
            f"{sd_text}\n\n"
            f"{summary_text}\n\n"
            f"{ra_text}\n\n"
            f"{description}\n\n"
            f"{sound_text}\n\n"
            f"{music_text}"
        )
        return prompt

    # --------------------------------------------------------
    # 从分镜表JSON批量生成（实用接口）
    # --------------------------------------------------------

    def generate_from_storyboard(self, storyboard: List[Dict],
                                 mode: str = "t2va",
                                 duration: float = 5.0,
                                 overall_soundscape: str = "",
                                 non_diegetic_music: str = "N/A") -> str:
        """从分镜表字典列表批量生成 prompt

        分镜表字段（兼容常见格式）：
        - shot_num / id: 镜头序号
        - cut_time / time: 切换时间
        - style: 风格
        - shot_size / framing: 景别
        - camera_motion / motion: 运镜
        - subjects / subject / character: 主体
        - action / description: 动作
        - environment / scene / lighting: 环境
        - dialogue / line / text: 对话
        - sound / sfx: 音效

        Args:
            storyboard: 分镜表列表
            mode: t2va/i2va/fl2va/l2va
            duration: 视频时长（fl2va/l2va需要）
            overall_soundscape: 整体音景
            non_diegetic_music: 非画内音乐

        Returns:
            完整 prompt
        """
        shots = []
        for i, sb in enumerate(storyboard):
            shot_num = sb.get("shot_num", sb.get("id", i + 1))
            cut_time = sb.get("cut_time", sb.get("time"))
            if cut_time and isinstance(cut_time, (int, float)):
                cut_time = self.format_time(cut_time)

            # 运镜处理
            motion = sb.get("camera_motion", sb.get("motion", ""))
            if isinstance(motion, dict):
                motion = self.build_camera_motion(
                    motion.get("type", "static"),
                    motion.get("amplitude", ""),
                    motion.get("speed", "")
                )

            # 对话处理
            dialogue = None
            dlg = sb.get("dialogue", sb.get("line", sb.get("text")))
            if dlg:
                if isinstance(dlg, dict):
                    dialogue = dlg
                elif isinstance(dlg, str):
                    dialogue = {
                        "speaker_id": sb.get("speaker", "S1"),
                        "voice_desc": sb.get("voice", ""),
                        "language": sb.get("language", "Chinese"),
                        "text": dlg
                    }

            shot = Shot(
                shot_num=shot_num,
                cut_time=cut_time,
                style=sb.get("style", "Live-action, cinematic"),
                shot_size=sb.get("shot_size", sb.get("framing", "")),
                camera_motion=motion,
                subjects=sb.get("subjects", sb.get("subject", sb.get("character", ""))),
                action=sb.get("action", sb.get("description", "")),
                environment=sb.get("environment", sb.get("scene", sb.get("lighting", ""))),
                dialogue=dialogue,
                diegetic_sound=sb.get("sound", sb.get("sfx", "")),
            )
            shots.append(shot)

        if mode == "t2va":
            return self.generate_t2va(shots, overall_soundscape, non_diegetic_music)
        elif mode == "i2va":
            return self.generate_i2va(shots, overall_soundscape, non_diegetic_music)
        elif mode == "fl2va":
            return self.generate_fl2va(shots, duration, overall_soundscape, non_diegetic_music)
        elif mode == "l2va":
            return self.generate_l2va(shots, duration, overall_soundscape, non_diegetic_music)
        else:
            raise ValueError(f"不支持的模式: {mode}，可选 t2va/i2va/fl2va/l2va")

    # --------------------------------------------------------
    # 校验
    # --------------------------------------------------------

    def validate_prompt(self, prompt: str, mode: str = "base") -> Dict:
        """校验生成的 prompt 是否符合 H3 规范

        Args:
            prompt: 待校验 prompt
            mode: base (T2VA/I2VA/FL2VA/L2VA) / ref (Ref2VA)

        Returns:
            校验结果 {"valid": bool, "errors": [...], "warnings": [...]}
        """
        errors = []
        warnings = []

        if mode == "base":
            # 检查三个核心字段
            for field in ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]:
                if f"{field}:" not in prompt:
                    errors.append(f"缺少字段: {field}")

            # 检查镜头标记
            if "[Shot 1]" not in prompt:
                errors.append("缺少 [Shot 1] 标记")

            # 检查对话格式
            if "<d>[" in prompt and "</d>" not in prompt:
                errors.append("对话标签 <d> 未闭合")

            # 检查时间格式
            import re
            bad_times = re.findall(r'At (\d+:\d+\.?\d*)', prompt)
            for bt in bad_times:
                if not re.match(r'\d{2}:\d{2}\.\d{3}', bt):
                    warnings.append(f"时间格式可能不规范: {bt}（应为 00:03.500）")

        elif mode == "ref":
            for field in ["subject_definitions", "summary", "retention_analysis",
                          "detailed_description", "overall_soundscape", "non_diegetic_music"]:
                if f"{field}:" not in prompt:
                    errors.append(f"Ref2VA缺少字段: {field}")

            # 检查参考标签
            if "<Subject" not in prompt and "<Picture" not in prompt:
                warnings.append("Ref2VA模式未检测到参考标签 <Subject N>/<Picture N>")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "mode": mode,
            "length": len(prompt)
        }

    def get_spec_summary(self) -> Dict:
        """获取 H3 Prompt 规范摘要"""
        return {
            "version": self.version,
            "source": self.spec_source,
            "modes": {
                "T2VA": "文生视频+音频，纯文本，三字段结构",
                "I2VA": "图生视频+音频，首帧参考，首行固定对齐指令",
                "FL2VA": "首尾帧视频+音频，首帧+尾帧参考，通常单镜头连续插值",
                "L2VA": "尾帧视频+音频，仅尾帧参考，从前序状态收敛到尾帧",
                "Ref2VA": "全参考模式，六段结构，支持多参考素材"
            },
            "core_fields_base": ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"],
            "core_fields_ref": ["subject_definitions", "summary", "retention_analysis",
                                "detailed_description", "overall_soundscape", "non_diegetic_music"],
            "dialogue_format": "<d>[Language]台词</d>",
            "speaker_format": "(S1), (S2), 复合 (S1,S2)",
            "shot_format": "[Shot 1] 无时间戳; [Shot 2] At 00:03.500, ...",
            "camera_motion_dimensions": ["motion type", "amplitude", "speed"]
        }


# ============================================================
# 便捷函数
# ============================================================

def quick_generate(shots_data: List[Dict], mode: str = "t2va",
                   soundscape: str = "", music: str = "N/A",
                   duration: float = 5.0) -> str:
    """便捷函数：从分镜数据快速生成 H3 prompt

    Args:
        shots_data: 分镜数据列表
        mode: t2va/i2va/fl2va/l2va
        soundscape: 整体音景
        music: 非画内音乐
        duration: 时长

    Returns:
        H3 规范 prompt
    """
    engine = H3PromptEngineer()
    return engine.generate_from_storyboard(shots_data, mode, duration, soundscape, music)


if __name__ == "__main__":
    # 自检：生成一个 T2VA 示例
    engine = H3PromptEngineer()

    shots = [
        engine.build_shot(1,
            style="Live-action, cinematic",
            shot_size="medium-wide shot",
            subjects="a middle-aged baker with a calm, slightly raspy voice (S1)",
            action="places a fresh loaf on the wooden counter",
            dialogue={"speaker_id": "S1", "voice_desc": "calm, slightly raspy",
                      "language": "English", "text": "First batch of the morning."},
            camera_motion=engine.build_camera_motion("push_in", "small", "slow")
        ),
        engine.build_shot(2,
            cut_time="00:05.000",
            shot_size="close-up",
            action="steam rising from the sliced bread"
        ),
    ]

    prompt = engine.generate_t2va(
        shots,
        overall_soundscape="Wooden shutters scrape open over a quiet street.",
        non_diegetic_music="A soft acoustic-guitar pattern at a moderate tempo."
    )

    print("=== H3 Prompt 生成引擎自检 ===")
    print(f"版本: {engine.version}")
    print(f"\n生成的 T2VA prompt:\n")
    print(prompt)
    print(f"\n校验结果: {json.dumps(engine.validate_prompt(prompt, 'base'), ensure_ascii=False, indent=2)}")
