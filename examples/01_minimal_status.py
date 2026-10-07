"""
示例1: 最小可用 - 连接ComfyUI并获取状态
运行: python examples/01_minimal_status.py
"""
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from comfy_controls import create_controls


def main():
    # 创建控制器（使用默认API地址 http://127.0.0.1:8188）
    cc = create_controls()

    # 检查连接状态
    print(f"ComfyUI在线: {cc.is_online()}")
    if not cc.is_online():
        print("提示: 请先启动ComfyUI")
        return

    # 获取完整状态
    status = cc.get_status()
    print(f"\n=== ComfyUI 状态 ===")
    print(f"API地址: {status['api_url']}")
    print(f"工作流数量: {len(status['workflows'])}")
    print(f"模型总数: {status['models_count']}")

    # 列出预设工作流
    print(f"\n=== 预设工作流 ===")
    for name, info in cc.PRESET_WORKFLOWS.items():
        print(f"  {name}: {info['name']} - {info['description']}")

    # 列出模型
    print(f"\n=== 可用模型 ===")
    models = cc.list_models()
    for model_type, model_list in models.items():
        print(f"  {model_type}: {len(model_list)}个")
        for m in model_list[:5]:
            print(f"    - {m}")
        if len(model_list) > 5:
            print(f"    ... 还有{len(model_list)-5}个")


if __name__ == "__main__":
    main()
