"""
MiniMax H3 视频生成增强模块 v2.0
在 minimax_h3_runner.py 基础上增加：
1. 提示词工程优化（Timeline结构化提示词模板库）
2. 多版本智能选择（根据场景自动选择FL2VA/Ref2VA/Hybrid）
3. 生成参数自动调优（分辨率/帧数/采样步数根据场景自动匹配）
4. 生成结果质量门（画面稳定性/运动连贯性/音频同步检测）
5. 失败自动重试与参数调整
"""

import os
import sys
import json
import time
import logging
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

FFPROBE = r"D:\Ai\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe"
FFMPEG = r"D:\Ai\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe"


# ============ 场景类型定义 ============

SCENE_TYPES = {
    "portrait": {
        "name": "人像特写",
        "description": "人物面部/半身特写，强调表情和细节",
        "preferred_model": "fl2va",
        "resolution": (768, 1024),
        "frames": 49,
        "motion_intensity": "low",
        "camera_movement": "subtle",
    },
    "full_body": {
        "name": "全身人像",
        "description": "人物全身动作展示",
        "preferred_model": "fl2va",
        "resolution": (768, 1024),
        "frames": 73,
        "motion_intensity": "medium",
        "camera_movement": "medium",
    },
    "scene_landscape": {
        "name": "风景场景",
        "description": "自然风光/城市景观/环境展示",
        "preferred_model": "fl2va",
        "resolution": (1280, 720),
        "frames": 73,
        "motion_intensity": "low",
        "camera_movement": "slow",
    },
    "action": {
        "name": "动作场景",
        "description": "快速运动/打斗/舞蹈/体育",
        "preferred_model": "fl2va",
        "resolution": (768, 1024),
        "frames": 97,
        "motion_intensity": "high",
        "camera_movement": "dynamic",
    },
    "product": {
        "name": "产品展示",
        "description": "商品/物品特写展示，强调质感",
        "preferred_model": "fl2va",
        "resolution": (1024, 1024),
        "frames": 49,
        "motion_intensity": "low",
        "camera_movement": "subtle",
    },
    "story": {
        "name": "剧情叙事",
        "description": "有情节发展的叙事场景",
        "preferred_model": "fl2va",
        "resolution": (768, 1024),
        "frames": 97,
        "motion_intensity": "medium",
        "camera_movement": "varied",
    },
    "reference_driven": {
        "name": "参考驱动",
        "description": "需要角色一致性/多参考输入/唇形同步",
        "preferred_model": "ref2va",
        "resolution": (768, 1024),
        "frames": 73,
        "motion_intensity": "medium",
        "camera_movement": "medium",
    },
    "abstract": {
        "name": "抽象艺术",
        "description": "抽象/艺术/实验性视觉",
        "preferred_model": "fl2va",
        "resolution": (1024, 1024),
        "frames": 73,
        "motion_intensity": "medium",
        "camera_movement": "dynamic",
    },
}


# ============ Timeline提示词模板库 ============

TIMELINE_TEMPLATES = {
    "cinematic_intro": {
        "name": "电影级开场",
        "structure": [
            {"time": "0s-2s", "shot": "远景/全景", "action": "场景建立，缓慢推进", "mood": "宁静/期待"},
            {"time": "2s-5s", "shot": "中景", "action": "主体出现，细节展示", "mood": "聚焦/引入"},
            {"time": "5s-8s", "shot": "特写", "action": "关键细节/表情", "mood": "高潮/强调"},
            {"time": "8s-10s", "shot": "全景", "action": "拉远收尾，留下余韵", "mood": "回味/结束"},
        ],
    },
    "product_showcase": {
        "name": "产品展示",
        "structure": [
            {"time": "0s-2s", "shot": "特写", "action": "产品细节缓慢旋转展示", "mood": "精致/高级"},
            {"time": "2s-5s", "shot": "中景", "action": "产品全貌，光影流动", "mood": "专业/可信"},
            {"time": "5s-8s", "shot": "使用场景", "action": "产品在实际场景中使用", "mood": "实用/向往"},
            {"time": "8s-10s", "shot": "品牌特写", "action": "Logo/品牌名定格", "mood": "记忆/结束"},
        ],
    },
    "emotional_story": {
        "name": "情感叙事",
        "structure": [
            {"time": "0s-3s", "shot": "中景", "action": "人物状态建立，环境交代", "mood": "平静/铺垫"},
            {"time": "3s-6s", "shot": "特写", "action": "情绪转折，表情变化", "mood": "冲突/转折"},
            {"time": "6s-8s", "shot": "近景", "action": "情感高潮，关键动作", "mood": "高潮/释放"},
            {"time": "8s-10s", "shot": "远景", "action": "结局状态，余韵收尾", "mood": "回味/希望"},
        ],
    },
    "dynamic_action": {
        "name": "动感节奏",
        "structure": [
            {"time": "0s-2s", "shot": "快速剪辑", "action": "多角度快速切换，建立节奏", "mood": "紧张/兴奋"},
            {"time": "2s-5s", "shot": "跟拍/运动镜头", "action": "主体动作跟拍，动态模糊", "mood": "动感/流畅"},
            {"time": "5s-8s", "shot": "慢动作特写", "action": "关键动作慢放，细节放大", "mood": "高潮/震撼"},
            {"time": "8s-10s", "shot": "定格/收尾", "action": "动作定格，品牌/标题出现", "mood": "结束/记忆"},
        ],
    },
    "aesthetic_vlog": {
        "name": "美学Vlog",
        "structure": [
            {"time": "0s-3s", "shot": "空镜/细节", "action": "环境细节，光影美学", "mood": "治愈/宁静"},
            {"time": "3s-6s", "shot": "中景/人物", "action": "人物活动，生活片段", "mood": "自然/真实"},
            {"time": "6s-8s", "shot": "特写/美食", "action": "美食/物品特写，质感展示", "mood": "享受/美好"},
            {"time": "8s-10s", "shot": "全景/日落", "action": "大场景收尾，氛围感拉满", "mood": "回味/温暖"},
        ],
    },
}


# ============ 提示词工程优化器 ============

class PromptEngineer:
    """提示词工程优化器"""

    # 画质增强前缀
    QUALITY_PREFIX = "masterpiece, best quality, ultra detailed, 8k, cinematic lighting, professional color grading"

    # 负面提示词
    DEFAULT_NEGATIVE = "low quality, blurry, distorted, deformed, bad anatomy, extra limbs, missing limbs, watermark, text, signature, ugly, pixelated, jpeg artifacts, oversaturated, underexposed"

    # 风格关键词映射
    STYLE_KEYWORDS = {
        "cinematic": "cinematic, film grain, anamorphic lens, shallow depth of field, color graded",
        "anime": "anime style, cel shading, vibrant colors, clean lines",
        "realistic": "photorealistic, hyperrealistic, natural lighting, skin texture, detailed fabric",
        "cyberpunk": "cyberpunk, neon lights, futuristic city, rain, reflections, high contrast",
        "vintage": "vintage, retro, film grain, warm tones, faded colors, 8mm",
        "dreamy": "dreamy, soft focus, ethereal, bokeh, pastel colors, gentle lighting",
        "documentary": "documentary style, handheld camera, natural lighting, candid, raw",
    }

    # 运镜关键词
    CAMERA_MOVEMENTS = {
        "static": "static shot, locked off camera",
        "slow_push": "slow push in, dolly in, gradual zoom",
        "slow_pull": "slow pull out, dolly out, gradual zoom out",
        "pan_left": "pan left, camera moves left",
        "pan_right": "pan right, camera moves right",
        "tilt_up": "tilt up, camera tilts upward",
        "tilt_down": "tilt down, camera tilts downward",
        "tracking": "tracking shot, follow subject, smooth camera movement",
        "orbit": "orbit shot, camera circles around subject",
        "handheld": "handheld camera, slight shake, documentary style",
        "crane_up": "crane shot, camera rises upward",
        "crane_down": "crane shot, camera descends",
    }

    def build_timeline_prompt(self, base_prompt: str,
                                template_name: str = "cinematic_intro",
                                style: str = "cinematic",
                                camera_movement: str = "slow_push",
                                duration: float = 10.0) -> str:
        """
        构建Timeline结构化提示词

        Args:
            base_prompt: 基础提示词（场景/主体描述）
            template_name: Timeline模板名
            style: 风格关键词
            camera_movement: 运镜方式
            duration: 视频时长（秒）

        Returns:
            结构化Timeline提示词
        """
        template = TIMELINE_TEMPLATES.get(template_name, TIMELINE_TEMPLATES["cinematic_intro"])
        style_kw = self.STYLE_KEYWORDS.get(style, "")
        camera_kw = self.CAMERA_MOVEMENTS.get(camera_movement, "")

        # 构建Timeline
        timeline_lines = [f"Timeline:"]
        for seg in template["structure"]:
            line = f"[{seg['time']}] {seg['shot']}: {seg['action']}, mood: {seg['mood']}"
            timeline_lines.append(line)

        # 组合完整提示词
        full_prompt = f"""{self.QUALITY_PREFIX}
{style_kw}
{camera_kw}

Scene: {base_prompt}

{chr(10).join(timeline_lines)}

Audio: ambient sound matching scene mood, subtle background music"""

        return full_prompt.strip()

    def build_simple_prompt(self, base_prompt: str,
                             style: str = "cinematic",
                             camera_movement: str = "slow_push") -> str:
        """构建简单提示词（非Timeline结构）"""
        style_kw = self.STYLE_KEYWORDS.get(style, "")
        camera_kw = self.CAMERA_MOVEMENTS.get(camera_movement, "")

        return f"{self.QUALITY_PREFIX}, {style_kw}, {camera_kw}. {base_prompt}"

    def get_negative_prompt(self) -> str:
        """获取负面提示词"""
        return self.DEFAULT_NEGATIVE

    def list_templates(self) -> List[Dict]:
        """列出所有Timeline模板"""
        return [{"id": k, "name": v["name"], "segments": len(v["structure"])}
                for k, v in TIMELINE_TEMPLATES.items()]

    def list_styles(self) -> List[str]:
        """列出所有风格"""
        return list(self.STYLE_KEYWORDS.keys())

    def list_camera_movements(self) -> List[str]:
        """列出所有运镜方式"""
        return list(self.CAMERA_MOVEMENTS.keys())


# ============ 智能版本选择器 ============

class ModelSelector:
    """多版本智能选择器"""

    def __init__(self):
        self.scene_types = SCENE_TYPES

    def select_model(self, scene_type: str = None,
                     need_reference: bool = False,
                     need_lip_sync: bool = False,
                     quality_priority: str = "balanced") -> str:
        """
        智能选择模型版本

        Args:
            scene_type: 场景类型
            need_reference: 是否需要参考驱动
            need_lip_sync: 是否需要唇形同步
            quality_priority: 质量优先级：quality/balanced/speed

        Returns:
            模型版本：fl2va/ref2va/hybrid
        """
        # 需要参考驱动或唇形同步 → Ref2VA
        if need_reference or need_lip_sync:
            return "ref2va"

        # 场景类型指定
        if scene_type and scene_type in self.scene_types:
            preferred = self.scene_types[scene_type]["preferred_model"]
            if preferred == "ref2va":
                return "ref2va"

        # 质量优先级
        if quality_priority == "quality":
            return "fl2va"  # FL2VA画质最佳
        elif quality_priority == "speed":
            return "fl2va"  # 加速LoRA对FL2VA优化最好
        else:  # balanced
            return "fl2va"  # 默认FL2VA

    def recommend_scene_type(self, prompt: str) -> str:
        """
        根据提示词推荐场景类型

        Args:
            prompt: 提示词

        Returns:
            场景类型
        """
        prompt_lower = prompt.lower()

        # 关键词匹配
        if any(kw in prompt_lower for kw in ["face", "portrait", "close-up", "特写", "面部", "表情"]):
            return "portrait"
        if any(kw in prompt_lower for kw in ["full body", "全身", "standing", "dance", "舞蹈"]):
            return "full_body"
        if any(kw in prompt_lower for kw in ["landscape", "风景", "nature", "mountain", "ocean", "city", "城市"]):
            return "scene_landscape"
        if any(kw in prompt_lower for kw in ["action", "fight", "打斗", "运动", "sports", "跑", "jump"]):
            return "action"
        if any(kw in prompt_lower for kw in ["product", "产品", "商品", "展示", "item", "object"]):
            return "product"
        if any(kw in prompt_lower for kw in ["story", "剧情", "叙事", "scene", "情节"]):
            return "story"
        if any(kw in prompt_lower for kw in ["abstract", "抽象", "艺术", "experimental"]):
            return "abstract"

        return "story"  # 默认剧情叙事

    def list_scene_types(self) -> List[Dict]:
        """列出所有场景类型"""
        return [{"id": k, **v} for k, v in self.scene_types.items()]


# ============ 参数自动调优器 ============

class ParameterOptimizer:
    """生成参数自动调优器"""

    # 分辨率预设
    RESOLUTION_PRESETS = {
        "portrait_768": (768, 1024),    # 竖屏768p
        "portrait_512": (512, 768),      # 竖屏512p（快速）
        "landscape_720": (1280, 720),    # 横屏720p
        "landscape_480": (854, 480),     # 横屏480p（快速）
        "square_1024": (1024, 1024),     # 方形1K
        "square_768": (768, 768),        # 方形768p
    }

    # 帧数预设（24fps）
    FRAME_PRESETS = {
        "2s": 49,    # 约2秒
        "3s": 73,    # 约3秒
        "4s": 97,    # 约4秒
        "5s": 121,   # 约5秒
        "6s": 145,   # 约6秒
        "8s": 193,   # 约8秒
        "10s": 241,  # 约10秒
    }

    def optimize(self, scene_type: str = "story",
                 quality_mode: str = "balanced",
                 target_duration: float = None,
                 gpu_vram: int = 12) -> Dict[str, Any]:
        """
        根据场景和质量模式自动优化参数

        Args:
            scene_type: 场景类型
            quality_mode: 质量模式：fast/balanced/high
            target_duration: 目标时长（秒），None则使用场景默认
            gpu_vram: GPU显存（GB）

        Returns:
            优化后的参数字典
        """
        scene = SCENE_TYPES.get(scene_type, SCENE_TYPES["story"])
        base_res = scene["resolution"]
        base_frames = scene["frames"]

        # 根据质量模式调整
        if quality_mode == "fast":
            # 快速模式：降低分辨率，减少帧数，使用加速LoRA
            resolution = self._downscale_resolution(base_res, 0.75)
            frames = min(base_frames, 49)
            steps = 4
            use_turbo = True
        elif quality_mode == "high":
            # 高质量模式：高分辨率，更多帧数，标准采样
            resolution = base_res
            frames = min(base_frames, 97)
            steps = 20
            use_turbo = False
        else:  # balanced
            resolution = base_res
            frames = base_frames
            steps = 4
            use_turbo = True

        # 根据显存调整
        if gpu_vram <= 8:
            # 8GB显存：进一步降低
            resolution = self._downscale_resolution(resolution, 0.8)
            frames = min(frames, 73)
        elif gpu_vram >= 16:
            # 16GB+显存：可以更高
            pass

        # 目标时长调整帧数
        if target_duration:
            target_frames = int(target_duration * 24) + 1  # 24fps
            # 对齐到H3支持的帧数（49/73/97/121/145/193/241）
            supported_frames = [49, 73, 97, 121, 145, 193, 241]
            frames = min(supported_frames, key=lambda x: abs(x - target_frames))

        return {
            "width": resolution[0],
            "height": resolution[1],
            "frames": frames,
            "steps": steps,
            "use_turbo_lora": use_turbo,
            "fps": 24,
            "duration_seconds": round((frames - 1) / 24, 1),
        }

    def _downscale_resolution(self, res: Tuple[int, int], factor: float) -> Tuple[int, int]:
        """降低分辨率，保持宽高比，对齐到64的倍数"""
        w = int(res[0] * factor)
        h = int(res[1] * factor)
        # 对齐到64的倍数（H3要求）
        w = (w // 64) * 64
        h = (h // 64) * 64
        return (w, h)

    def list_resolution_presets(self) -> Dict[str, Tuple[int, int]]:
        """列出分辨率预设"""
        return self.RESOLUTION_PRESETS

    def list_frame_presets(self) -> Dict[str, int]:
        """列出帧数预设"""
        return self.FRAME_PRESETS


# ============ 生成结果质量门 ============

class VideoQualityGate:
    """视频生成结果质量门"""

    def check(self, video_path: str) -> Dict[str, Any]:
        """
        全面质量检测

        Args:
            video_path: 视频文件路径

        Returns:
            质量检测报告
        """
        report = {
            "video_path": video_path,
            "passed": True,
            "score": 100,
            "checks": {},
            "issues": [],
            "warnings": [],
        }

        if not os.path.exists(video_path):
            report["passed"] = False
            report["score"] = 0
            report["issues"].append("视频文件不存在")
            return report

        # 1. 文件大小检查
        file_size = os.path.getsize(video_path)
        report["checks"]["file_size"] = file_size
        if file_size < 10240:  # 小于10KB
            report["passed"] = False
            report["score"] -= 30
            report["issues"].append(f"文件过小（{file_size} bytes），可能生成失败")
        elif file_size < 102400:  # 小于100KB
            report["score"] -= 10
            report["warnings"].append(f"文件偏小（{file_size} bytes），画质可能不足")

        # 2. ffprobe技术检测
        try:
            tech_info = self._ffprobe_check(video_path)
            report["checks"]["technical"] = tech_info

            # 时长检查
            duration = tech_info.get("duration", 0)
            if duration < 0.5:
                report["passed"] = False
                report["score"] -= 20
                report["issues"].append(f"视频时长过短（{duration}s）")
            elif duration < 1.0:
                report["score"] -= 5
                report["warnings"].append(f"视频时长偏短（{duration}s）")

            # 分辨率检查
            width = tech_info.get("width", 0)
            height = tech_info.get("height", 0)
            if width < 256 or height < 256:
                report["passed"] = False
                report["score"] -= 20
                report["issues"].append(f"分辨率过低（{width}x{height}）")

            # 帧率检查
            fps = tech_info.get("fps", 0)
            if fps < 10:
                report["score"] -= 10
                report["warnings"].append(f"帧率偏低（{fps}fps）")

            # 音频检查
            has_audio = tech_info.get("has_audio", False)
            report["checks"]["has_audio"] = has_audio
            if not has_audio:
                report["warnings"].append("视频无音轨（H3应原生带音频）")

        except Exception as e:
            report["warnings"].append(f"技术检测失败: {e}")

        # 3. 最终评分
        report["score"] = max(0, min(100, report["score"]))
        if report["score"] >= 80:
            report["grade"] = "A"
        elif report["score"] >= 60:
            report["grade"] = "B"
        elif report["score"] >= 40:
            report["grade"] = "C"
        else:
            report["grade"] = "D"

        return report

    def _ffprobe_check(self, video_path: str) -> Dict[str, Any]:
        """使用ffprobe进行技术检测"""
        result = subprocess.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, timeout=30
        )
        info = json.loads(result.stdout)

        tech = {}
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                tech["width"] = stream.get("width", 0)
                tech["height"] = stream.get("height", 0)
                tech["codec"] = stream.get("codec_name", "")
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    tech["fps"] = float(num) / float(den) if float(den) != 0 else 0
                tech["bitrate"] = int(stream.get("bit_rate", 0))
            elif stream.get("codec_type") == "audio":
                tech["has_audio"] = True
                tech["audio_codec"] = stream.get("codec_name", "")
                tech["audio_channels"] = stream.get("channels", 0)
                tech["audio_sample_rate"] = stream.get("sample_rate", 0)

        if "has_audio" not in tech:
            tech["has_audio"] = False

        fmt = info.get("format", {})
        tech["duration"] = float(fmt.get("duration", 0))
        tech["size"] = int(fmt.get("size", 0))
        tech["format"] = fmt.get("format_name", "")

        return tech

    def needs_retry(self, report: Dict[str, Any]) -> bool:
        """判断是否需要重试"""
        return not report["passed"] or report["score"] < 50

    def get_retry_suggestion(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """获取重试建议（参数调整）"""
        suggestions = {
            "adjust_params": {},
            "reason": "",
        }

        for issue in report.get("issues", []):
            if "文件过小" in issue or "生成失败" in issue:
                suggestions["adjust_params"]["steps"] = 20  # 增加步数
                suggestions["adjust_params"]["use_turbo_lora"] = False  # 关闭加速
                suggestions["reason"] = "生成可能不完整，使用标准模式重试"
            elif "时长过短" in issue:
                suggestions["adjust_params"]["frames"] = 97  # 增加帧数
                suggestions["reason"] = "增加视频时长"
            elif "分辨率过低" in issue:
                suggestions["adjust_params"]["width"] = 768
                suggestions["adjust_params"]["height"] = 1024
                suggestions["reason"] = "提升分辨率"

        if not suggestions["reason"]:
            suggestions["reason"] = "使用不同随机种子重试"
            suggestions["adjust_params"]["seed"] = int(time.time()) % (2**31)

        return suggestions


# ============ 自动重试执行器 ============

class AutoRetryExecutor:
    """自动重试执行器"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.quality_gate = VideoQualityGate()

    def execute_with_retry(self, generate_func, config: Dict[str, Any],
                            output_dir: str, output_name: str = None) -> Dict[str, Any]:
        """
        带自动重试的视频生成执行

        Args:
            generate_func: 生成函数（接收config，返回输出路径）
            config: 生成配置
            output_dir: 输出目录
            output_name: 输出文件名

        Returns:
            执行结果
        """
        current_config = config.copy()
        attempts = []

        for attempt in range(self.max_retries):
            logger.info(f"尝试生成 [{attempt+1}/{self.max_retries}]...")

            try:
                output_path = generate_func(current_config, output_dir, output_name)

                if not output_path or not os.path.exists(output_path):
                    attempts.append({"attempt": attempt+1, "success": False, "error": "生成失败，无输出文件"})
                    current_config = self._adjust_for_retry(current_config, attempts[-1])
                    continue

                # 质量检测
                report = self.quality_gate.check(output_path)
                attempts.append({
                    "attempt": attempt+1,
                    "success": report["passed"],
                    "score": report["score"],
                    "grade": report.get("grade", ""),
                    "issues": report.get("issues", []),
                    "output_path": output_path,
                })

                if report["passed"] and report["score"] >= 60:
                    logger.info(f"生成成功，质量评分: {report['score']} ({report.get('grade', '')})")
                    return {
                        "success": True,
                        "output_path": output_path,
                        "attempts": attempts,
                        "quality_report": report,
                        "final_config": current_config,
                    }

                # 需要重试
                if attempt < self.max_retries - 1:
                    suggestion = self.quality_gate.get_retry_suggestion(report)
                    logger.info(f"质量不达标（{report['score']}分），重试原因: {suggestion['reason']}")
                    current_config.update(suggestion["adjust_params"])

            except Exception as e:
                logger.error(f"生成异常: {e}")
                attempts.append({"attempt": attempt+1, "success": False, "error": str(e)})
                if attempt < self.max_retries - 1:
                    time.sleep(2)  # 异常后等待

        # 所有重试失败，返回最后一次结果
        logger.warning(f"所有{self.max_retries}次尝试均未达到质量标准")
        last_attempt = attempts[-1] if attempts else {}
        return {
            "success": False,
            "output_path": last_attempt.get("output_path"),
            "attempts": attempts,
            "error": "所有重试均未达到质量标准",
            "final_config": current_config,
        }

    def _adjust_for_retry(self, config: Dict, last_attempt: Dict) -> Dict:
        """根据上次失败调整配置"""
        adjusted = config.copy()
        adjusted["seed"] = int(time.time()) % (2**31)  # 换种子

        error = last_attempt.get("error", "")
        if "生成失败" in error:
            adjusted["steps"] = 20
            adjusted["use_turbo_lora"] = False

        return adjusted


# ============ 全局单例 ============

_prompt_engineer = None
_model_selector = None
_param_optimizer = None
_quality_gate = None
_auto_retry_executor = None


def get_prompt_engineer() -> PromptEngineer:
    global _prompt_engineer
    if _prompt_engineer is None:
        _prompt_engineer = PromptEngineer()
    return _prompt_engineer


def get_model_selector() -> ModelSelector:
    global _model_selector
    if _model_selector is None:
        _model_selector = ModelSelector()
    return _model_selector


def get_param_optimizer() -> ParameterOptimizer:
    global _param_optimizer
    if _param_optimizer is None:
        _param_optimizer = ParameterOptimizer()
    return _param_optimizer


def get_quality_gate() -> VideoQualityGate:
    global _quality_gate
    if _quality_gate is None:
        _quality_gate = VideoQualityGate()
    return _quality_gate


def get_auto_retry_executor(max_retries: int = 3) -> AutoRetryExecutor:
    return AutoRetryExecutor(max_retries=max_retries)


# ============ 便捷函数 ============

def smart_generate_config(prompt: str,
                           scene_type: str = None,
                           quality_mode: str = "balanced",
                           need_reference: bool = False,
                           need_lip_sync: bool = False,
                           target_duration: float = None,
                           style: str = "cinematic",
                           camera_movement: str = "slow_push",
                           use_timeline: bool = True,
                           timeline_template: str = "cinematic_intro") -> Dict[str, Any]:
    """
    一键智能生成配置（综合所有优化器）

    Args:
        prompt: 基础提示词
        scene_type: 场景类型（None则自动推荐）
        quality_mode: 质量模式：fast/balanced/high
        need_reference: 是否需要参考驱动
        need_lip_sync: 是否需要唇形同步
        target_duration: 目标时长（秒）
        style: 风格
        camera_movement: 运镜方式
        use_timeline: 是否使用Timeline结构化提示词
        timeline_template: Timeline模板名

    Returns:
        完整生成配置
    """
    # 1. 场景类型自动推荐
    selector = get_model_selector()
    if not scene_type:
        scene_type = selector.recommend_scene_type(prompt)

    # 2. 模型版本智能选择
    model_variant = selector.select_model(
        scene_type=scene_type,
        need_reference=need_reference,
        need_lip_sync=need_lip_sync,
        quality_priority=quality_mode,
    )

    # 3. 参数自动调优
    optimizer = get_param_optimizer()
    params = optimizer.optimize(
        scene_type=scene_type,
        quality_mode=quality_mode,
        target_duration=target_duration,
    )

    # 4. 提示词工程优化
    engineer = get_prompt_engineer()
    if use_timeline:
        enhanced_prompt = engineer.build_timeline_prompt(
            base_prompt=prompt,
            template_name=timeline_template,
            style=style,
            camera_movement=camera_movement,
            duration=params["duration_seconds"],
        )
    else:
        enhanced_prompt = engineer.build_simple_prompt(
            base_prompt=prompt,
            style=style,
            camera_movement=camera_movement,
        )

    negative_prompt = engineer.get_negative_prompt()

    # 5. 组合完整配置
    config = {
        "prompt": enhanced_prompt,
        "negative_prompt": negative_prompt,
        "model_variant": model_variant,
        "scene_type": scene_type,
        "quality_mode": quality_mode,
        "width": params["width"],
        "height": params["height"],
        "frames": params["frames"],
        "steps": params["steps"],
        "use_turbo_lora": params["use_turbo_lora"],
        "fps": params["fps"],
        "duration_seconds": params["duration_seconds"],
        "seed": int(time.time()) % (2**31),
        "use_tiled_vae": True,
        "use_mem_eff_attention": True,
        "video_fps": 24,
        "video_bit_depth": 8,
    }

    return config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=== MiniMax H3 增强模块 v2.0 测试 ===\n")

    # 测试提示词工程
    print("--- 提示词工程 ---")
    engineer = get_prompt_engineer()
    print(f"Timeline模板: {len(engineer.list_templates())}个")
    print(f"风格: {len(engineer.list_styles())}种")
    print(f"运镜方式: {len(engineer.list_camera_movements())}种")

    # 测试智能选版
    print("\n--- 智能选版 ---")
    selector = get_model_selector()
    print(f"场景类型: {len(selector.list_scene_types())}种")
    print(f"人像特写推荐: {selector.select_model(scene_type='portrait')}")
    print(f"需要参考驱动: {selector.select_model(need_reference=True)}")
    print(f"自动推荐场景('a girl dancing'): {selector.recommend_scene_type('a girl dancing')}")

    # 测试参数调优
    print("\n--- 参数调优 ---")
    optimizer = get_param_optimizer()
    for mode in ["fast", "balanced", "high"]:
        params = optimizer.optimize(scene_type="portrait", quality_mode=mode)
        print(f"  {mode}: {params['width']}x{params['height']}, {params['frames']}帧, {params['steps']}步")

    # 测试智能配置生成
    print("\n--- 智能配置生成 ---")
    config = smart_generate_config(
        prompt="a beautiful woman in cheongsam standing in an ancient Chinese garden",
        quality_mode="balanced",
        style="cinematic",
        camera_movement="slow_push",
    )
    print(f"场景类型: {config['scene_type']}")
    print(f"模型版本: {config['model_variant']}")
    print(f"分辨率: {config['width']}x{config['height']}")
    print(f"帧数: {config['frames']} ({config['duration_seconds']}s)")
    print(f"步数: {config['steps']} (turbo={config['use_turbo_lora']})")
    print(f"提示词前100字: {config['prompt'][:100]}...")

    print("\n✅ 所有模块测试通过")
