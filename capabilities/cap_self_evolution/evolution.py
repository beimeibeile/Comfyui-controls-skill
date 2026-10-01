"""
自我进化模块
从生成结果中学习优化参数、积累最佳实践
"""
import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class SelfEvolution:
    """自我进化模块"""

    def __init__(self, knowledge_dir: str = None):
        self.knowledge_dir = knowledge_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "knowledge"
        )
        os.makedirs(self.knowledge_dir, exist_ok=True)
        self.best_practices_file = os.path.join(self.knowledge_dir, "best_practices.json")
        self.learning_log_file = os.path.join(self.knowledge_dir, "learning_log.json")

    def record_result(self, workflow: str, params: Dict, result: Dict, quality_score: float) -> bool:
        """
        记录生成结果用于学习

        Args:
            workflow: 工作流名称
            params: 使用的参数
            result: 生成结果
            quality_score: 质量评分（0-1）

        Returns:
            是否记录成功
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "workflow": workflow,
                "params": params,
                "quality_score": quality_score,
                "result_summary": {
                    "success": result.get("status") == "success",
                    "output_count": len(result.get("outputs", [])),
                }
            }

            # 追加到学习日志
            log = self._load_json(self.learning_log_file, [])
            log.append(log_entry)
            # 只保留最近1000条
            if len(log) > 1000:
                log = log[-1000:]
            self._save_json(self.learning_log_file, log)

            # 更新最佳实践
            if quality_score >= 0.8:
                self._update_best_practice(workflow, params, quality_score)

            return True
        except Exception as e:
            print(f"❌ 记录学习结果失败: {e}")
            return False

    def get_best_params(self, workflow: str) -> Optional[Dict]:
        """获取某工作流的最佳参数"""
        practices = self._load_json(self.best_practices_file, {})
        return practices.get(workflow, {}).get("best_params")

    def suggest_optimization(self, workflow: str, current_params: Dict) -> Dict:
        """
        基于历史数据建议参数优化

        Args:
            workflow: 工作流名称
            current_params: 当前参数

        Returns:
            优化建议
        """
        best = self.get_best_params(workflow)
        if not best:
            return {"suggestion": "no_history", "message": "暂无历史数据，使用默认参数"}

        # 比较当前参数和最佳参数
        suggestions = []
        for key, best_value in best.items():
            if key in current_params and current_params[key] != best_value:
                suggestions.append({
                    "param": key,
                    "current": current_params[key],
                    "suggested": best_value,
                    "reason": "历史最佳实践",
                })

        return {
            "workflow": workflow,
            "best_quality_score": best.get("_quality_score", 0),
            "suggestions": suggestions,
        }

    def get_learning_stats(self) -> Dict:
        """获取学习统计"""
        log = self._load_json(self.learning_log_file, [])
        practices = self._load_json(self.best_practices_file, {})

        total = len(log)
        high_quality = sum(1 for entry in log if entry.get("quality_score", 0) >= 0.8)
        avg_quality = sum(entry.get("quality_score", 0) for entry in log) / total if total > 0 else 0

        return {
            "total_records": total,
            "high_quality_count": high_quality,
            "average_quality_score": round(avg_quality, 3),
            "best_practices_count": len(practices),
            "workflows_learned": list(practices.keys()),
        }

    def _update_best_practice(self, workflow: str, params: Dict, quality_score: float):
        """更新最佳实践"""
        practices = self._load_json(self.best_practices_file, {})

        current_best = practices.get(workflow, {})
        if quality_score > current_best.get("_quality_score", 0):
            practices[workflow] = {
                "best_params": params,
                "_quality_score": quality_score,
                "_updated_at": datetime.now().isoformat(),
            }
            self._save_json(self.best_practices_file, practices)

    def auto_evaluate_output(self, output_path: str, gen_time_sec: float = 0,
                             expected_resolution: tuple = None) -> Dict:
        """
        自动评估ComfyUI生成结果的质量

        Args:
            output_path: 生成的图片/视频路径
            gen_time_sec: 生成耗时（秒）
            expected_resolution: 期望分辨率 (width, height)

        Returns:
            质量评估结果（含score 0-1）
        """
        if not os.path.exists(output_path):
            return {"score": 0.0, "passed": False, "error": "file_not_found"}

        try:
            file_size_kb = os.path.getsize(output_path) / 1024
            is_image = output_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            is_video = output_path.lower().endswith((".mp4", ".mov", ".avi"))

            checks = {"file_size": file_size_kb > 5}
            score = 0.0

            if is_image:
                try:
                    from PIL import Image
                    with Image.open(output_path) as img:
                        width, height = img.size
                    checks["resolution"] = width >= 256 and height >= 256
                    if expected_resolution:
                        checks["matches_expected"] = (width == expected_resolution[0] and
                                                      height == expected_resolution[1])
                    # 分辨率评分
                    res_score = min(1.0, (width * height) / (2048 * 2048))
                    # 文件大小评分（过小可能是空白图）
                    size_score = min(1.0, file_size_kb / 500)
                    score = (res_score + size_score) / 2

                    # 检测全黑/全白图
                    import numpy as np
                    arr = np.array(img.convert("L"))
                    mean_brightness = float(arr.mean())
                    checks["not_black"] = mean_brightness > 5
                    checks["not_white"] = mean_brightness < 250
                    if mean_brightness <= 5 or mean_brightness >= 250:
                        score *= 0.3
                except ImportError:
                    score = 0.5 if file_size_kb > 10 else 0.2
                except Exception as e:
                    score = 0.3

            elif is_video:
                # 视频评分：文件大小+时长
                checks["video_valid"] = file_size_kb > 50
                score = min(1.0, file_size_kb / 5000)
                if gen_time_sec > 0:
                    # 生成效率评分
                    efficiency = min(1.0, 30 / gen_time_sec) if gen_time_sec > 0 else 0.5
                    score = (score + efficiency) / 2

            # 生成效率评分
            if gen_time_sec > 0:
                checks["generation_time"] = gen_time_sec
                if is_image:
                    efficiency = min(1.0, 60 / gen_time_sec) if gen_time_sec > 0 else 0.5
                else:
                    efficiency = min(1.0, 300 / gen_time_sec) if gen_time_sec > 0 else 0.5
                score = (score + efficiency) / 2

            passed = all(checks.values()) and score >= 0.3

            return {
                "score": round(score, 3),
                "passed": passed,
                "checks": checks,
                "file_size_kb": round(file_size_kb, 1),
                "gen_time_sec": gen_time_sec,
            }
        except Exception as e:
            return {"score": 0.0, "passed": False, "error": str(e)}

    def analyze_failure(self, error_msg: str, params: Dict = None) -> Dict:
        """
        分析ComfyUI生成失败原因

        Args:
            error_msg: 错误信息
            params: 使用的参数

        Returns:
            失败分析和建议
        """
        error_lower = error_msg.lower() if error_msg else ""

        failure_types = {
            "out_of_memory": {
                "keywords": ["out of memory", "oom", "cuda out of memory", "显存不足"],
                "cause": "GPU显存不足",
                "suggestion": "降低分辨率/批量大小，或使用更小的模型",
            },
            "timeout": {
                "keywords": ["timeout", "timed out", "超时"],
                "cause": "生成超时",
                "suggestion": "减少步数或降低分辨率",
            },
            "model_not_found": {
                "keywords": ["not found", "no such file", "模型不存在", "file not found"],
                "cause": "模型文件缺失",
                "suggestion": "检查模型路径，下载所需模型",
            },
            "invalid_param": {
                "keywords": ["invalid", "error", "exception", "valueerror"],
                "cause": "参数错误",
                "suggestion": "检查参数范围和类型",
            },
            "connection_error": {
                "keywords": ["connection", "refused", "连接", "127.0.0.1", "8188"],
                "cause": "ComfyUI服务未启动或连接失败",
                "suggestion": "启动ComfyUI服务，检查端口8188",
            },
        }

        detected = "unknown"
        cause = "未知错误"
        suggestion = "查看完整错误日志"

        for ftype, info in failure_types.items():
            if any(kw in error_lower for kw in info["keywords"]):
                detected = ftype
                cause = info["cause"]
                suggestion = info["suggestion"]
                break

        # 记录失败案例
        failure_log = os.path.join(self.knowledge_dir, "failure_log.json")
        failures = self._load_json(failure_log, [])
        failures.append({
            "timestamp": datetime.now().isoformat(),
            "error_type": detected,
            "error_msg": error_msg[:500],
            "params": params or {},
        })
        if len(failures) > 500:
            failures = failures[-500:]
        self._save_json(failure_log, failures)

        return {
            "error_type": detected,
            "cause": cause,
            "suggestion": suggestion,
            "original_error": error_msg[:200],
        }

    def get_model_usage_stats(self) -> Dict:
        """获取模型使用统计"""
        log = self._load_json(self.learning_log_file, [])
        model_stats = {}

        for entry in log:
            params = entry.get("params", {})
            model = params.get("model", params.get("ckpt_name", "unknown"))
            if model not in model_stats:
                model_stats[model] = {"count": 0, "success": 0, "avg_quality": 0, "qualities": []}
            model_stats[model]["count"] += 1
            if entry.get("result_summary", {}).get("success", False):
                model_stats[model]["success"] += 1
            q = entry.get("quality_score", 0)
            model_stats[model]["qualities"].append(q)

        for model, stats in model_stats.items():
            stats["success_rate"] = round(stats["success"] / stats["count"], 3) if stats["count"] > 0 else 0
            stats["avg_quality"] = round(sum(stats["qualities"]) / len(stats["qualities"]), 3) if stats["qualities"] else 0
            del stats["qualities"]

        return {
            "total_generations": len(log),
            "models": model_stats,
            "top_model": max(model_stats.items(), key=lambda x: x[1]["success_rate"])[0] if model_stats else None,
        }

    def get_optimization_report(self) -> Dict:
        """生成全局优化建议报告"""
        stats = self.get_learning_stats()
        model_stats = self.get_model_usage_stats()
        practices = self._load_json(self.best_practices_file, {})

        report = {
            "summary": stats,
            "model_stats": model_stats,
            "top_workflows": [],
            "weak_workflows": [],
            "recommendations": [],
        }

        # 按工作流统计
        workflow_scores = {}
        for entry in self._load_json(self.learning_log_file, []):
            wf = entry.get("workflow", "unknown")
            if wf not in workflow_scores:
                workflow_scores[wf] = []
            workflow_scores[wf].append(entry.get("quality_score", 0))

        for wf, scores in workflow_scores.items():
            avg = sum(scores) / len(scores) if scores else 0
            if avg >= 0.8:
                report["top_workflows"].append({"workflow": wf, "avg_score": round(avg, 3), "runs": len(scores)})
            elif avg < 0.5 and len(scores) >= 3:
                report["weak_workflows"].append({"workflow": wf, "avg_score": round(avg, 3), "runs": len(scores)})

        # 生成建议
        if stats["total_records"] < 10:
            report["recommendations"].append("数据量不足，建议多运行几次工作流以积累学习数据")
        if report["weak_workflows"]:
            report["recommendations"].append(
                f"以下工作流表现较差，建议优化参数: {[w['workflow'] for w in report['weak_workflows']]}"
            )
        if model_stats.get("top_model"):
            report["recommendations"].append(
                f"推荐使用模型: {model_stats['top_model']} (成功率最高)"
            )

        return report

    def export_knowledge(self, output_path: str) -> str:
        """导出知识库为JSON"""
        data = {
            "best_practices": self._load_json(self.best_practices_file, {}),
            "learning_log": self._load_json(self.learning_log_file, []),
            "failure_log": self._load_json(os.path.join(self.knowledge_dir, "failure_log.json"), []),
            "stats": self.get_learning_stats(),
            "model_stats": self.get_model_usage_stats(),
            "exported_at": datetime.now().isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path

    def _load_json(self, path: str, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: str, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    se = SelfEvolution()
    print(f"知识库目录: {se.knowledge_dir}")
    print(f"学习统计: {json.dumps(se.get_learning_stats(), indent=2, ensure_ascii=False)}")
