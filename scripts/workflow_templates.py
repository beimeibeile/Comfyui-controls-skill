"""
ComfyUI工作流模板库（Workflow Templates）
提供常用工作流的快速构建和执行，支持文生图、图生图、批量生成、视频生成等场景
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============ 工作流模板定义 ============
@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    name: str
    description: str
    category: str  # text2image / image2image / batch / video / audio
    default_params: Dict[str, Any] = field(default_factory=dict)
    required_inputs: List[str] = field(default_factory=list)


# 预设工作流模板
WORKFLOW_TEMPLATES = {
    "text2image_standard": WorkflowTemplate(
        template_id="text2image_standard",
        name="标准文生图",
        description="标准文生图工作流，支持SDXL/SD1.5模型",
        category="text2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.0, "sampler": "euler", "scheduler": "normal",
            "denoise": 1.0,
        },
        required_inputs=["prompt", "model"],
    ),
    "text2image_fast": WorkflowTemplate(
        template_id="text2image_fast",
        name="快速文生图",
        description="Lightning/Turbo快速模型，4-8步生成",
        category="text2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 4,
            "cfg": 1.0, "sampler": "euler", "scheduler": "normal",
            "denoise": 1.0,
        },
        required_inputs=["prompt", "model"],
    ),
    "image2image_standard": WorkflowTemplate(
        template_id="image2image_standard",
        name="标准图生图",
        description="基于参考图的图生图工作流",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.0, "denoise": 0.5,
        },
        required_inputs=["prompt", "image_path", "model"],
    ),
    "image2image_inpaint": WorkflowTemplate(
        template_id="image2image_inpaint",
        name="局部重绘",
        description="基于遮罩的局部重绘工作流",
        category="image2image",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.0, "denoise": 0.75,
        },
        required_inputs=["prompt", "image_path", "mask_path", "model"],
    ),
    "batch_text2image": WorkflowTemplate(
        template_id="batch_text2image",
        name="批量文生图",
        description="批量文生图，支持多张提示词并行生成",
        category="batch",
        default_params={
            "width": 1024, "height": 1024, "steps": 30,
            "cfg": 7.0, "batch_size": 4,
        },
        required_inputs=["prompts", "model"],
    ),
    "upscale_4x": WorkflowTemplate(
        template_id="upscale_4x",
        name="4倍超分",
        description="ESRGAN 4倍超分辨率放大",
        category="image2image",
        default_params={
            "scale": 4, "model": "4x-UltraSharp",
        },
        required_inputs=["image_path"],
    ),
    "remove_background": WorkflowTemplate(
        template_id="remove_background",
        name="智能抠图",
        description="REM BG智能背景移除",
        category="image2image",
        default_params={
            "model": "rembg", "alpha_matting": True,
        },
        required_inputs=["image_path"],
    ),
    "video_text2video": WorkflowTemplate(
        template_id="video_text2video",
        name="文生视频",
        description="LTX/Hunyuan视频生成工作流",
        category="video",
        default_params={
            "width": 768, "height": 512, "frames": 49,
            "steps": 30, "cfg": 6.0, "fps": 16,
        },
        required_inputs=["prompt", "model"],
    ),
    "video_image2video": WorkflowTemplate(
        template_id="video_image2video",
        name="图生视频",
        description="基于首帧图的视频生成",
        category="video",
        default_params={
            "width": 768, "height": 512, "frames": 49,
            "steps": 30, "cfg": 6.0, "fps": 16, "denoise": 0.7,
        },
        required_inputs=["prompt", "image_path", "model"],
    ),
    "tts_standard": WorkflowTemplate(
        template_id="tts_standard",
        name="标准TTS",
        description="Qwen3-TTS语音合成",
        category="audio",
        default_params={
            "voice": "Serena", "emotion": "calm", "speed": 1.0,
        },
        required_inputs=["text"],
    ),
}


class WorkflowTemplateLibrary:
    """工作流模板库"""

    def __init__(self, comfyui_url: str = "http://127.0.0.1:8188"):
        self.comfyui_url = comfyui_url
        self.templates = WORKFLOW_TEMPLATES.copy()

    def list_templates(self, category: str = None) -> List[Dict]:
        """列出所有工作流模板"""
        result = []
        for tid, tpl in self.templates.items():
            if category and tpl.category != category:
                continue
            result.append({
                "id": tpl.template_id,
                "name": tpl.name,
                "description": tpl.description,
                "category": tpl.category,
                "default_params": tpl.default_params,
                "required_inputs": tpl.required_inputs,
            })
        return result

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取指定模板"""
        return self.templates.get(template_id)

    def build_workflow(self, template_id: str, **kwargs) -> Optional[Dict]:
        """
        构建工作流JSON

        Args:
            template_id: 模板ID
            **kwargs: 覆盖默认参数

        Returns:
            ComfyUI工作流JSON字典
        """
        template = self.templates.get(template_id)
        if not template:
            logger.error(f"模板不存在: {template_id}")
            return None

        # 合并参数
        params = template.default_params.copy()
        params.update(kwargs)

        # 根据模板类型构建工作流
        if template.category == "text2image":
            return self._build_text2image_workflow(params)
        elif template.category == "image2image":
            return self._build_image2image_workflow(params)
        elif template.category == "video":
            return self._build_video_workflow(params)
        elif template.category == "audio":
            return self._build_tts_workflow(params)
        else:
            logger.error(f"不支持的模板类别: {template.category}")
            return None

    def _build_text2image_workflow(self, params: Dict) -> Dict:
        """构建文生图工作流"""
        prompt = params.get("prompt", "")
        negative_prompt = params.get("negative_prompt", "")
        model = params.get("model", "sd_xl_base_1.0.safetensors")
        width = params.get("width", 1024)
        height = params.get("height", 1024)
        steps = params.get("steps", 30)
        cfg = params.get("cfg", 7.0)
        sampler = params.get("sampler", "euler")
        scheduler = params.get("scheduler", "normal")
        seed = params.get("seed", -1)
        batch_size = params.get("batch_size", 1)

        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width, "height": height,
                    "batch_size": batch_size,
                },
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"images": ["8", 0], "filename_prefix": "ComfyUI"},
            },
        }
        return workflow

    def _build_image2image_workflow(self, params: Dict) -> Dict:
        """构建图生图工作流"""
        # 基于文生图工作流，添加LoadImage和VAEEncode
        workflow = self._build_text2image_workflow(params)
        image_path = params.get("image_path", "")
        denoise = params.get("denoise", 0.5)

        # 修改KSampler的denoise
        workflow["3"]["inputs"]["denoise"] = denoise
        # 替换EmptyLatentImage为LoadImage+VAEEncode
        workflow["5"] = {
            "class_type": "LoadImage",
            "inputs": {"image": os.path.basename(image_path)},
        }
        workflow["10"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["5", 0], "vae": ["4", 2]},
        }
        workflow["3"]["inputs"]["latent_image"] = ["10", 0]

        return workflow

    def _build_video_workflow(self, params: Dict) -> Dict:
        """构建视频生成工作流（简化版）"""
        prompt = params.get("prompt", "")
        model = params.get("model", "ltx-2.5")
        width = params.get("width", 768)
        height = params.get("height", 512)
        frames = params.get("frames", 49)
        steps = params.get("steps", 30)
        cfg = params.get("cfg", 6.0)

        return {
            "1": {
                "class_type": "LTXVideoSampler",
                "inputs": {
                    "prompt": prompt,
                    "width": width, "height": height,
                    "length": frames, "steps": steps,
                    "cfg": cfg, "model": model,
                },
            },
            "2": {
                "class_type": "SaveVideo",
                "inputs": {"video": ["1", 0]},
            },
        }

    def _build_tts_workflow(self, params: Dict) -> Dict:
        """构建TTS工作流（简化版）"""
        return {
            "1": {
                "class_type": "Qwen3TTS",
                "inputs": {
                    "text": params.get("text", ""),
                    "voice": params.get("voice", "Serena"),
                    "emotion": params.get("emotion", "calm"),
                },
            },
            "2": {
                "class_type": "SaveAudio",
                "inputs": {"audio": ["1", 0]},
            },
        }

    def execute_template(self, template_id: str, **kwargs) -> Optional[List[str]]:
        """
        执行模板工作流

        Args:
            template_id: 模板ID
            **kwargs: 工作流参数

        Returns:
            输出文件路径列表
        """
        workflow = self.build_workflow(template_id, **kwargs)
        if not workflow:
            return None

        try:
            from comfy_client import ComfyUIClient
            client = ComfyUIClient(self.comfyui_url)
            result = client.queue_prompt(workflow)
            if result and "prompt_id" in result:
                outputs = client.wait_for_prompt(result["prompt_id"])
                return client.get_output_files(outputs)
            return None
        except ImportError:
            logger.warning("comfy_client不可用，返回工作流JSON")
            return None

    def get_template_summary(self) -> Dict:
        """获取模板库摘要"""
        categories = {}
        for tpl in self.templates.values():
            cat = tpl.category
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        return {
            "total_templates": len(self.templates),
            "categories": categories,
            "templates": [
                {"id": t.template_id, "name": t.name, "category": t.category}
                for t in self.templates.values()
            ],
        }


# ============ 便捷函数 ============
def list_all_templates() -> List[Dict]:
    """列出所有模板（便捷函数）"""
    library = WorkflowTemplateLibrary()
    return library.list_templates()


def build_workflow(template_id: str, **kwargs) -> Optional[Dict]:
    """构建工作流（便捷函数）"""
    library = WorkflowTemplateLibrary()
    return library.build_workflow(template_id, **kwargs)


if __name__ == "__main__":
    library = WorkflowTemplateLibrary()
    summary = library.get_template_summary()
    print(f"工作流模板库: {summary['total_templates']}个模板")
    for cat, count in summary["categories"].items():
        print(f"  {cat}: {count}个")
    print("\n✅ WorkflowTemplateLibrary模块加载成功")
