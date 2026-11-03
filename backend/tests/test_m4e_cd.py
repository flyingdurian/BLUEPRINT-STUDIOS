from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _validator():
    path = ROOT / "tools" / "validate_m4e_cd.py"
    spec = importlib.util.spec_from_file_location("validate_m4e_cd", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_m4e_cd_contracts_and_godot_sources_match():
    module = _validator()
    errors = module.validate(ROOT / "docs" / "examples" / "BS-M4-PILOT-STAGE-PLAN.json")
    assert errors == []


def test_smoothstep_midpoint_and_endpoints():
    module = _validator()
    assert module.sample_weight(0, 24, 0, 0.38, 0.0) == 0.38
    assert module.sample_weight(0, 24, 24, 0.38, 0.0) == 0.0
    assert abs(module.sample_weight(0, 24, 12, 0.38, 0.0) - 0.19) < 1e-9
