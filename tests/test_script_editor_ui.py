import subprocess
from pathlib import Path


def test_script_editor_html_structure():
    js_path = Path(__file__).resolve().parent.parent / "static" / "js" / "script_editor.js"
    content = js_path.read_text(encoding="utf-8")
    assert "editor_lines" in content
    assert "editor_highlight" in content
    assert "script_editor" in content
    assert "highlightYaml" in content
    assert "updateEditor" in content


def test_yaml_syntax_highlighter_logic_via_node():
    node_script = """
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');
    const jsContent = fs.readFileSync(path.join(process.cwd(), 'static', 'js', 'script_editor.js'), 'utf-8');
    // Extract highlightYaml implementation
    const sandbox = {
        document: {
            getElementById: () => ({ addEventListener: () => {}, value: '', style: {} })
        }
    };
    const se = vm.runInNewContext(jsContent + '\\n; ScriptEditor;', sandbox);
    const hl = se.highlightYaml;
    if (typeof hl !== 'function') {
        throw new Error('highlightYaml is not a function');
    }

    // 1. Comment highlighting
    const outComment = hl('# This is a comment');
    if (!outComment.includes('color:#6c757d') || !outComment.includes('This is a comment')) {
        throw new Error('Comment highlighting failed: ' + outComment);
    }

    // 2. Key highlighting
    const outKey = hl('interval_ms: 500');
    if (!outKey.includes('color:#4fc3f7') || !outKey.includes('interval_ms')) {
        throw new Error('Key highlighting failed: ' + outKey);
    }

    // 3. String highlighting
    const outStr = hl("target: 'D100'");
    if (!outStr.includes('color:#ffe082') || !outStr.includes('D100')) {
        throw new Error('String highlighting failed: ' + outStr);
    }

    // 4. Number highlighting
    const outNum = hl('value: 42');
    if (!outNum.includes('color:#f06292') || !outNum.includes('42')) {
        throw new Error('Number highlighting failed: ' + outNum);
    }

    console.log('ALL_HIGHLIGHT_CHECKS_PASSED');
    """
    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    assert "ALL_HIGHLIGHT_CHECKS_PASSED" in res.stdout
