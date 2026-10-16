#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识管理引擎 (Knowledge Manager)
用于 ComfyUI Controls Skill 的学习、进化和能力提升。

功能：
1. 知识库管理：结构化存储模型知识、最佳实践、故障排除
2. 学习记录：记录每次任务的经验教训，自动沉淀到知识库
3. 知识检索：按关键词/模型/场景检索相关知识
4. 版本管理：知识库版本化，支持回滚和对比
5. 自进化：从成功/失败案例中提取规律，更新最佳实践
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any


class KnowledgeManager:
    """知识管理引擎"""

    def __init__(self, skill_root: Optional[str] = None):
        if skill_root is None:
            # 自动探测 skill 根目录
            skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skill_root = skill_root
        self.knowledge_dir = os.path.join(skill_root, "knowledge")
        self.kb_dir = os.path.join(self.knowledge_dir, "knowledge_base")
        self.versions_dir = os.path.join(self.knowledge_dir, "versions")
        self.logs_dir = os.path.join(self.knowledge_dir, "learning_logs")
        self.version_file = os.path.join(self.versions_dir, "knowledge_version.json")

        os.makedirs(self.kb_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        self._init_version()

    def _init_version(self):
        """初始化版本文件"""
        if not os.path.exists(self.version_file):
            self._save_version({
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "knowledge_domains": ["minimax_h3"],
                "total_entries": 0,
                "learning_records": 0,
                "changelog": []
            })

    def _load_version(self) -> Dict:
        with open(self.version_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_version(self, data: Dict):
        data["updated_at"] = datetime.now().isoformat()
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_version(self) -> Dict:
        """获取知识库版本信息"""
        return self._load_version()

    def list_domains(self) -> List[str]:
        """列出所有知识领域"""
        domains = []
        if os.path.exists(self.kb_dir):
            for item in os.listdir(self.kb_dir):
                item_path = os.path.join(self.kb_dir, item)
                if os.path.isdir(item_path) and not item.startswith("_"):
                    domains.append(item)
        return sorted(domains)

    def list_knowledge(self, domain: Optional[str] = None) -> List[Dict]:
        """列出知识库条目

        Args:
            domain: 知识领域（如 minimax_h3），None 则列出全部

        Returns:
            知识条目列表，每项含 domain/title/file/path/size
        """
        results = []
        search_dirs = [os.path.join(self.kb_dir, domain)] if domain else [
            os.path.join(self.kb_dir, d) for d in self.list_domains()
        ]
        for d in search_dirs:
            if not os.path.exists(d):
                continue
            domain_name = os.path.basename(d)
            for fname in os.listdir(d):
                if fname.endswith(".md"):
                    fpath = os.path.join(d, fname)
                    results.append({
                        "domain": domain_name,
                        "title": fname.replace(".md", ""),
                        "file": fname,
                        "path": fpath,
                        "size_kb": round(os.path.getsize(fpath) / 1024, 1)
                    })
        return sorted(results, key=lambda x: (x["domain"], x["title"]))

    def read_knowledge(self, domain: str, title: str) -> str:
        """读取知识条目内容

        Args:
            domain: 知识领域
            title: 条目标题（不含.md）

        Returns:
            知识内容（Markdown 文本）
        """
        fpath = os.path.join(self.kb_dir, domain, f"{title}.md")
        if not os.path.exists(fpath):
            return f"[知识不存在] {domain}/{title}"
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read()

    def search_knowledge(self, query: str, domain: Optional[str] = None,
                         max_results: int = 10) -> List[Dict]:
        """关键词检索知识库

        Args:
            query: 搜索关键词
            domain: 限定领域
            max_results: 最大返回数

        Returns:
            匹配的知识条目，按相关度排序
        """
        query_lower = query.lower()
        keywords = [k for k in query_lower.split() if len(k) > 1]
        results = []
        for entry in self.list_knowledge(domain):
            content = self.read_knowledge(entry["domain"], entry["title"]).lower()
            score = 0
            # 标题匹配权重高
            title_lower = entry["title"].lower()
            for kw in keywords:
                if kw in title_lower:
                    score += 5
                if kw in content:
                    score += content.count(kw)
            if score > 0:
                entry["relevance_score"] = score
                # 提取匹配上下文
                lines = content.split("\n")
                matches = []
                for i, line in enumerate(lines):
                    if any(kw in line for kw in keywords):
                        matches.append(line.strip()[:120])
                        if len(matches) >= 3:
                            break
                entry["context"] = matches
                results.append(entry)
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_results]

    def add_knowledge(self, domain: str, title: str, content: str,
                      source: str = "manual", tags: Optional[List[str]] = None):
        """新增知识条目

        Args:
            domain: 知识领域
            title: 条目标题
            content: Markdown 内容
            source: 来源（manual/learned/official/extracted）
            tags: 标签列表
        """
        domain_dir = os.path.join(self.kb_dir, domain)
        os.makedirs(domain_dir, exist_ok=True)
        fpath = os.path.join(domain_dir, f"{title}.md")

        # 添加元数据头
        header = (
            f"---\n"
            f"domain: {domain}\n"
            f"title: {title}\n"
            f"source: {source}\n"
            f"tags: {', '.join(tags or [])}\n"
            f"created_at: {datetime.now().isoformat()}\n"
            f"---\n\n"
        )
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(header + content)

        # 更新版本
        v = self._load_version()
        v["total_entries"] = len(self.list_knowledge())
        if domain not in v["knowledge_domains"]:
            v["knowledge_domains"].append(domain)
        v["changelog"].append({
            "action": "add",
            "domain": domain,
            "title": title,
            "source": source,
            "time": datetime.now().isoformat()
        })
        self._save_version(v)
        self._log_learning("add_knowledge", f"{domain}/{title}", source)

    def update_knowledge(self, domain: str, title: str, content: str,
                         reason: str = ""):
        """更新知识条目"""
        fpath = os.path.join(self.kb_dir, domain, f"{title}.md")
        if not os.path.exists(fpath):
            self.add_knowledge(domain, title, content, source="updated")
            return
        # 保留元数据头，更新正文
        with open(fpath, "r", encoding="utf-8") as f:
            old = f.read()
        # 提取头部
        if old.startswith("---"):
            end = old.index("---", 3)
            header = old[:end + 3]
        else:
            header = f"---\ndomain: {domain}\ntitle: {title}\nsource: updated\n---\n"
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(header + "\n\n" + content)

        v = self._load_version()
        v["changelog"].append({
            "action": "update",
            "domain": domain,
            "title": title,
            "reason": reason,
            "time": datetime.now().isoformat()
        })
        self._save_version(v)
        self._log_learning("update_knowledge", f"{domain}/{title}", reason)

    def record_learning(self, task_type: str, outcome: str, lesson: str,
                        model: str = "", params: Optional[Dict] = None):
        """记录学习经验（从任务中沉淀）

        Args:
            task_type: 任务类型（如 h3_generation, image_gen, video_edit）
            outcome: 结果（success/failure/partial）
            lesson: 经验教训描述
            model: 涉及的模型
            params: 关键参数
        """
        record = {
            "id": hashlib.md5(f"{task_type}{lesson}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "outcome": outcome,
            "lesson": lesson,
            "model": model,
            "params": params or {}
        }
        log_file = os.path.join(self.logs_dir, f"learning_{datetime.now().strftime('%Y%m')}.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        v = self._load_version()
        v["learning_records"] = v.get("learning_records", 0) + 1
        self._save_version(v)

    def _log_learning(self, action: str, target: str, detail: str = ""):
        """内部学习日志"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": target,
            "detail": detail
        }
        log_file = os.path.join(self.logs_dir, "knowledge_ops.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_learning_stats(self) -> Dict:
        """获取学习统计"""
        stats = {
            "total_records": 0,
            "by_outcome": {"success": 0, "failure": 0, "partial": 0},
            "by_task_type": {},
            "recent_lessons": []
        }
        for fname in os.listdir(self.logs_dir):
            if fname.startswith("learning_") and fname.endswith(".jsonl"):
                fpath = os.path.join(self.logs_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        stats["total_records"] += 1
                        outcome = rec.get("outcome", "unknown")
                        if outcome in stats["by_outcome"]:
                            stats["by_outcome"][outcome] += 1
                        tt = rec.get("task_type", "unknown")
                        stats["by_task_type"][tt] = stats["by_task_type"].get(tt, 0) + 1
                        if len(stats["recent_lessons"]) < 10:
                            stats["recent_lessons"].append({
                                "time": rec.get("timestamp", "")[:19],
                                "task": rec.get("task_type", ""),
                                "outcome": outcome,
                                "lesson": rec.get("lesson", "")[:100]
                            })
        return stats

    def evolve_best_practices(self, domain: str = "minimax_h3") -> Dict:
        """从学习记录中进化最佳实践

        分析成功/失败案例，提取规律，更新 best_practices 知识条目。
        """
        stats = self.get_learning_stats()
        # 收集该领域的成功经验
        success_lessons = []
        failure_lessons = []
        for fname in os.listdir(self.logs_dir):
            if fname.startswith("learning_") and fname.endswith(".jsonl"):
                fpath = os.path.join(self.logs_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        if domain in rec.get("model", "").lower() or domain in rec.get("task_type", "").lower():
                            if rec.get("outcome") == "success":
                                success_lessons.append(rec.get("lesson", ""))
                            elif rec.get("outcome") == "failure":
                                failure_lessons.append(rec.get("lesson", ""))

        result = {
            "domain": domain,
            "success_lessons_collected": len(success_lessons),
            "failure_lessons_collected": len(failure_lessons),
            "updated": False
        }

        # 如果有足够的学习记录，更新最佳实践
        if len(success_lessons) + len(failure_lessons) >= 3:
            content = self.read_knowledge(domain, "best_practices")
            # 添加从经验中提取的新条目
            new_section = "\n\n## 从实战中进化的经验\n\n"
            if success_lessons:
                new_section += "### 成功经验\n"
                for i, lesson in enumerate(success_lessons[-5:], 1):
                    new_section += f"{i}. {lesson}\n"
            if failure_lessons:
                new_section += "\n### 失败教训\n"
                for i, lesson in enumerate(failure_lessons[-5:], 1):
                    new_section += f"{i}. {lesson}\n"

            if "从实战中进化的经验" not in content:
                self.update_knowledge(domain, "best_practices",
                                      content + new_section,
                                      reason=f"从{len(success_lessons)+len(failure_lessons)}条学习记录进化")
                result["updated"] = True

        return result

    def get_status(self) -> Dict:
        """获取知识管理系统状态"""
        v = self._load_version()
        return {
            "version": v.get("version"),
            "domains": self.list_domains(),
            "total_entries": v.get("total_entries", 0),
            "learning_records": v.get("learning_records", 0),
            "last_updated": v.get("updated_at", ""),
            "knowledge_items": self.list_knowledge()
        }


if __name__ == "__main__":
    # 自检
    km = KnowledgeManager()
    status = km.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
