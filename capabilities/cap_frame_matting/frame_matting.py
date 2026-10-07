#!/usr/bin/env python3
"""
P1-3: ComfyUI逐帧抠图管线 v1.0
从视频或图片序列中逐帧提取前景，生成带Alpha通道的PNG序列，
可选合成ProRes 4444透明背景视频。

支持后端：
- comfyui: 通过ComfyUI API调用抠图模型（BiRefNet/RMBG/SAM等）
- rembg: 本地rembg库（U2Net/ISNet等）
- auto: 自动选择可用后端

用法:
    python frame_matting.py <输入视频或图片目录> <输出目录> [--backend auto] [--prores]
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 外部工具路径
FFMPEG = os.environ.get("AVE_FFMPEG", shutil.which("ffmpeg") or r"D:\Ai\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")
FFPROBE = os.environ.get("AVE_FFPROBE", shutil.which("ffprobe") or r"D:\Ai\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


class FrameMattingPipeline:
    """逐帧抠图管线"""

    def __init__(self, output_dir: str, backend: str = "auto",
                 comfyui_url: str = COMFYUI_URL):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir = self.output_dir / "frames"
        self.matted_dir = self.output_dir / "matted"
        self.frames_dir.mkdir(exist_ok=True)
        self.matted_dir.mkdir(exist_ok=True)
        self.backend = backend
        self.comfyui_url = comfyui_url.rstrip("/")
        self._comfyui_available = None

    def detect_backend(self) -> str:
        """自动检测可用后端"""
        if self.backend != "auto":
            return self.backend

        # 优先ComfyUI（质量更好）
        if self._check_comfyui():
            return "comfyui"

        # 回退rembg
        try:
            import rembg
            return "rembg"
        except ImportError:
            pass

        return "none"

    def _check_comfyui(self) -> bool:
        """检查ComfyUI是否可用"""
        if self._comfyui_available is not None:
            return self._comfyui_available
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.comfyui_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._comfyui_available = resp.status == 200
        except Exception:
            self._comfyui_available = False
        return self._comfyui_available

    def extract_frames(self, input_path: str, fps: int = 30) -> int:
        """从视频提取帧，或复制图片序列

        Returns:
            提取的帧数
        """
        input_path = Path(input_path)

        if input_path.is_dir():
            # 图片序列：复制到frames目录
            exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
            files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in exts])
            for i, f in enumerate(files):
                dst = self.frames_dir / f"frame_{i:04d}{f.suffix.lower()}"
                shutil.copy2(f, dst)
            return len(files)

        # 视频：用ffmpeg提取帧
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-vf", f"fps={fps}",
            str(self.frames_dir / "frame_%04d.png"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"帧提取失败: {result.stderr[-500:]}")

        frames = list(self.frames_dir.glob("frame_*.png"))
        return len(frames)

    def mat_frame_comfyui(self, input_path: str, output_path: str) -> bool:
        """用ComfyUI抠图单帧"""
        try:
            import urllib.request

            # 上传图片
            with open(input_path, "rb") as f:
                img_data = f.read()

            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="image"; filename="input.png"\r\n'
                f"Content-Type: image/png\r\n\r\n"
            ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()

            req = urllib.request.Request(
                f"{self.comfyui_url}/upload/image",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                upload_result = json.loads(resp.read())

            filename = upload_result.get("name")
            if not filename:
                return False

            # 构建抠图工作流（使用BiRefNet或通用分割节点）
            workflow = self._build_matting_workflow(filename)

            # 提交工作流
            req = urllib.request.Request(
                f"{self.comfyui_url}/prompt",
                data=json.dumps({"prompt": workflow}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                prompt_result = json.loads(resp.read())

            prompt_id = prompt_result.get("prompt_id")
            if not prompt_id:
                return False

            # 等待完成
            import time
            for _ in range(120):  # 最多等2分钟
                time.sleep(1)
                try:
                    req = urllib.request.Request(f"{self.comfyui_url}/history/{prompt_id}")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        history = json.loads(resp.read())
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        for node_id, node_out in outputs.items():
                            if "images" in node_out:
                                img_name = node_out["images"][0]["filename"]
                                # 下载结果
                                req = urllib.request.Request(
                                    f"{self.comfyui_url}/view?filename={img_name}&type=output"
                                )
                                with urllib.request.urlopen(req, timeout=30) as resp:
                                    with open(output_path, "wb") as f:
                                        f.write(resp.read())
                                return True
                except Exception:
                    continue
            return False

        except Exception as e:
            print(f"  ComfyUI抠图失败: {e}")
            return False

    def _build_matting_workflow(self, image_filename: str) -> Dict:
        """构建ComfyUI抠图工作流

        尝试使用可用的抠图节点，回退到简单的色彩范围抠图
        """
        # 基础工作流：加载图片 -> 抠图 -> 保存
        # 实际使用时需要根据ComfyUI安装的节点调整
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": image_filename},
            },
            "2": {
                "class_type": "ImageRemoveBackground",  # 通用抠图节点名
                "inputs": {"images": ["1", 0]},
            },
            "3": {
                "class_type": "SaveImage",
                "inputs": {"images": ["2", 0], "filename_prefix": "matted"},
            },
        }
        return workflow

    def mat_frame_rembg(self, input_path: str, output_path: str) -> bool:
        """用rembg本地抠图单帧"""
        try:
            from rembg import remove
            from PIL import Image

            input_img = Image.open(input_path)
            output_img = remove(input_img)
            output_img.save(output_path, "PNG")
            return True
        except ImportError:
            print("  rembg未安装，跳过")
            return False
        except Exception as e:
            print(f"  rembg抠图失败: {e}")
            return False

    def process(self, input_path: str, fps: int = 30,
                max_frames: Optional[int] = None) -> Dict[str, Any]:
        """执行完整抠图管线

        Args:
            input_path: 输入视频路径或图片目录
            fps: 提取帧率（视频输入时）
            max_frames: 最大处理帧数（None=全部）

        Returns:
            处理结果统计
        """
        backend = self.detect_backend()
        print(f"使用后端: {backend}")

        if backend == "none":
            return {"success": False, "error": "无可用抠图后端（ComfyUI未运行且rembg未安装）"}

        # 1. 提取帧
        print("[1/3] 提取帧...")
        frame_count = self.extract_frames(input_path, fps)
        print(f"  提取了 {frame_count} 帧")

        if max_frames:
            frame_count = min(frame_count, max_frames)

        # 2. 逐帧抠图
        print(f"[2/3] 逐帧抠图（{frame_count}帧）...")
        success_count = 0
        frames = sorted(self.frames_dir.glob("frame_*.png"))[:frame_count]

        for i, frame in enumerate(frames):
            output_path = self.matted_dir / f"matted_{i:04d}.png"
            if backend == "comfyui":
                ok = self.mat_frame_comfyui(str(frame), str(output_path))
            else:
                ok = self.mat_frame_rembg(str(frame), str(output_path))

            if ok:
                success_count += 1
            if (i + 1) % 10 == 0 or i == len(frames) - 1:
                print(f"  进度: {i+1}/{frame_count} (成功{success_count})")

        # 3. 结果
        result = {
            "success": success_count > 0,
            "backend": backend,
            "total_frames": frame_count,
            "success_frames": success_count,
            "matted_dir": str(self.matted_dir),
        }

        print(f"[3/3] 完成: {success_count}/{frame_count} 帧抠图成功")
        return result

    def compose_prores(self, output_name: str = "matted_prores4444.mov",
                       fps: int = 30) -> Optional[str]:
        """将抠图后的PNG序列合成为ProRes 4444视频

        Returns:
            输出文件路径，失败返回None
        """
        matted_files = sorted(self.matted_dir.glob("matted_*.png"))
        if not matted_files:
            print("没有抠图后的帧，无法合成")
            return None

        output_path = str(self.output_dir / output_name)
        cmd = [
            FFMPEG, "-y",
            "-framerate", str(fps),
            "-i", str(self.matted_dir / "matted_%04d.png"),
            "-c:v", "prores_ks",
            "-profile:v", "4",
            "-pix_fmt", "yuva444p12le",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ProRes合成失败: {result.stderr[-500:]}")
            return None

        print(f"ProRes 4444合成成功: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description="逐帧抠图管线")
    parser.add_argument("input", help="输入视频路径或图片目录")
    parser.add_argument("output", help="输出目录")
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "comfyui", "rembg"],
                        help="抠图后端")
    parser.add_argument("--fps", type=int, default=30, help="提取帧率")
    parser.add_argument("--max-frames", type=int, default=None, help="最大处理帧数")
    parser.add_argument("--prores", action="store_true", help="合成ProRes 4444视频")
    args = parser.parse_args()

    pipeline = FrameMattingPipeline(args.output, backend=args.backend)
    result = pipeline.process(args.input, fps=args.fps, max_frames=args.max_frames)

    print("\n=== 结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.prores and result["success"]:
        pipeline.compose_prores(fps=args.fps)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
