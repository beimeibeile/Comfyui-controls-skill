"""
tts_executor.py 单元测试
验证TTS音色映射和情绪指令映射
"""
import os
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from tts_executor import CHARACTER_VOICE_MAP, EMOTION_INSTRUCT_MAP


class TestTTSExecutor(unittest.TestCase):
    """TTS执行器测试"""

    def test_character_voice_map_complete(self):
        """角色音色映射应包含主要角色"""
        required_chars = ["豆包", "旁白", "默认"]
        for char in required_chars:
            self.assertIn(char, CHARACTER_VOICE_MAP,
                          f"缺少角色音色: {char}")

    def test_voice_map_values_nonempty(self):
        """所有音色映射值不应为空"""
        for char, voice in CHARACTER_VOICE_MAP.items():
            self.assertTrue(voice, f"角色{char}的音色为空")

    def test_emotion_instruct_map_complete(self):
        """情绪指令映射应包含基础情绪"""
        required_emotions = [
            "normal", "happy", "sad", "angry",
            "fear", "surprise", "calm",
        ]
        for emotion in required_emotions:
            self.assertIn(emotion, EMOTION_INSTRUCT_MAP,
                          f"缺少情绪: {emotion}")

    def test_calm_emotion_has_instruction(self):
        """calm情绪应有具体指令"""
        self.assertTrue(len(EMOTION_INSTRUCT_MAP["calm"]) > 0)

    def test_angry_emotion_has_instruction(self):
        """angry情绪应有具体指令"""
        self.assertTrue(len(EMOTION_INSTRUCT_MAP["angry"]) > 0)

    def test_chinese_emotions_present(self):
        """中文情绪映射应存在"""
        chinese_emotions = [
            "委屈抱怨", "得意洋洋", "冷笑嘲讽",
            "心慌意乱", "暴跳如雷", "低声下气",
        ]
        for emotion in chinese_emotions:
            self.assertIn(emotion, EMOTION_INSTRUCT_MAP,
                          f"缺少中文情绪: {emotion}")

    def test_comfyui_url_format(self):
        """ComfyUI URL格式正确"""
        from tts_executor import COMFYUI_URL
        self.assertTrue(COMFYUI_URL.startswith("http://"))
        self.assertIn("8188", COMFYUI_URL)


if __name__ == "__main__":
    unittest.main()
