"""
批量生成器
批量生成、队列管理、进度监控、结果归档
"""
import os
import json
import time
from typing import Dict, List, Optional, Callable


class BatchGenerator:
    """批量生成器"""

    def __init__(self, output_dir: str = None, api=None):
        self.output_dir = output_dir or os.environ.get("DEFAULT_OUTPUT_DIR", "./output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.api = api
        self._queue = []
        self._results = {"success": [], "failed": [], "pending": []}

    def _get_api(self):
        if self.api is None:
            from cap_api_wrapper import ComfyAPI
            self.api = ComfyAPI()
        return self.api

    def generate(self, workflow: str, prompts: List[str],
                 output_dir: str = None, quality_check: bool = False,
                 on_progress: Callable = None) -> Dict:
        """
        批量生成

        Args:
            workflow: 工作流名称
            prompts: 提示词列表
            output_dir: 输出目录
            quality_check: 是否启用质量检查
            on_progress: 进度回调函数

        Returns:
            生成结果字典
        """
        out_dir = output_dir or self.output_dir
        os.makedirs(out_dir, exist_ok=True)

        api = self._get_api()
        results = {"success": [], "failed": [], "total": len(prompts)}

        for i, prompt in enumerate(prompts):
            try:
                # 构建工作流（简化版，实际需要根据workflow名称加载模板）
                workflow_data = self._build_workflow(workflow, prompt)

                # 提交到队列
                queue_result = api.queue_prompt(workflow_data)
                prompt_id = queue_result.get("prompt_id")

                if prompt_id:
                    # 等待完成
                    result = api.wait_for_prompt(prompt_id, timeout=300)
                    if result:
                        # 下载结果
                        output_files = self._download_results(result, out_dir, i)
                        results["success"].append({
                            "index": i,
                            "prompt": prompt,
                            "files": output_files,
                        })
                    else:
                        results["failed"].append({"index": i, "prompt": prompt, "error": "timeout"})
                else:
                    results["failed"].append({"index": i, "prompt": prompt, "error": "queue_failed"})

            except Exception as e:
                results["failed"].append({"index": i, "prompt": prompt, "error": str(e)})

            # 进度回调
            if on_progress:
                on_progress(i + 1, len(prompts), results)

        return results

    def _build_workflow(self, workflow_name: str, prompt: str) -> Dict:
        """构建工作流（简化版）"""
        # 实际实现需要从WorkflowManager加载模板并应用参数
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": int(time.time()),
                    "steps": 20,
                    "cfg": 8.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "bad quality", "clip": ["4", 1]}
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "batch", "images": ["8", 0]}
            }
        }

    def _download_results(self, result: Dict, output_dir: str, index: int) -> List[str]:
        """下载生成结果"""
        api = self._get_api()
        files = []
        outputs = result.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    try:
                        img_data = api.get_image(
                            img["filename"],
                            img.get("subfolder", ""),
                            img.get("type", "output")
                        )
                        out_path = os.path.join(output_dir, f"batch_{index:04d}_{img['filename']}")
                        with open(out_path, "wb") as f:
                            f.write(img_data)
                        files.append(out_path)
                    except Exception as e:
                        print(f"  下载失败: {e}")
        return files

    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        api = self._get_api()
        return api.get_queue()


if __name__ == "__main__":
    bg = BatchGenerator()
    print(f"输出目录: {bg.output_dir}")
    print(f"API在线: {'✅' if bg._get_api().is_online() else '❌'}")
