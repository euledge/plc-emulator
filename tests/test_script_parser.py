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
