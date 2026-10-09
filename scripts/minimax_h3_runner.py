"""
MiniMax H3 视频生成工作流封装
基于ComfyUI API，支持文生视频/图生视频/首尾帧生视频

优化方案（RTX 3080 12GB可稳定运行）：
- MiniMax H3 Mem Eff Sage Attention Patch（显存优化）
- 加速LoRA：minimax_h3_fl2v_turbo_4step_v1.0_768p（4步加速）
- VAE分块解码：tile_size=512, overlap=64, time_size=64, time_overlap=8
- 原生2K分辨率/24fps/原生立体声音频
- Timeline分时间段提示词

依赖节点：
- ComfyUI-MiniMaxH3（官方节点）
- KJNodes（Mem Eff Sage Attention Patch）
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 添加comfy_client到路径
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
from comfy_client import ComfyClient


# ============ 配置预设 ============

@dataclass
class H3OptimizationConfig:
    """H3优化配置"""
    use_mem_eff_attention: bool = True      # 显存高效注意力
    use_turbo_lora: bool = True              # 加速LoRA
    turbo_lora_name: str = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
    turbo_steps: int = 4                      # 加速模式步数
    standard_steps: int = 20                  # 标准模式步数
    use_tiled_vae: bool = True               # 分块VAE解码
    vae_tile_size: int = 512
    vae_overlap: int = 64
    vae_time_size: int = 64
    vae_time_overlap: int = 8
    sampler: str = "res_multistep"
    scheduler: str = "simple"
    cfg: float = 1.0                          # 加速LoRA下CFG=1
    video_fps: int = 24
    video_bit_depth: int = 8


# 预设配置
PRESETS = {
    "turbo_768p": H3OptimizationConfig(
        use_turbo_lora=True,
        turbo_steps=4,
        cfg=1.0,
    ),
    "standard_768p": H3OptimizationConfig(
        use_turbo_lora=False,
        standard_steps=20,
        cfg=6.0,
    ),
    "turbo_2k": H3OptimizationConfig(
        use_turbo_lora=True,
        turbo_steps=4,
        cfg=1.0,
        vae_tile_size=512,
    ),
    "quality_2k": H3OptimizationConfig(
        use_turbo_lora=False,
        standard_steps=30,
        cfg=6.0,
        vae_tile_size=256,
        vae_overlap=32,
    ),
}


# ============ Timeline提示词构建 ============

@dataclass
class TimelineSegment:
    """Timeline时间段"""
    start_time: str      # 如 "0s-1s"
    description: str     # 该时间段的画面描述


def build_timeline_prompt(segments: List[TimelineSegment], overall_prompt: str = "") -> str:
    """
    构建H3 Timeline格式提示词

    Args:
        segments: 时间段列表
        overall_prompt: 整体风格/氛围描述（放在Timeline之前）

    Returns:
        格式化的提示词字符串
    """
    parts = []
    if overall_prompt:
        parts.append(overall_prompt.strip())

    parts.append("Timeline:")
    for seg in segments:
        parts.append(f"[{seg.start_time}] {seg.description}")

    return "\n".join(parts)


# ============ 工作流构建器 ============

class MiniMaxH3WorkflowBuilder:
    """MiniMax H3工作流构建器"""

    def __init__(self, config: H3OptimizationConfig = None):
        self.config = config or PRESETS["turbo_768p"]
        self._node_counter = 0

    def _next_id(self) -> str:
        self._node_counter += 1
        return str(self._node_counter)

    def _base_nodes(self) -> Dict[str, Any]:
        """构建基础节点（模型/CLIP/VAE/优化）"""
        nodes = {}

        # 1. 模型加载
        model_id = self._next_id()
        nodes[model_id] = {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "MiniMaxH3.safetensors",
                "weight_dtype": "bfloat16",
            }
        }

        # 2. CLIP加载
        clip_id = self._next_id()
        nodes[clip_id] = {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "MiniMaxH3_text_encoder.safetensors",
                "type": "sd3",
            }
        }

        # 3. VAE加载
        vae_id = self._next_id()
        nodes[vae_id] = {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "MiniMaxH3_video_vae.safetensors",
            }
        }

        current_model = model_id

        # 4. 显存高效注意力（可选）
        if self.config.use_mem_eff_attention:
            mem_eff_id = self._next_id()
            nodes[mem_eff_id] = {
                "class_type": "MiniMax H3 Mem Eff Sage Attention Patch",
                "inputs": {
                    "model": [current_model, 0],
                }
            }
            current_model = mem_eff_id

        # 5. 加速LoRA（可选）
        if self.config.use_turbo_lora:
            lora_id = self._next_id()
            nodes[lora_id] = {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": [current_model, 0],
                    "lora_name": self.config.turbo_lora_name,
                    "strength_model": 1.0,
                }
            }
            current_model = lora_id

        return {
            "model": current_model,
            "clip": clip_id,
            "vae": vae_id,
            "nodes": nodes,
        }

    def _sampling_nodes(self, model_id: str, positive_id: str, latent_id: str,
                         steps: int = None) -> Tuple[str, Dict[str, Any]]:
        """构建采样节点"""
        nodes = {}
        s = steps or (self.config.turbo_steps if self.config.use_turbo_lora else self.config.standard_steps)

        # 基本引导器
        guid_id = self._next_id()
        nodes[guid_id] = {
            "class_type": "BasicGuider",
            "inputs": {
                "model": [model_id, 0],
                "conditioning": [positive_id, 0],
            }
        }

        # K采样器选择
        ksampler_id = self._next_id()
        nodes[ksampler_id] = {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": self.config.sampler,
            }
        }

        # 基本调度器
        sched_id = self._next_id()
        nodes[sched_id] = {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": self.config.scheduler,
                "steps": s,
                "denoise": 1.0,
            }
        }

        # 自定义采样器（高级）
        custom_sampler_id = self._next_id()
        nodes[custom_sampler_id] = {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [latent_id, 0],
                "guider": [guid_id, 0],
                "sampler": [ksampler_id, 0],
                "sigmas": [sched_id, 0],
                "latent_image": [latent_id, 0],
            }
        }

        return custom_sampler_id, nodes

    def _decode_and_save_nodes(self, vae_id: str, latent_id: str,
                                output_prefix: str = "h3_video") -> Dict[str, Any]:
        """构建VAE解码和视频保存节点"""
        nodes = {}

        if self.config.use_tiled_vae:
            # 分块VAE解码（视频）
            decode_id = self._next_id()
            nodes[decode_id] = {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": [latent_id, 0],
                    "vae": [vae_id, 0],
                    "tile_size": self.config.vae_tile_size,
                    "overlap": self.config.vae_overlap,
                    "time_size": self.config.vae_time_size,
                    "time_overlap": self.config.vae_time_overlap,
                }
            }
        else:
            decode_id = self._next_id()
            nodes[decode_id] = {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": [latent_id, 0],
                    "vae": [vae_id, 0],
                }
            }

        # 音频VAE解码
        audio_decode_id = self._next_id()
        nodes[audio_decode_id] = {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [latent_id, 0],
                "vae": [vae_id, 0],
            }
        }

        # 创建视频
        video_id = self._next_id()
        nodes[video_id] = {
            "class_type": "Create Video",
            "inputs": {
                "images": [decode_id, 0],
                "audio": [audio_decode_id, 0],
                "fps": self.config.video_fps,
                "bit_depth": self.config.video_bit_depth,
            }
        }

        return nodes

    def build_text_to_video(self, prompt: str, width: int = 1344, height: int = 768,
                             frames: int = 81, output_prefix: str = "h3_t2v") -> Dict[str, Any]:
        """
        构建文生视频工作流

        Args:
            prompt: 提示词（支持Timeline格式）
            width: 宽度
            height: 高度
            frames: 帧数（24fps下，81帧≈3.4秒）
            output_prefix: 输出文件名前缀

        Returns:
            ComfyUI工作流JSON
        """
        self._node_counter = 0
        base = self._base_nodes()
        workflow = base["nodes"]

        # 文生视频节点
        t2v_id = self._next_id()
        workflow[t2v_id] = {
            "class_type": "Text to Video (MiniMax H3)",
            "inputs": {
                "model": [base["model"], 0],
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_frames": frames,
            }
        }

        # 随机噪声
        noise_id = self._next_id()
        workflow[noise_id] = {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": int(time.time()) % (2**31),
            }
        }

        # 采样
        sample_out, sample_nodes = self._sampling_nodes(
            base["model"], t2v_id, noise_id
        )
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], sample_out, output_prefix)
        workflow.update(decode_nodes)

        return workflow

    def build_image_to_video(self, prompt: str, image_path: str,
                              width: int = 1344, height: int = 768,
                              frames: int = 81, output_prefix: str = "h3_i2v") -> Dict[str, Any]:
        """
        构建图生视频工作流

        Args:
            prompt: 提示词（支持Timeline格式）
            image_path: 首帧图片路径
            width: 宽度
            height: 高度
            frames: 帧数
            output_prefix: 输出文件名前缀

        Returns:
            ComfyUI工作流JSON
        """
        self._node_counter = 0
        base = self._base_nodes()
        workflow = base["nodes"]

        # 加载图片
        img_id = self._next_id()
        workflow[img_id] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": os.path.basename(image_path),
            }
        }

        # 图生视频节点
        i2v_id = self._next_id()
        workflow[i2v_id] = {
            "class_type": "Image to Video (MiniMax H3)",
            "inputs": {
                "model": [base["model"], 0],
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "first_frame": [img_id, 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_frames": frames,
            }
        }

        # 随机噪声
        noise_id = self._next_id()
        workflow[noise_id] = {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": int(time.time()) % (2**31),
            }
        }

        # 采样
        sample_out, sample_nodes = self._sampling_nodes(base["model"], i2v_id, noise_id)
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], sample_out, output_prefix)
        workflow.update(decode_nodes)

        return workflow

    def build_first_last_to_video(self, prompt: str, first_frame_path: str,
                                    last_frame_path: str,
                                    width: int = 1344, height: int = 768,
                                    frames: int = 81, output_prefix: str = "h3_fl2v") -> Dict[str, Any]:
        """
        构建首尾帧生视频工作流

        Args:
            prompt: 提示词（支持Timeline格式）
            first_frame_path: 首帧图片路径
            last_frame_path: 尾帧图片路径
            width: 宽度
            height: 高度
            frames: 帧数
            output_prefix: 输出文件名前缀

        Returns:
            ComfyUI工作流JSON
        """
        self._node_counter = 0
        base = self._base_nodes()
        workflow = base["nodes"]

        # 加载首帧
        first_id = self._next_id()
        workflow[first_id] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": os.path.basename(first_frame_path),
            }
        }

        # 加载尾帧
        last_id = self._next_id()
        workflow[last_id] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": os.path.basename(last_frame_path),
            }
        }

        # 首尾帧生视频节点
        fl2v_id = self._next_id()
        workflow[fl2v_id] = {
            "class_type": "Image to Video (MiniMax H3)",
            "inputs": {
                "model": [base["model"], 0],
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "first_frame": [first_id, 0],
                "last_frame": [last_id, 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_frames": frames,
            }
        }

        # 随机噪声
        noise_id = self._next_id()
        workflow[noise_id] = {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": int(time.time()) % (2**31),
            }
        }

        # 采样
        sample_out, sample_nodes = self._sampling_nodes(base["model"], fl2v_id, noise_id)
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], sample_out, output_prefix)
        workflow.update(decode_nodes)

        return workflow


# ============ 执行器 ============

class MiniMaxH3Runner:
    """MiniMax H3视频生成执行器"""

    def __init__(self, server_addr: str = "127.0.0.1:8188",
                 output_dir: str = None,
                 preset: str = "turbo_768p"):
        """
        初始化执行器

        Args:
            server_addr: ComfyUI服务器地址
            output_dir: 输出目录
            preset: 优化预设名称
        """
        self.client = ComfyClient(server_addr=server_addr)
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "h3_output"
        )
        os.makedirs(self.output_dir, exist_ok=True)

        self.config = PRESETS.get(preset, PRESETS["turbo_768p"])
        self.builder = MiniMaxH3WorkflowBuilder(self.config)

    def is_available(self) -> bool:
        """检查ComfyUI是否可用"""
        return self.client.is_running()

    def text_to_video(self, prompt: str, width: int = 1344, height: int = 768,
                      frames: int = 81, timeout: int = 600) -> Optional[str]:
        """
        文生视频

        Args:
            prompt: 提示词
            width: 宽度
            height: 高度
            frames: 帧数
            timeout: 超时时间（秒）

        Returns:
            输出视频路径，失败返回None
        """
        workflow = self.builder.build_text_to_video(prompt, width, height, frames)
        return self._execute(workflow, timeout)

    def image_to_video(self, prompt: str, image_path: str,
                        width: int = 1344, height: int = 768,
                        frames: int = 81, timeout: int = 600) -> Optional[str]:
        """
        图生视频

        Args:
            prompt: 提示词
            image_path: 首帧图片路径
            width: 宽度
            height: 高度
            frames: 帧数
            timeout: 超时时间

        Returns:
            输出视频路径
        """
        workflow = self.builder.build_image_to_video(prompt, image_path, width, height, frames)
        return self._execute(workflow, timeout)

    def first_last_to_video(self, prompt: str, first_frame_path: str,
                             last_frame_path: str,
                             width: int = 1344, height: int = 768,
                             frames: int = 81, timeout: int = 600) -> Optional[str]:
        """
        首尾帧生视频

        Args:
            prompt: 提示词
            first_frame_path: 首帧图片路径
            last_frame_path: 尾帧图片路径
            width: 宽度
            height: 高度
            frames: 帧数
            timeout: 超时时间

        Returns:
            输出视频路径
        """
        workflow = self.builder.build_first_last_to_video(
            prompt, first_frame_path, last_frame_path, width, height, frames
        )
        return self._execute(workflow, timeout)

    def _execute(self, workflow: Dict[str, Any], timeout: int = 600) -> Optional[str]:
        """执行工作流并等待结果"""
        try:
            # 提交工作流
            prompt_id = self.client.queue_prompt(workflow)
            if not prompt_id:
                logger.error("提交工作流失败")
                return None

            logger.info(f"工作流已提交，prompt_id={prompt_id}")

            # 等待完成
            result = self.client.wait_for_completion(prompt_id, timeout=timeout)
            if not result:
                logger.error("工作流执行超时或失败")
                return None

            # 获取输出
            outputs = self.client.get_outputs(prompt_id)
            if outputs:
                for node_id, output in outputs.items():
                    if "videos" in output:
                        for video in output["videos"]:
                            video_path = os.path.join(self.output_dir, video.get("filename", ""))
                            logger.info(f"视频已生成: {video_path}")
                            return video_path

            logger.warning("未找到视频输出")
            return None

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return None


# ============ 便捷函数 ============

_default_runner = None

def get_runner(preset: str = "turbo_768p") -> MiniMaxH3Runner:
    global _default_runner
    if _default_runner is None:
        _default_runner = MiniMaxH3Runner(preset=preset)
    return _default_runner


def list_presets() -> Dict[str, H3OptimizationConfig]:
    """列出所有预设"""
    return PRESETS


def main():
    """测试"""
    print("=== MiniMax H3 工作流封装 ===")
    print(f"预设: {list(PRESETS.keys())}")
    print()

    # 测试工作流构建
    builder = MiniMaxH3WorkflowBuilder()

    # T2V
    t2v = builder.build_text_to_video("a cat walking on the grass", 1344, 768, 81)
    print(f"文生视频工作流: {len(t2v)}个节点")

    # I2V
    i2v = builder.build_image_to_video("a cat walking", "test.png", 1344, 768, 81)
    print(f"图生视频工作流: {len(i2v)}个节点")

    # FL2V
    fl2v = builder.build_first_last_to_video("transition", "first.png", "last.png", 1344, 768, 81)
    print(f"首尾帧生视频工作流: {len(fl2v)}个节点")

    # Timeline测试
    timeline = build_timeline_prompt([
        TimelineSegment("0s-1s", "a cat appears"),
        TimelineSegment("1s-2s", "cat starts walking"),
        TimelineSegment("2s-3s", "cat walks away"),
    ], "cinematic style, warm lighting")
    print(f"\nTimeline提示词:\n{timeline}")

    print("\nMiniMax H3 模块就绪")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
