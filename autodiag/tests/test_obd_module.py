import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obd_module import _safe_eval_formula, ELMConnection


def test_safe_eval_formula_basic_subtraction():
    assert _safe_eval_formula("A-40", {"A": 100, "B": 0, "C": 0, "D": 0}) == 60


def test_safe_eval_formula_rpm_style():
    result = _safe_eval_formula("((A*256)+B)/4", {"A": 1, "B": 244, "C": 0, "D": 0})
    assert result == 125.0


def test_safe_eval_formula_rejects_function_call():
    with pytest.raises(Exception):
        _safe_eval_formula("__import__('os')", {"A": 0, "B": 0, "C": 0, "D": 0})


def test_safe_eval_formula_rejects_attribute_access():
    with pytest.raises(Exception):
        _safe_eval_formula("A.__class__", {"A": 0, "B": 0, "C": 0, "D": 0})


def test_safe_eval_formula_unknown_name_raises():
    with pytest.raises(Exception):
        _safe_eval_formula("E", {"A": 0, "B": 0, "C": 0, "D": 0})


def test_parse_dtc_single_code():
    conn = ELMConnection()
    codes = conn._parse_dtc("43 01 03")
    assert codes == ["P0103"]


def test_parse_dtc_no_codes():
    conn = ELMConnection()
    codes = conn._parse_dtc("43 00 00")
    assert codes == []


def test_parse_dtc_garbage_input_does_not_raise():
    conn = ELMConnection()
    codes = conn._parse_dtc("NODATA")
    assert codes == []


def test_parse_pid_value_rejects_unsafe_formula():
    conn = ELMConnection()
    pid_info = {
        "name": "evil",
        "mode": "01",
        "pid": "010C",
        "formula": "__import__('os').system('echo hacked')",
    }
    result = conn.parse_pid_value(pid_info, "41 0C 00 00")
    assert result is None


def test_parse_pid_value_basic_rpm():
    conn = ELMConnection()
    pid_info = {"name": "rpm", "mode": "01", "pid": "010C", "formula": "((A*256)+B)/4"}
    result = conn.parse_pid_value(pid_info, "41 0C 00 00 01 F4")
    assert result == pytest.approx(125.0)


def test_parse_pid_value_too_short_returns_none():
    conn = ELMConnection()
    pid_info = {"name": "rpm", "mode": "01", "pid": "010C", "formula": "A"}
    result = conn.parse_pid_value(pid_info, "")
    assert result is None
