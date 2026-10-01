"""
质量控制器
生成结果质量检测、自动筛选、不合格重生成
"""
import os
from typing import Dict, List, Optional


class QualityController:
    """质量控制器"""

    def __init__(self, quality_threshold: float = 0.7):
        self.quality_threshold = quality_threshold
        self.checks = {
            "resolution": self._check_resolution,
            "file_size": self._check_file_size,
            "aspect_ratio": self._check_aspect_ratio,
        }

    def check_image(self, image_path: str) -> Dict:
        """
        检查图片质量

        Args:
            image_path: 图片路径

        Returns:
            质量检查结果字典
        """
        if not os.path.exists(image_path):
            return {"status": "failed", "error": "file_not_found"}

        results = {"file": image_path, "checks": {}, "passed": True}

        for check_name, check_func in self.checks.items():
            try:
                check_result = check_func(image_path)
                results["checks"][check_name] = check_result
                if not check_result.get("passed", True):
                    results["passed"] = False
            except Exception as e:
                results["checks"][check_name] = {"passed": False, "error": str(e)}
                results["passed"] = False

        return results

    def check_batch(self, image_paths: List[str]) -> Dict:
        """批量检查图片质量"""
        results = {"total": len(image_paths), "passed": [], "failed": []}
        for path in image_paths:
            result = self.check_image(path)
            if result["passed"]:
                results["passed"].append(result)
            else:
                results["failed"].append(result)
        return results

    def _check_resolution(self, image_path: str) -> Dict:
        """检查分辨率"""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
            min_size = 256
            passed = width >= min_size and height >= min_size
            return {"passed": passed, "width": width, "height": height}
        except ImportError:
            return {"passed": True, "warning": "Pillow not installed, skipped"}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _check_file_size(self, image_path: str) -> Dict:
        """检查文件大小"""
        try:
            size_kb = os.path.getsize(image_path) / 1024
            min_size_kb = 10  # 最小10KB
            passed = size_kb >= min_size_kb
            return {"passed": passed, "size_kb": round(size_kb, 2)}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _check_aspect_ratio(self, image_path: str) -> Dict:
        """检查宽高比"""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
            ratio = width / height if height > 0 else 0
            # 允许的宽高比范围 0.5 - 2.0
            passed = 0.5 <= ratio <= 2.0
            return {"passed": passed, "ratio": round(ratio, 2)}
        except ImportError:
            return {"passed": True, "warning": "Pillow not installed, skipped"}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def auto_regenerate(self, failed_results: List[Dict], generator=None) -> Dict:
        """自动重生成不合格的图片（占位，待实现）"""
        return {
            "regenerated": len(failed_results),
            "status": "regeneration_pending",
            "message": "自动重生成功能开发中",
        }


if __name__ == "__main__":
    qc = QualityController()
    print(f"质量阈值: {qc.quality_threshold}")
    print(f"可用检查项: {list(qc.checks.keys())}")
