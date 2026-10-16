"""
ComfyUI 知识管理模块
用于学习、进化和提高 ComfyUI 及相关模型的使用能力。

核心能力：
- knowledge_manager: 知识管理引擎（学习/检索/进化/版本管理）
- prompt_engineer: H3 Prompt 生成引擎（集成官方 Prompt Writing Skill）
"""

from .knowledge_manager import KnowledgeManager
from .prompt_engineer import H3PromptEngineer

__all__ = ["KnowledgeManager", "H3PromptEngineer"]
__version__ = "1.0.0"
