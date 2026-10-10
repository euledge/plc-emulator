import pytest
from src.scripting.parser import ScriptParser


def test_parse_periodic():
    yaml_text = """
scripts:
  - name: "test"
    type: periodic
    interval_ms: 1000
    actions:
      - target: D100
        expr: "sin(t) * 100"
"""
    scripts = ScriptParser.parse(yaml_text)
    assert len(scripts) == 1
    s = scripts[0]
    assert s["name"] == "test"
    assert s["type"] == "periodic"
    assert s["interval_ms"] == 1000
    assert len(s["actions"]) == 1
    assert s["actions"][0]["target"] == "D100"
    assert s["actions"][0]["expr"] == "sin(t) * 100"


def test_parse_conditional():
    yaml_text = """
scripts:
  - name: "cond"
    type: conditional
    watch: D100
    interval_ms: 500
    conditions:
      - when: "D100 > 100"
        actions:
          - target: M0
            value: 1
"""
    scripts = ScriptParser.parse(yaml_text)
    assert len(scripts) == 1
    s = scripts[0]
    assert s["type"] == "conditional"
    assert len(s["conditions"]) == 1


def test_parse_sequence():
    yaml_text = """
scripts:
  - name: "seq"
    type: sequence
    loop: false
    steps:
      - wait_ms: 1000
        actions:
          - target: M0
            value: 1
"""
    scripts = ScriptParser.parse(yaml_text)
    assert len(scripts) == 1
    s = scripts[0]
    assert s["type"] == "sequence"
    assert len(s["steps"]) == 1


def test_parse_ramp():
    yaml_text = """
scripts:
  - name: "ramp"
    type: ramp
    target: D500
    start_value: 0
    end_value: 1000
    duration_ms: 5000
    loop: true
"""
    scripts = ScriptParser.parse(yaml_text)
    assert len(scripts) == 1
    s = scripts[0]
    assert s["type"] == "ramp"
    assert s["target"] == "D500"
    assert s["end_value"] == 1000


def test_invalid_yaml():
    with pytest.raises(ValueError, match="YAML"):
        ScriptParser.parse("invalid: [yaml: broken")
def test_validate_typed_value_actions():
    valid = """
type: sequence
name: typed
steps:
  - wait_ms: 0
    actions:
      - target: D100
        value: 100000
        data_type: dword
      - target: D110
        value: PLC
        data_type: ascii
        length: 8
"""
    ok, errors = ScriptParser.validate_content(valid)
    assert ok, errors


@pytest.mark.parametrize(
    ("action", "message"),
    [
        ({"target": "D100", "value": 1, "data_type": "word"}, "unsupported"),
        ({"target": "M0", "value": 1, "data_type": "dword"}, "word device"),
        ({"target": "D100", "value": 1.5, "data_type": "dword"}, "must be an integer"),
        ({"target": "D100", "value": 0x100000000, "data_type": "dword"}, "out of range"),
        ({"target": "D100", "value": -0x80000001, "data_type": "long"}, "out of range"),
        ({"target": "D100", "value": 1, "data_type": "ascii"}, "string"),
        ({"target": "D100", "value": "PLC", "data_type": "ascii", "length": 2}, "fit"),
        ({"target": "D100", "value": 1, "data_type": "long", "length": 2}, "only valid"),
    ],
)
def test_validate_typed_value_errors(action, message):
    content = {
        "type": "sequence",
        "name": "invalid",
        "steps": [{"wait_ms": 0, "actions": [action]}],
    }
    import yaml

    ok, errors = ScriptParser.validate_content(yaml.safe_dump(content))
    assert not ok
    assert any(message in error for error in errors)
