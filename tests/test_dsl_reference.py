import re
from pathlib import Path
from src.scripting.parser import ScriptParser


def test_script_dsl_reference_exists_and_contains_all_types():
    ref_path = Path(__file__).resolve().parent.parent / "docs" / "script_dsl_reference.md"
    assert ref_path.exists()
    content = ref_path.read_text(encoding="utf-8")

    # Check that all 4 types are covered
    assert "periodic" in content
    assert "conditional" in content
    assert "sequence" in content
    assert "ramp" in content

    # Check built-in functions and variables
    assert "clamp" in content
    assert "sin" in content
    assert "cos" in content
    assert "square" in content
    assert "sawtooth" in content
    assert "tick" in content
    assert "dt" in content

    # Check execution controls and API
    assert "/api/scripts" in content
    assert "Start" in content
    assert "Stop" in content
    assert "Pause" in content


def test_script_dsl_reference_yaml_examples_are_all_valid():
    ref_path = Path(__file__).resolve().parent.parent / "docs" / "script_dsl_reference.md"
    content = ref_path.read_text(encoding="utf-8")

    # Extract all ```yaml ... ``` code blocks
    pattern = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)
    yaml_blocks = pattern.findall(content)
    assert len(yaml_blocks) >= 4

    for i, yaml_text in enumerate(yaml_blocks):
        valid, errors = ScriptParser.validate_content(yaml_text)
        assert valid, f"YAML example #{i + 1} validation failed: {errors}\nSnippet:\n{yaml_text}"
