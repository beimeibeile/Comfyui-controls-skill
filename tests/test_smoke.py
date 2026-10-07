"""
冒烟测试: 验证comfyui-controls-skill核心模块可导入、可初始化
不依赖ComfyUI实际运行（离线模式）
纯Python断言，无需pytest
"""
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

passed = 0
failed = 0

def check(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {type(e).__name__}: {e}")
        failed += 1

print("=== 模块导入测试 ===")

def t_import_comfy_controls():
    from comfy_controls import ComfyControls, create_controls, PRESET_WORKFLOWS
    assert ComfyControls is not None
    assert create_controls is not None
    assert isinstance(PRESET_WORKFLOWS, dict)
    assert len(PRESET_WORKFLOWS) >= 3
check("comfy_controls 导入", t_import_comfy_controls)

def t_import_api_wrapper():
    from capabilities.cap_api_wrapper.api import ComfyAPI
    assert ComfyAPI is not None
check("cap_api_wrapper 导入", t_import_api_wrapper)

def t_import_workflow_manager():
    from capabilities.cap_workflow_manager.manager import WorkflowManager
    assert WorkflowManager is not None
check("cap_workflow_manager 导入", t_import_workflow_manager)

def t_import_model_manager():
    from capabilities.cap_model_manager.manager import ModelManager
    assert ModelManager is not None
check("cap_model_manager 导入", t_import_model_manager)

def t_import_batch_generator():
    from capabilities.cap_batch_generator.generator import BatchGenerator
    assert BatchGenerator is not None
check("cap_batch_generator 导入", t_import_batch_generator)

def t_import_quality_controller():
    from capabilities.cap_quality_control.controller import QualityController
    assert QualityController is not None
check("cap_quality_control 导入", t_import_quality_controller)

def t_import_self_evolution():
    from capabilities.cap_self_evolution.evolution import SelfEvolution
    assert SelfEvolution is not None
check("cap_self_evolution 导入", t_import_self_evolution)

print("\n=== 预设工作流测试 ===")

def t_preset_structure():
    from comfy_controls import PRESET_WORKFLOWS
    for name, info in PRESET_WORKFLOWS.items():
        assert "name" in info, f"{name}缺少name"
        assert "description" in info, f"{name}缺少description"
        assert "model" in info, f"{name}缺少model"
        assert "default_params" in info, f"{name}缺少default_params"
check("预设工作流结构完整", t_preset_structure)

def t_ltx_i2v_preset():
    from comfy_controls import PRESET_WORKFLOWS
    assert "ltx_i2v" in PRESET_WORKFLOWS
    p = PRESET_WORKFLOWS["ltx_i2v"]
    assert "steps" in p["default_params"]
    assert "width" in p["default_params"]
    assert "height" in p["default_params"]
check("ltx_i2v预设参数", t_ltx_i2v_preset)

print("\n=== 离线初始化测试 ===")

def t_workflow_manager_init():
    from capabilities.cap_workflow_manager.manager import WorkflowManager
    wm = WorkflowManager()
    assert wm is not None
    workflows = wm.list_workflows()
    assert isinstance(workflows, list)
check("WorkflowManager 初始化", t_workflow_manager_init)

def t_quality_controller_init():
    from capabilities.cap_quality_control.controller import QualityController
    qc = QualityController()
    assert qc is not None
check("QualityController 初始化", t_quality_controller_init)

def t_self_evolution_init():
    from capabilities.cap_self_evolution.evolution import SelfEvolution
    se = SelfEvolution()
    assert se is not None
    stats = se.get_learning_stats()
    assert isinstance(stats, dict)
check("SelfEvolution 初始化", t_self_evolution_init)

print(f"\n=== 结果: {passed} passed, {failed} failed ===")
sys.exit(1 if failed > 0 else 0)
