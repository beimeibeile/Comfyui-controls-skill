"""
ComfyUI API 统一封装
屏蔽ComfyUI版本差异，提供统一接口
"""
import os
import json
import time
import uuid
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Any


class ComfyAPI:
    """ComfyUI API 统一封装"""

    def __init__(self, address: str = None, client_id: str = None):
        self.address = address or os.environ.get("COMFYUI_ADDRESS", "127.0.0.1:8188")
        self.client_id = client_id or str(uuid.uuid4())
        self.base_url = f"http://{self.address}"

    def _request(self, endpoint: str, method: str = "GET", data: dict = None) -> Any:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        if method == "GET":
            if data:
                url += "?" + urllib.parse.urlencode(data)
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
                                          headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_system_stats(self) -> Dict:
        """获取系统状态（GPU/内存/队列）"""
        try:
            return self._request("/system_stats")
        except Exception as e:
            return {"error": str(e), "status": "offline"}

    def get_queue(self) -> Dict:
        """获取队列状态"""
        return self._request("/queue")

    def get_history(self, max_items: int = 100) -> Dict:
        """获取历史记录"""
        return self._request("/history", data={"max_items": max_items})

    def queue_prompt(self, prompt: Dict) -> Dict:
        """提交提示词到队列"""
        payload = {
            "prompt": prompt,
            "client_id": self.client_id,
        }
        return self._request("/prompt", method="POST", data=payload)

    def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """获取生成的图片"""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url = f"{self.base_url}/view?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read()

    def get_node_defs(self) -> Dict:
        """获取所有节点定义"""
        return self._request("/object_info")

    def interrupt(self) -> Dict:
        """中断当前执行"""
        return self._request("/interrupt", method="POST")

    def free_memory(self) -> Dict:
        """释放显存"""
        return self._request("/free", method="POST")

    def wait_for_prompt(self, prompt_id: str, timeout: int = 300, poll_interval: float = 1.0) -> Optional[Dict]:
        """等待提示词执行完成"""
        start = time.time()
        while time.time() - start < timeout:
            history = self.get_history()
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(poll_interval)
        return None

    def is_online(self) -> bool:
        """检查ComfyUI是否在线"""
        try:
            stats = self.get_system_stats()
            return "error" not in stats
        except Exception:
            return False

    def get_available_models(self, model_type: str = "checkpoints") -> List[str]:
        """获取可用模型列表"""
        try:
            node_defs = self.get_node_defs()
            if model_type == "checkpoints" and "CheckpointLoaderSimple" in node_defs:
                return node_defs["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            if model_type == "loras" and "LoraLoader" in node_defs:
                return node_defs["LoraLoader"]["input"]["required"]["lora_name"][0]
            if model_type == "vaes" and "VAELoader" in node_defs:
                return node_defs["VAELoader"]["input"]["required"]["vae_name"][0]
        except Exception:
            pass
        return []


if __name__ == "__main__":
    api = ComfyAPI()
    print(f"ComfyUI 地址: {api.base_url}")
    print(f"在线状态: {'✅' if api.is_online() else '❌'}")
    if api.is_online():
        stats = api.get_system_stats()
        print(f"系统状态: {json.dumps(stats, indent=2, ensure_ascii=False)[:500]}")
