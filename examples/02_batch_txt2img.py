"""
示例2: 典型场景 - 批量文生图
运行: python examples/02_batch_txt2img.py
前置: ComfyUI运行中，且有文生图工作流
"""
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from comfy_controls import create_controls


def main():
    cc = create_controls(output_dir="./output_batch")

    if not cc.is_online():
        print("❌ ComfyUI离线，请先启动")
        return

    # 批量生成提示词
    prompts = [
        "一只可爱的橘猫坐在窗台上，阳光洒落，高清摄影",
        "赛博朋克风格的城市夜景，霓虹灯，雨天，电影感",
        "水彩画风格的山间小屋，晨雾，宁静",
    ]

    print(f"开始批量生成 {len(prompts)} 张图片...")
    results = cc.batch_generate(
        workflow="zimage_t2i",  # 使用Z-Image极速文生图预设
        prompts=prompts,
        quality_check=False,
    )

    print(f"\n=== 生成结果 ===")
    print(f"成功: {len(results.get('success', []))}")
    print(f"失败: {len(results.get('failed', []))}")

    if results.get("success"):
        print(f"\n输出目录: {os.path.abspath('./output_batch')}")
        for path in results["success"]:
            print(f"  ✅ {path}")


if __name__ == "__main__":
    main()
