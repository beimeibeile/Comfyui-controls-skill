"""
ComfyUI Controls Skill - 统一入口模块
智能管理和控制ComfyUI，自动进化、自动出产品

使用方法：
    from comfy_controls import ComfyControls
    cc = ComfyControls(comfyui_root="D:/Ai/ComfyUI-aki-v3.2/ComfyUI")
    cc.list_models()
    cc.run_workflow("ltx_i2v", {"image": "input.jpg", "prompt": "a cat"})
"""

import os
import sys
from typing import Dict, List, Optional, Any

# 添加能力模块路径
_cap_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capabilities")
for sub in ["cap_api_wrapper", "cap_workflow_manager", "cap_model_manager",
            "cap_batch_generator", "cap_quality_control", "cap_self_evolution"]:
    sys.path.insert(0, os.path.join(_cap_dir, sub))

from cap_api_wrapper.comfy_api import ComfyAPI
from cap_workflow_manager.manager import WorkflowManager
from cap_model_manager.manager import ModelManager
from cap_batch_generator.generator import BatchGenerator
from cap_quality_control.controller import QualityController
from cap_self_evolution.evolution import SelfEvolution


class ComfyControls:
    """ComfyUI智能控制器 - 统一入口"""

    def __init__(self,
                 comfyui_root: str = None,
                 api_url: str = "http://127.0.0.1:8188",
                 output_dir: str = None,
                 auto_evolve: bool = True):
        """
        初始化ComfyUI控制器

        Args:
            comfyui_root: ComfyUI根目录
            api_url: ComfyUI API地址
            output_dir: 输出目录
            auto_evolve: 是否启用自动进化
        """
        self.comfyui_root = comfyui_root or os.environ.get("COMFYUI_ROOT", "")
        self.api_url = api_url
        self.output_dir = output_dir or os.environ.get("COMFY_OUTPUT_DIR", "./output")
        self.auto_evolve = auto_evolve

        # 初始化各模块
        self.api = ComfyAPI(base_url=api_url)
        self.workflows = WorkflowManager()
        self.models = ModelManager(comfyui_root=self.comfyui_root)
        self.batch = BatchGenerator(output_dir=self.output_dir, api=self.api)
        self.quality = QualityController()
        self.evolution = SelfEvolution()

        print(f"✅ ComfyControls 初始化完成")
        print(f"   API: {api_url} {'在线' if self.api.is_online() else '离线'}")
        print(f"   工作流: {len(self.workflows.list_workflows())}个")
        print(f"   自动进化: {'开启' if auto_evolve else '关闭'}")

    def is_online(self) -> bool:
        """检查ComfyUI是否在线"""
        return self.api.is_online()

    def list_models(self, model_type: str = None) -> Dict[str, List[str]]:
        """列出模型"""
        if model_type:
            return {model_type: self.models.list_models(model_type)}
        return self.models.list_all_models()

    def list_workflows(self) -> List[str]:
        """列出可用工作流"""
        return self.workflows.list_workflows()

    def run_workflow(self, name: str, params: Dict = None) -> Optional[Dict]:
        """
        运行工作流

        Args:
            name: 工作流名称
            params: 参数

        Returns:
            生成结果
        """
        if not self.is_online():
            print("❌ ComfyUI离线，无法运行工作流")
            return None

        # 自动进化：如果有历史最佳参数，优先使用
        if self.auto_evolve:
            best = self.evolution.get_best_params(name)
            if best and params:
                for k, v in best.items():
                    if k not in params and not k.startswith("_"):
                        params[k] = v

        result = self.workflows.run(name, params=params, api=self.api)

        # 记录学习结果
        if self.auto_evolve and result:
            quality_score = 0.5  # 默认质量分，实际需要质量评估
            self.evolution.record_result(name, params or {}, result, quality_score)

        return result

    def batch_generate(self, workflow: str, prompts: List[str],
                       quality_check: bool = False) -> Dict:
        """
        批量生成

        Args:
            workflow: 工作流名称
            prompts: 提示词列表
            quality_check: 是否启用质量检查

        Returns:
            批量生成结果
        """
        return self.batch.generate(
            workflow=workflow,
            prompts=prompts,
            quality_check=quality_check,
        )

    def check_quality(self, image_path: str) -> Dict:
        """检查图片质量"""
        return self.quality.check_image(image_path)

    def get_evolution_stats(self) -> Dict:
        """获取进化统计"""
        return self.evolution.get_learning_stats()

    def get_status(self) -> Dict:
        """获取完整状态"""
        return {
            "online": self.is_online(),
            "api_url": self.api_url,
            "workflows": self.list_workflows(),
            "models_count": sum(len(v) for v in self.list_models().values()),
            "evolution": self.get_evolution_stats(),
            "queue": self.api.get_queue() if self.is_online() else {},
        }


# 预设工作流模板
PRESET_WORKFLOWS = {
    "ltx_i2v": {
        "name": "LTX图生视频",
        "description": "LTX Video int8 distilled 图生视频",
        "model": "ltx-video-2b-int8-distilled.safetensors",
        "default_params": {
            "steps": 30,
            "cfg": 3.0,
            "width": 768,
            "height": 512,
            "duration": 97,
        },
    },
    "hunyuan_i2v": {
        "name": "混元视频I2V",
        "description": "HunyuanVideo 1.5 图生视频",
        "model": "hunyuan-video-1.5-i2v.safetensors",
        "default_params": {
            "steps": 30,
            "cfg": 6.0,
            "width": 720,
            "height": 1280,
        },
    },
    "zimage_t2i": {
        "name": "Z-Image文生图",
        "description": "Z-Image-Turbo 极速文生图",
        "model": "z-image-turbo.safetensors",
        "default_params": {
            "steps": 6,
            "cfg": 1.0,
            "width": 1024,
            "height": 1024,
        },
    },
}


def create_controls(comfyui_root: str = None, **kwargs) -> ComfyControls:
    """便捷创建ComfyControls实例"""
    return ComfyControls(comfyui_root=comfyui_root, **kwargs)


if __name__ == "__main__":
    print("=" * 60)
    print("ComfyUI Controls Skill")
    print("=" * 60)
    print("\n预设工作流:")
    for name, info in PRESET_WORKFLOWS.items():
        print(f"  - {name}: {info['name']} ({info['description']})")
    print("\n使用方法:")
    print("  cc = create_controls(comfyui_root='D:/Ai/ComfyUI')")
    print("  cc.list_models()")
    print("  cc.run_workflow('ltx_i2v', {'image': 'input.jpg'})")
