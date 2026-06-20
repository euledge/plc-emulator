import pytest
from src.scripting.evaluator import SafeEvaluator
from src.device.device_manager import DeviceManager


@pytest.fixture
def eval():
    dm = DeviceManager()
    return SafeEvaluator(device_manager=dm)


def test_simple_arithmetic(eval):
    assert eval.evaluate("1 + 2 * 3") == 7


def test_builtin_function_call(eval):
    assert eval.evaluate("sin(0)") == 0.0
    assert eval.evaluate("abs(-5)") == 5


def test_device_reference(eval):
    eval.device_manager.write_word("D", 100, 42)
    assert eval.evaluate("D100") == 42


def test_builtin_variables(eval):
    assert eval.evaluate("t") == 0.0
    eval.elapsed = 10.5
    assert eval.evaluate("t") == 10.5


def test_unsafe_import_raises(eval):
    with pytest.raises(ValueError, match="not allowed"):
        eval.evaluate("__import__('os')")


def test_unsafe_call_raises(eval):
    with pytest.raises(ValueError, match="not allowed"):
        eval.evaluate("open('/etc/passwd')")


def test_attribute_access_raises(eval):
    with pytest.raises(ValueError):
        eval.evaluate("().__class__")
