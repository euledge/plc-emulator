import ast
import re
import yaml
from src.device.device_definition import DeviceType, get_device_type
from src.scripting.evaluator import SafeEvaluator

DEVICE_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")
class ScriptParser:

    @classmethod
    def parse(cls, yaml_text: str) -> list[dict]:
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {e}")

        if not isinstance(data, dict) or "scripts" not in data:
            raise ValueError("Missing 'scripts' key in YAML")

        scripts = data["scripts"]
        if not isinstance(scripts, list):
            raise ValueError("'scripts' must be a list")

        for s in scripts:
            cls._validate(s)

        return scripts

    @classmethod
    def _validate(cls, script: dict) -> None:
        if "name" not in script:
            raise ValueError("Script missing 'name'")
        if "type" not in script:
            raise ValueError("Script missing 'type'")
        stype = script["type"]
        if stype not in ("periodic", "conditional", "sequence", "ramp"):
            raise ValueError(f"Unknown script type: {stype}")
        if stype == "periodic":
            if "actions" not in script:
                raise ValueError("Periodic script missing 'actions'")
        elif stype == "conditional":
            if "conditions" not in script:
                raise ValueError("Conditional script missing 'conditions'")
        elif stype == "sequence":
            if "steps" not in script:
                raise ValueError("Sequence script missing 'steps'")
        elif stype == "ramp":
            if "target" not in script:
                raise ValueError("Ramp script missing 'target'")

    @classmethod
    def validate_content(cls, yaml_text: str) -> tuple[bool, list[str]]:
        errors = []
        if not yaml_text or not yaml_text.strip():
            return False, ["Script content is empty"]

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            msg = str(e)
            if hasattr(e, "problem_mark") and e.problem_mark:
                line = e.problem_mark.line + 1
                col = e.problem_mark.column + 1
                msg = f"YAML syntax error at line {line}, col {col}: {e.problem or e}"
            return False, [msg]

        if not data:
            return False, ["Script content is empty"]

        scripts = []
        if isinstance(data, list):
            scripts = data
        elif isinstance(data, dict):
            if "scripts" in data and isinstance(data["scripts"], list):
                scripts = data["scripts"]
            else:
                scripts = [data]
        else:
            return False, ["Script content must be a YAML mapping or list"]

        evaluator = SafeEvaluator()

        for idx, s in enumerate(scripts):
            prefix = f"Script #{idx + 1}" + (f" ('{s.get('name')}')" if isinstance(s, dict) and s.get("name") else "")
            if not isinstance(s, dict):
                errors.append(f"{prefix}: must be a dictionary")
                continue

            stype = s.get("type")
            if not stype:
                errors.append(f"{prefix}: missing 'type'")
                continue
            if stype not in ("periodic", "conditional", "sequence", "ramp"):
                errors.append(f"{prefix}: unknown script type '{stype}'")
                continue

            if stype == "periodic":
                if "interval_ms" not in s or not isinstance(s["interval_ms"], (int, float)) or s["interval_ms"] <= 0:
                    errors.append(f"{prefix}: 'interval_ms' must be a positive number")
                if "actions" not in s or not isinstance(s["actions"], list):
                    errors.append(f"{prefix}: missing or invalid 'actions' list")
                else:
                    for a_idx, action in enumerate(s["actions"]):
                        cls._validate_action(prefix, f"action #{a_idx + 1}", action, evaluator, errors)

            elif stype == "ramp":
                target = s.get("target")
                if not target or not isinstance(target, str) or not DEVICE_PATTERN.match(target):
                    errors.append(f"{prefix}: 'target' must be a valid device (e.g. D100)")
                if "start_value" not in s or not isinstance(s["start_value"], (int, float)):
                    errors.append(f"{prefix}: 'start_value' must be a number")
                if "end_value" not in s or not isinstance(s["end_value"], (int, float)):
                    errors.append(f"{prefix}: 'end_value' must be a number")
                if "duration_ms" not in s or not isinstance(s["duration_ms"], (int, float)) or s["duration_ms"] <= 0:
                    errors.append(f"{prefix}: 'duration_ms' must be a positive number")

            elif stype == "conditional":
                if "conditions" not in s or not isinstance(s["conditions"], list):
                    errors.append(f"{prefix}: missing or invalid 'conditions' list")
                else:
                    for c_idx, cond in enumerate(s["conditions"]):
                        c_name = f"condition #{c_idx + 1}"
                        if not isinstance(cond, dict):
                            errors.append(f"{prefix} {c_name}: must be a dictionary")
                            continue
                        when_expr = cond.get("when")
                        if not when_expr or not isinstance(when_expr, str):
                            errors.append(f"{prefix} {c_name}: missing 'when' expression")
                        else:
                            cls._validate_expression(prefix, f"{c_name} 'when'", when_expr, evaluator, errors)
                        actions = cond.get("actions", [])
                        if not isinstance(actions, list):
                            errors.append(f"{prefix} {c_name}: 'actions' must be a list")
                        else:
                            for a_idx, action in enumerate(actions):
                                cls._validate_action(prefix, f"{c_name} action #{a_idx + 1}", action, evaluator, errors)

            elif stype == "sequence":
                if "steps" not in s or not isinstance(s["steps"], list):
                    errors.append(f"{prefix}: missing or invalid 'steps' list")
                else:
                    for step_idx, step in enumerate(s["steps"]):
                        s_name = f"step #{step_idx + 1}"
                        if not isinstance(step, dict):
                            errors.append(f"{prefix} {s_name}: must be a dictionary")
                            continue
                        if "wait_ms" not in step or not isinstance(step["wait_ms"], (int, float)) or step["wait_ms"] < 0:
                            errors.append(f"{prefix} {s_name}: 'wait_ms' must be a non-negative number")
                        actions = step.get("actions", [])
                        if not isinstance(actions, list):
                            errors.append(f"{prefix} {s_name}: 'actions' must be a list")
                        else:
                            for a_idx, action in enumerate(actions):
                                cls._validate_action(prefix, f"{s_name} action #{a_idx + 1}", action, evaluator, errors)

        return (len(errors) == 0), errors

    @classmethod
    def _validate_action(cls, prefix: str, label: str, action: dict, evaluator, errors: list[str]) -> None:
        if not isinstance(action, dict):
            errors.append(f"{prefix} {label}: action must be a dictionary")
            return
        target = action.get("target")
        if not target or not isinstance(target, str) or not DEVICE_PATTERN.match(target):
            errors.append(f"{prefix} {label}: invalid target '{target}'")
        if "value" not in action and "expr" not in action:
            errors.append(f"{prefix} {label}: action must have either 'value' or 'expr'")
        data_type = action.get("data_type")
        if data_type is not None:
            if not isinstance(data_type, str) or data_type.lower() not in {"dword", "long", "float32", "ascii"}:
                errors.append(f"{prefix} {label}: unsupported 'data_type'")
            else:
                data_type = data_type.lower()
                match = DEVICE_PATTERN.match(target) if isinstance(target, str) else None
                if match and get_device_type(match.group(1).upper()) == DeviceType.BIT:
                    errors.append(f"{prefix} {label}: typed values require a word device")
                if data_type == "ascii":
                    if "expr" in action:
                        errors.append(f"{prefix} {label}: ascii requires a string 'value'")
                    if "value" in action and not isinstance(action["value"], str):
                        errors.append(f"{prefix} {label}: ascii 'value' must be a string")
                elif "value" in action:
                    value = action["value"]
                    if data_type in {"dword", "long"}:
                        if isinstance(value, bool) or not isinstance(value, int):
                            errors.append(f"{prefix} {label}: {data_type} 'value' must be an integer")
                        elif data_type == "dword" and not 0 <= value <= 0xFFFFFFFF:
                            errors.append(f"{prefix} {label}: dword 'value' is out of range")
                        elif data_type == "long" and not -0x80000000 <= value <= 0x7FFFFFFF:
                            errors.append(f"{prefix} {label}: long 'value' is out of range")
                    elif isinstance(value, bool) or not isinstance(value, (int, float)):
                        errors.append(f"{prefix} {label}: numeric typed 'value' must be a number")
                if "length" in action:
                    if data_type != "ascii":
                        errors.append(f"{prefix} {label}: 'length' is only valid for ascii")
                    elif not isinstance(action["length"], int) or action["length"] <= 0:
                        errors.append(f"{prefix} {label}: ascii 'length' must be positive")
                    elif "value" in action and isinstance(action["value"], str) and len(action["value"]) > action["length"]:
                        errors.append(f"{prefix} {label}: ascii value must fit 'length'")
        elif "length" in action:
            errors.append(f"{prefix} {label}: 'length' requires a typed ascii value")
        if "expr" in action:
            expr_str = action["expr"]
            if not isinstance(expr_str, str):
                errors.append(f"{prefix} {label}: 'expr' must be a string")
            else:
                cls._validate_expression(prefix, f"{label} 'expr'", expr_str, evaluator, errors)

    @classmethod
    def _validate_expression(cls, prefix: str, label: str, expr: str, evaluator, errors: list[str]) -> None:
        try:
            tree = ast.parse(expr, mode="eval")
            evaluator._check(tree)
        except SyntaxError as e:
            errors.append(f"{prefix} {label}: syntax error in expression '{expr}': {e.msg}")
        except ValueError as e:
            errors.append(f"{prefix} {label}: unsafe expression '{expr}': {e}")
        except TimeoutError as e:
            errors.append(f"{prefix} {label}: expression '{expr}' too complex: {e}")
