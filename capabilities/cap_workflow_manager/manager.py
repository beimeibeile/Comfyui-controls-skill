"""
工作流管理器
工作流模板库、版本控制、参数优化、一键运行
"""
import os
import json
from typing import Dict, List, Optional


class WorkflowManager:
    """工作流管理器"""

    def __init__(self, workflows_dir: str = None):
        self.workflows_dir = workflows_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "workflows"
        )
        os.makedirs(self.workflows_dir, exist_ok=True)

    def list_workflows(self) -> List[str]:
        """列出所有工作流模板"""
        workflows = []
        for f in os.listdir(self.workflows_dir):
            if f.endswith(".json"):
                workflows.append(f.replace(".json", ""))
        return sorted(workflows)

    def load_workflow(self, name: str) -> Optional[Dict]:
        """加载工作流模板"""
        path = os.path.join(self.workflows_dir, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_workflow(self, name: str, workflow: Dict, version: str = "1.0") -> str:
        """保存工作流模板"""
        workflow["_meta"] = {
            "name": name,
            "version": version,
            "created_at": os.path.getmtime(__file__),
        }
        path = os.path.join(self.workflows_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, ensure_ascii=False, indent=2)
        return path

    def run(self, name: str, params: Dict = None, api=None) -> Optional[Dict]:
        """运行工作流"""
        workflow = self.load_workflow(name)
        if not workflow:
            print(f"❌ 工作流不存在: {name}")
            return None

        # 应用参数
        if params:
            workflow = self._apply_params(workflow, params)

        if api is None:
            from cap_api_wrapper import ComfyAPI
            api = ComfyAPI()

        result = api.queue_prompt(workflow)
        return result

    def _apply_params(self, workflow: Dict, params: Dict) -> Dict:
        """应用参数到工作流"""
        # 简单的参数替换：根据节点id和字段名替换
        for node_id, node in workflow.items():
            if isinstance(node, dict) and "inputs" in node:
                for key, value in params.items():
                    if key in node["inputs"]:
                        node["inputs"][key] = value
        return workflow

    def optimize(self, name: str, test_prompts: List[str] = None) -> Dict:
        """自动优化工作流参数（占位，待实现）"""
        return {
            "workflow": name,
            "status": "optimization_pending",
            "message": "自动优化功能开发中",
        }


if __name__ == "__main__":
    wm = WorkflowManager()
    print(f"工作流目录: {wm.workflows_dir}")
    print(f"可用工作流: {wm.list_workflows()}")
