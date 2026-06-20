from dataclasses import dataclass, field


@dataclass
class ConfigManager:
    protocol: str = "3E"
    transport: str = "tcp"
    port: int = 5000
    data_format: str = "binary"
    plc_model: str = "Q03UDE"
    error_response_enabled: bool = True

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConfigManager":
        cfg = cls()
        for key in ("protocol", "transport", "port", "data_format", "plc_model",
                     "error_response_enabled", "latency_mode", "latency_params"):
            if key in data:
                setattr(cfg, key, data[key])
        return cfg
