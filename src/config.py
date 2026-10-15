from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class ConfigManager:
    protocol: str = "3E"
    transport: str = "tcp"
    port: int = 5000
    data_format: str = "binary"
    plc_model: str = "Q03UDE"
    error_response_enabled: bool = True
    remote_password: str = ""

    latency_mode: str = "none"
    latency_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "protocol": self.protocol,
            "transport": self.transport,
            "port": self.port,
            "data_format": self.data_format,
            "plc_model": self.plc_model,
            "error_response_enabled": self.error_response_enabled,
            "latency_mode": self.latency_mode,
            "latency_params": dict(self.latency_params),
            "remote_password": self.remote_password,
        }

    def save_to_file(self, path: str | Path) -> str:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(file_path)

    @classmethod
    def load_from_file(cls, path: str | Path) -> "ConfigManager":
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "ConfigManager":
        cfg = cls()
        for key in (
            "protocol",
            "transport",
            "port",
            "data_format",
            "plc_model",
            "error_response_enabled",
            "latency_mode",
            "latency_params",
            "remote_password",
        ):
            if key in data:
                setattr(cfg, key, data[key])
        return cfg
