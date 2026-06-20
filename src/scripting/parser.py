import yaml


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
