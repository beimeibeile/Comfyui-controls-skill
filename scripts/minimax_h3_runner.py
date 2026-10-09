"""
MiniMax H3 视频生成工作流封装
基于ComfyUI API，支持文生视频/图生视频/首尾帧生视频/参考驱动生成

模型版本：
- FL2VA：高质量版本，支持T2V/I2V/FL2V，视觉和音频质量最佳
- Ref2VA：参考驱动版本，支持9图+3视频+3音频参考+唇形同步，画质略低
- Hybrid：社区混合版，FL2VA画质+Ref2VA参考能力（如已下载）

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


# ============ 模型版本定义 ============

# FL2VA：高质量版本（First/Last to Video + Audio）
# - 支持 T2V（纯文本）、I2V（首帧）、FL2V（首尾帧）
# - 视觉和音频质量最佳
# - 不支持多参考输入
MODEL_FL2VA = "fl2va"

# Ref2VA：参考驱动版本（Reference to Video + Audio）
# - 支持 最多9张图像 + 3段视频 + 3段音频参考
# - 支持唇形同步（lip-sync）
# - 支持角色/动作/相机/声音参考迁移
# - 原始输出画质略低于FL2VA
MODEL_REF2VA = "ref2va"

# Hybrid：社区混合版
# - 合并FL2VA的高质量 + Ref2VA的参考支持
# - 单一checkpoint，需单独下载
MODEL_HYBRID = "hybrid"

# 模型文件名映射（ComfyUI models/diffusion_models/ 目录下）
MODEL_FILES = {
    MODEL_FL2VA: "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    MODEL_REF2VA: "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    MODEL_HYBRID: "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
}

# CLIP文本编码器
CLIP_FILE = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"

# VAE文件
VIDEO_VAE_FILE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE_FILE = "minimax_h3_audio_vae_fp32.safetensors"

# 各版本支持的模式
MODEL_MODES = {
    MODEL_FL2VA: ["t2v", "i2v", "fl2v"],
    MODEL_REF2VA: ["t2v", "i2v", "fl2v", "ref2v"],  # ref2v=参考驱动
    MODEL_HYBRID: ["t2v", "i2v", "fl2v", "ref2v"],
}


# ============ 配置预设 ============

@dataclass
class H3OptimizationConfig:
    """H3优化配置"""
    model_variant: str = MODEL_FL2VA       # 模型版本：fl2va/ref2va/hybrid
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
        model_variant=MODEL_FL2VA,
        use_turbo_lora=True,
        turbo_steps=4,
        cfg=1.0,
    ),
    "standard_768p": H3OptimizationConfig(
        model_variant=MODEL_FL2VA,
        use_turbo_lora=False,
        standard_steps=20,
        cfg=6.0,
    ),
    "turbo_2k": H3OptimizationConfig(
        model_variant=MODEL_FL2VA,
        use_turbo_lora=True,
        turbo_steps=4,
        cfg=1.0,
        vae_tile_size=512,
    ),
    "quality_2k": H3OptimizationConfig(
        model_variant=MODEL_FL2VA,
        use_turbo_lora=False,
        standard_steps=30,
        cfg=6.0,
        vae_tile_size=256,
        vae_overlap=32,
    ),
    "ref2va_turbo": H3OptimizationConfig(
        model_variant=MODEL_REF2VA,
        use_turbo_lora=True,
        turbo_steps=4,
        cfg=1.0,
    ),
    "ref2va_standard": H3OptimizationConfig(
        model_variant=MODEL_REF2VA,
        use_turbo_lora=False,
        standard_steps=20,
        cfg=6.0,
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

        # 根据版本选择模型文件
        model_file = MODEL_FILES.get(self.config.model_variant, MODEL_FILES[MODEL_FL2VA])

        # 1. 模型加载
        model_id = self._next_id()
        nodes[model_id] = {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": model_file,
                "weight_dtype": "default",
            }
        }

        # 2. CLIP加载
        clip_id = self._next_id()
        nodes[clip_id] = {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": CLIP_FILE,
                "type": "minimax",
            }
        }

        # 3. 视频VAE加载
        vae_id = self._next_id()
        nodes[vae_id] = {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": VIDEO_VAE_FILE,
            }
        }

        # 4. 音频VAE加载
        audio_vae_id = self._next_id()
        nodes[audio_vae_id] = {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": AUDIO_VAE_FILE,
            }
        }

        current_model = model_id

        # 4. 显存高效注意力（可选）
        if self.config.use_mem_eff_attention:
            mem_eff_id = self._next_id()
            nodes[mem_eff_id] = {
                "class_type": "MiniMaxH3MemoryEfficientSageAttentionPatch",
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
            "audio_vae": audio_vae_id,
            "nodes": nodes,
        }

    def _sampling_nodes(self, model_id: str, positive_id: str, latent_id: str,
                         noise_id: str, steps: int = None) -> Tuple[str, Dict[str, Any]]:
        """构建采样节点

        Args:
            model_id: 模型节点ID
            positive_id: positive conditioning节点ID（MiniMaxH3ImageToVideo输出index0）
            latent_id: latent节点ID（MiniMaxH3ImageToVideo输出index1）
            noise_id: 噪声节点ID（RandomNoise输出）
            steps: 采样步数
        """
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
                "model": [model_id, 0],
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
                "noise": [noise_id, 0],
                "guider": [guid_id, 0],
                "sampler": [ksampler_id, 0],
                "sigmas": [sched_id, 0],
                "latent_image": [latent_id, 1],
            }
        }

        return custom_sampler_id, nodes

    def _decode_and_save_nodes(self, vae_id: str, audio_vae_id: str, latent_id: str,
                                output_prefix: str = "h3_video") -> Dict[str, Any]:
        """构建VAE解码和视频保存节点"""
        nodes = {}

        if self.config.use_tiled_vae:
            # 分块VAE解码（视频）
            decode_id = self._next_id()
            nodes[decode_id] = {
                "class_type": "VAEDecodeTiled",
                "inputs": {
                    "samples": [latent_id, 0],
                    "vae": [vae_id, 0],
                    "tile_size": self.config.vae_tile_size,
                    "overlap": self.config.vae_overlap,
                    "temporal_size": self.config.vae_time_size,
                    "temporal_overlap": self.config.vae_time_overlap,
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

        # 音频VAE解码（使用音频VAE，输出AUDIO类型）
        audio_decode_id = self._next_id()
        nodes[audio_decode_id] = {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": [latent_id, 0],
                "vae": [audio_vae_id, 0],
            }
        }

        # 创建视频
        video_id = self._next_id()
        nodes[video_id] = {
            "class_type": "CreateVideo",
            "inputs": {
                "images": [decode_id, 0],
                "audio": [audio_decode_id, 0],
                "fps": self.config.video_fps,
                "bit_depth": self.config.video_bit_depth,
            }
        }

        # 保存视频（输出节点）
        save_id = self._next_id()
        nodes[save_id] = {
            "class_type": "SaveVideo",
            "inputs": {
                "video": [video_id, 0],
                "filename_prefix": output_prefix,
                "format": "auto",
                "codec": "auto",
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

        # 文生视频节点（使用MiniMaxH3ImageToVideo，不传首帧即为文生视频）
        t2v_id = self._next_id()
        workflow[t2v_id] = {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "length": frames,
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

        # 采样（t2v_id输出index0=positive, index1=latent）
        sample_out, sample_nodes = self._sampling_nodes(
            base["model"], t2v_id, t2v_id, noise_id
        )
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], base["audio_vae"], sample_out, output_prefix)
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
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "first_frame": [img_id, 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "length": frames,
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

        # 采样（i2v_id输出index0=positive, index1=latent）
        sample_out, sample_nodes = self._sampling_nodes(
            base["model"], i2v_id, i2v_id, noise_id
        )
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], base["audio_vae"], sample_out, output_prefix)
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
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": [base["clip"], 0],
                "vae": [base["vae"], 0],
                "first_frame": [first_id, 0],
                "last_frame": [last_id, 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "length": frames,
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

        # 采样（fl2v_id输出index0=positive, index1=latent）
        sample_out, sample_nodes = self._sampling_nodes(
            base["model"], fl2v_id, fl2v_id, noise_id
        )
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], base["audio_vae"], sample_out, output_prefix)
        workflow.update(decode_nodes)

        return workflow

    def build_reference_to_video(self, prompt: str,
                                   reference_images: List[str],
                                   reference_videos: List[str],
                                   reference_audios: List[str],
                                   width: int = 1344, height: int = 768,
                                   frames: int = 81) -> Dict[str, Any]:
        """
        构建参考驱动生视频工作流（Ref2VA模式）
        支持最多9张图像 + 3段视频 + 3段音频参考

        Args:
            prompt: 提示词
            reference_images: 参考图像路径列表
            reference_videos: 参考视频路径列表
            reference_audios: 参考音频路径列表
            width: 宽度
            height: 高度
            frames: 帧数

        Returns:
            ComfyUI工作流字典
        """
        workflow = {}
        base = self._base_nodes()
        workflow.update(base["nodes"])

        output_prefix = f"h3_ref2v_{int(time.time())}"

        # 加载参考图像（最多9张）
        ref_image_ids = []
        for i, img_path in enumerate(reference_images[:9]):
            img_id = self._next_id()
            workflow[img_id] = {
                "class_type": "LoadImage",
                "inputs": {"image": os.path.basename(img_path)}
            }
            ref_image_ids.append(img_id)

        # 加载参考视频（最多3段）
        ref_video_ids = []
        for i, vid_path in enumerate(reference_videos[:3]):
            vid_id = self._next_id()
            workflow[vid_id] = {
                "class_type": "Load Video",
                "inputs": {"video": os.path.basename(vid_path)}
            }
            ref_video_ids.append(vid_id)

        # 加载参考音频（最多3段）
        ref_audio_ids = []
        for i, aud_path in enumerate(reference_audios[:3]):
            aud_id = self._next_id()
            workflow[aud_id] = {
                "class_type": "Load Audio",
                "inputs": {"audio": os.path.basename(aud_path)}
            }
            ref_audio_ids.append(aud_id)

        # 参考驱动生视频节点（Ref2VA）
        ref2v_inputs = {
            "clip": [base["clip"], 0],
            "vae": [base["vae"], 0],
            "audio_vae": [base["vae"], 0],
            "prompt": prompt,
            "width": width,
            "height": height,
            "length": frames,
        }

        # 连接参考图像（Autogrow输入：ref_image_0, ref_image_1, ...）
        for i, img_id in enumerate(ref_image_ids):
            ref2v_inputs[f"ref_image_{i}"] = [img_id, 0]

        # 连接参考视频（Autogrow输入：ref_video_0, ref_video_1, ...）
        for i, vid_id in enumerate(ref_video_ids):
            ref2v_inputs[f"ref_video_{i}"] = [vid_id, 0]

        # 连接独立参考音频（Autogrow输入：ref_audio_0, ref_audio_1, ...）
        for i, aud_id in enumerate(ref_audio_ids):
            ref2v_inputs[f"ref_audio_{i}"] = [aud_id, 0]

        ref2v_id = self._next_id()
        workflow[ref2v_id] = {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": ref2v_inputs
        }

        # 随机噪声
        noise_id = self._next_id()
        workflow[noise_id] = {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(time.time()) % (2**31)}
        }

        # 采样（ref2v_id输出index0=positive, index1=latent）
        sample_out, sample_nodes = self._sampling_nodes(
            base["model"], ref2v_id, ref2v_id, noise_id
        )
        workflow.update(sample_nodes)

        # 解码和保存
        decode_nodes = self._decode_and_save_nodes(base["vae"], base["audio_vae"], sample_out, output_prefix)
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

    def reference_to_video(self, prompt: str,
                            reference_images: List[str] = None,
                            reference_videos: List[str] = None,
                            reference_audios: List[str] = None,
                            width: int = 1344, height: int = 768,
                            frames: int = 81, timeout: int = 600) -> Optional[str]:
        """
        参考驱动生视频（Ref2VA模式）
        支持最多9张图像 + 3段视频 + 3段音频参考，支持唇形同步

        Args:
            prompt: 提示词
            reference_images: 参考图像路径列表（最多9张）
            reference_videos: 参考视频路径列表（最多3段，每段2-15秒）
            reference_audios: 参考音频路径列表（最多3段，须与图像/视频一同输入）
            width: 宽度
            height: 高度
            frames: 帧数
            timeout: 超时时间

        Returns:
            输出视频路径，失败返回None

        Note:
            此方法需要Ref2VA或Hybrid版本模型，FL2VA不支持参考驱动
        """
        if self.config.model_variant == MODEL_FL2VA:
            logger.warning("FL2VA版本不支持参考驱动生成，自动切换为图生视频（首帧参考）")
            if reference_images and len(reference_images) > 0:
                return self.image_to_video(prompt, reference_images[0], width, height, frames, timeout)
            return self.text_to_video(prompt, width, height, frames, timeout)

        workflow = self.builder.build_reference_to_video(
            prompt, reference_images or [], reference_videos or [],
            reference_audios or [], width, height, frames
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
            history = self.client.wait_for_completion(prompt_id, timeout=timeout)
            if not history:
                logger.error("工作流执行超时或失败")
                return None

            # 从history中获取输出
            outputs = history.get("outputs", {})
            if outputs:
                for node_id, output in outputs.items():
                    # SaveVideo节点输出格式为 "images" + "animated: [True]"
                    if "images" in output and output.get("animated", [False])[0]:
                        for video in output["images"]:
                            filename = video.get("filename", "")
                            subfolder = video.get("subfolder", "")
                            # ComfyUI output目录
                            comfy_output = r"D:\Ai\ComfyUI-aki-v3.2\ComfyUI\output"
                            if subfolder:
                                src_path = os.path.join(comfy_output, subfolder, filename)
                            else:
                                src_path = os.path.join(comfy_output, filename)

                            if os.path.exists(src_path):
                                # 复制到runner的output_dir
                                os.makedirs(self.output_dir, exist_ok=True)
                                dst_path = os.path.join(self.output_dir, filename)
                                import shutil
                                shutil.copy2(src_path, dst_path)
                                logger.info(f"视频已生成: {dst_path}")
                                return dst_path
                            else:
                                logger.warning(f"视频文件不存在: {src_path}")
                                # 尝试直接返回ComfyUI中的路径
                                return src_path

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
