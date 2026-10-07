"""
cap_frame_matting - 逐帧抠图能力模块
从视频或图片序列中逐帧提取前景，生成带Alpha通道的PNG序列
"""
from .frame_matting import FrameMattingPipeline

__all__ = ["FrameMattingPipeline"]
