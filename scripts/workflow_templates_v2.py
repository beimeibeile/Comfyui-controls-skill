"""
ComfyUI工作流模板库扩充 v2.0
在原有10个模板基础上扩充到25+个，覆盖：
- 文生图：人像/风景/动漫/产品/概念艺术
- 图生图：风格迁移/换脸/上色/扩图
- 视频：AnimateDiff/插帧/超分/首尾帧
- 音频：情感TTS/音乐生成/音效
- 特效：粒子/光效/烟雾/爆炸
- 批量：批量图生图/批量超分/批量抠图
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 导入原有模板
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
try:
    from workflow_templates import WorkflowTemplate, WORKFLOW_TEMPLATES as BASE_TEMPLATES
except ImportError:
    WorkflowTemplate = None
    BASE_TEMPLATES = {}


# ============ 新增模板定义 ============

EXTRA_TEMPLATES = {
    # ===== 文生图扩充 =====
    "text2image_portrait": WorkflowTemplate(
        template_id="text2image_portrait",
        name="人像生成",
        description="专业人像生成，优化面部细节和皮肤质感",
        category="text2image",
        default_params={
            "width": 832, "height": 1216, "steps": 35,
            "cfg": 6.5, "sampler": "dpmpp_2m", "scheduler": "karras",
            "denoise": 1.0, "face_detail": True,
        },
        required_inputs=["prompt", "model"],
    ),
    "text2image_landscape": WorkflowTemplate(
        template_id="text2image_landscape",
        name="风景生成",
        description="宽幅风景生成，优化远景和氛围",
        category="text2image",
        default_params={
            "width": 1344, "height": 768, "steps": 30,
            "cfg": 7.0, "sampler": "dpmpp_2m", "scheduler": "karras",
            "denoise": 1.0,
        },
        required_inputs=["prompt", "model"],
    ),
    "text2image_anime": WorkflowTemplate(
        template_id="text2image_anime",
        name="动漫风格",
        description="动漫/二次元风格生成",
        category="text2image",
        default_params={
            "width": 832, "height": 1216, "steps": 28,
            "cfg": 7.5, "sampler": "euler_a", "scheduler": "normal",
            "denoise": 1.0,
        },
        required_inputs=["prompt", "model"],
    ),
    "text2image_product": WorkflowTemplate(
        template_id="text2image_product",
        name="产品图生成",
        description="电商产品图生成，白底/场景图",
        category="text2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 32,
            "cfg": 6.0, "sampler": "dpmpp_2m", "scheduler": "karras",
            "denoise": 1.0, "background": "white",
        },
        required_inputs=["prompt", "model"],
    ),
    "text2image_concept": WorkflowTemplate(
        template_id="text2image_concept",
        name="概念艺术",
        description="概念艺术/插画风格，高细节",
        category="text2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 40,
            "cfg": 8.0, "sampler": "dpmpp_2m_sde", "scheduler": "karras",
            "denoise": 1.0,
        },
        required_inputs=["prompt", "model"],
    ),

    # ===== 图生图扩充 =====
    "image2image_style_transfer": WorkflowTemplate(
        template_id="image2image_style_transfer",
        name="风格迁移",
        description="将参考图转换为指定艺术风格",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 6.5, "denoise": 0.65,
        },
        required_inputs=["prompt", "image_path", "model"],
    ),
    "image2image_face_enhance": WorkflowTemplate(
        template_id="image2image_face_enhance",
        name="人脸增强",
        description="面部细节增强/修复",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 35,
            "cfg": 5.5, "denoise": 0.35, "face_model": "GFPGAN",
        },
        required_inputs=["image_path"],
    ),
    "image2image_colorize": WorkflowTemplate(
        template_id="image2image_colorize",
        name="黑白上色",
        description="黑白照片智能上色",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 6.0, "denoise": 0.45,
        },
        required_inputs=["image_path", "model"],
    ),
    "image2image_outpaint": WorkflowTemplate(
        template_id="image2image_outpaint",
        name="智能扩图",
        description="向外扩展画布，AI补全边缘内容",
        category="image2image",
        default_params={
            "width": 1536, "height": 1024, "steps": 30,
            "cfg": 7.0, "denoise": 0.8, "expand_direction": "both",
        },
        required_inputs=["image_path", "model"],
    ),
    "image2image_sketch_to_image": WorkflowTemplate(
        template_id="image2image_sketch_to_image",
        name="线稿转图",
        description="将线稿/草图转换为完整图像",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.5, "denoise": 0.85, "control_type": "lineart",
        },
        required_inputs=["prompt", "image_path", "model"],
    ),

    # ===== 视频扩充 =====
    "video_animatediff": WorkflowTemplate(
        template_id="video_animatediff",
        name="AnimateDiff动画",
        description="AnimateDiff文生视频/图生视频动画",
        category="video",
        default_params={
            "width": 512, "height": 512, "frames": 16,
            "steps": 25, "cfg": 7.5, "fps": 8,
            "motion_model": "mm_sd_v15_v2",
        },
        required_inputs=["prompt", "model"],
    ),
    "video_frame_interpolation": WorkflowTemplate(
        template_id="video_frame_interpolation",
        name="视频插帧",
        description="RIFE/IFRNet视频帧插值，提升帧率",
        category="video",
        default_params={
            "multiplier": 2, "model": "rife47",
        },
        required_inputs=["video_path"],
    ),
    "video_super_resolution": WorkflowTemplate(
        template_id="video_super_resolution",
        name="视频超分",
        description="视频分辨率提升（480p→1080p等）",
        category="video",
        default_params={
            "scale": 2, "model": "RealESRGAN_x4plus",
        },
        required_inputs=["video_path"],
    ),
    "video_first_last_frame": WorkflowTemplate(
        template_id="video_first_last_frame",
        name="首尾帧视频",
        description="基于首帧和尾帧生成过渡视频",
        category="video",
        default_params={
            "width": 768, "height": 512, "frames": 49,
            "steps": 30, "cfg": 6.0, "fps": 16,
        },
        required_inputs=["prompt", "first_frame", "last_frame", "model"],
    ),
    "video_image_to_video_motion": WorkflowTemplate(
        template_id="video_image_to_video_motion",
        name="图生动图",
        description="静态图片生成动态视频（运镜/微动）",
        category="video",
        default_params={
            "width": 768, "height": 512, "frames": 49,
            "steps": 25, "cfg": 5.5, "fps": 16, "denoise": 0.6,
            "motion_type": "subtle",  # subtle/medium/strong
        },
        required_inputs=["image_path", "model"],
    ),

    # ===== 音频扩充 =====
    "tts_emotional": WorkflowTemplate(
        template_id="tts_emotional",
        name="情感TTS",
        description="带情感的语音合成（开心/悲伤/愤怒等）",
        category="audio",
        default_params={
            "voice": "Serena", "emotion": "calm",
            "speed": 1.0, "pitch": 1.0,
        },
        required_inputs=["text"],
    ),
    "tts_multi_voice": WorkflowTemplate(
        template_id="tts_multi_voice",
        name="多角色配音",
        description="多角色对话配音，自动分配音色",
        category="audio",
        default_params={
            "voices": ["Serena", "Adam", "Jessica"],
            "speed": 1.0,
        },
        required_inputs=["dialogue"],  # [{"role": "A", "text": "..."}]
    ),
    "audio_music_generation": WorkflowTemplate(
        template_id="audio_music_generation",
        name="AI音乐生成",
        description="文本描述生成背景音乐",
        category="audio",
        default_params={
            "duration": 30, "style": "cinematic",
            "tempo": 120, "instrument": "orchestral",
        },
        required_inputs=["description"],
    ),
    "audio_sfx_generation": WorkflowTemplate(
        template_id="audio_sfx_generation",
        name="音效生成",
        description="文本描述生成音效（爆炸/风声/脚步声等）",
        category="audio",
        default_params={
            "duration": 3, "quality": "high",
        },
        required_inputs=["description"],
    ),

    # ===== 特效扩充 =====
    "effect_particle": WorkflowTemplate(
        template_id="effect_particle",
        name="粒子特效",
        description="粒子系统特效（星空/雪花/光斑/烟花）",
        category="effect",
        default_params={
            "width": 1024, "height": 1024, "frames": 48,
            "particle_type": "starfield", "count": 500,
        },
        required_inputs=["particle_type"],
    ),
    "effect_light_sweep": WorkflowTemplate(
        template_id="effect_light_sweep",
        name="光效扫描",
        description="光线扫描/扫光特效",
        category="effect",
        default_params={
            "width": 1024, "height": 1024, "frames": 30,
            "light_color": "#ffffff", "speed": 1.0,
        },
        required_inputs=[],
    ),
    "effect_smoke_fog": WorkflowTemplate(
        template_id="effect_smoke_fog",
        name="烟雾特效",
        description="烟雾/雾气/云雾动态特效",
        category="effect",
        default_params={
            "width": 1024, "height": 1024, "frames": 60,
            "density": 0.5, "speed": 0.5,
        },
        required_inputs=[],
    ),

    # ===== 批量扩充 =====
    "batch_image2image": WorkflowTemplate(
        template_id="batch_image2image",
        name="批量图生图",
        description="批量处理多张图片的图生图",
        category="batch",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.0, "denoise": 0.5,
        },
        required_inputs=["prompts", "image_paths", "model"],
    ),
    "batch_upscale": WorkflowTemplate(
        template_id="batch_upscale",
        name="批量超分",
        description="批量图片超分辨率放大",
        category="batch",
        default_params={
            "scale": 2, "model": "RealESRGAN_x4plus",
        },
        required_inputs=["image_paths"],
    ),
    "batch_remove_background": WorkflowTemplate(
        template_id="batch_remove_background",
        name="批量抠图",
        description="批量移除图片背景",
        category="batch",
        default_params={
            "model": "rembg", "alpha_matting": True,
        },
        required_inputs=["image_paths"],
    ),
}


class WorkflowTemplateLibraryV2:
    """工作流模板库 v2.0（扩充版）"""

    def __init__(self, comfyui_url: str = "http://127.0.0.1:8188"):
        self.comfyui_url = comfyui_url
        # 合并基础模板和扩充模板
        self.templates = {}
        self.templates.update(BASE_TEMPLATES)
        self.templates.update(EXTRA_TEMPLATES)

    def list_templates(self, category: str = None) -> List[Dict]:
        """列出所有模板"""
        result = []
        for tpl in self.templates.values():
            if category and tpl.category != category:
                continue
            result.append({
                "id": tpl.template_id,
                "name": tpl.name,
                "description": tpl.description,
                "category": tpl.category,
                "required_inputs": tpl.required_inputs,
            })
        return result

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    def list_categories(self) -> Dict[str, int]:
        """列出分类及模板数量"""
        categories = {}
        for tpl in self.templates.values():
            categories[tpl.category] = categories.get(tpl.category, 0) + 1
        return categories

    def search_templates(self, keyword: str) -> List[Dict]:
        """搜索模板"""
        keyword = keyword.lower()
        result = []
        for tpl in self.templates.values():
            if (keyword in tpl.name.lower() or
                keyword in tpl.description.lower() or
                keyword in tpl.template_id.lower() or
                keyword in tpl.category.lower()):
                result.append({
                    "id": tpl.template_id,
                    "name": tpl.name,
                    "description": tpl.description,
                    "category": tpl.category,
                })
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取模板库统计"""
        return {
            "total": len(self.templates),
            "categories": self.list_categories(),
            "base_count": len(BASE_TEMPLATES),
            "extended_count": len(EXTRA_TEMPLATES),
        }


# 全局便捷函数
_default_library = None

def get_library() -> WorkflowTemplateLibraryV2:
    global _default_library
    if _default_library is None:
        _default_library = WorkflowTemplateLibraryV2()
    return _default_library

def list_all_templates(category: str = None) -> List[Dict]:
    return get_library().list_templates(category)

def get_template(template_id: str) -> Optional[WorkflowTemplate]:
    return get_library().get_template(template_id)


def main():
    """测试模板库v2.0"""
    library = WorkflowTemplateLibraryV2()
    stats = library.get_stats()

    print("=== ComfyUI工作流模板库 v2.0 ===")
    print(f"总模板数: {stats['total']} (基础{stats['base_count']} + 扩充{stats['extended_count']})")
    print()
    print("【分类统计】")
    for cat, count in stats["categories"].items():
        print(f"  {cat}: {count}个")
    print()

    print("【全部模板列表】")
    for tpl in library.list_templates():
        print(f"  [{tpl['category']}] {tpl['id']} - {tpl['name']}")
        print(f"    {tpl['description']}")

    print()
    print("【搜索测试: '视频'】")
    for tpl in library.search_templates("视频"):
        print(f"  {tpl['id']} - {tpl['name']}")

    print()
    print("模板库 v2.0 就绪")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
