import json
from pathlib import Path
from src.device.device_manager import DeviceManager


class PersistenceManager:
    def __init__(self, device_manager: DeviceManager, save_dir: str | None = None) -> None:
        self.device_manager = device_manager
        self._save_dir = Path(save_dir) if save_dir else Path.cwd() / "saves"
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str = "plc_state.json") -> str:
        path = self._save_dir / name
        data = {
            "devices": self.device_manager.get_all_devices()
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def load(self, name: str = "plc_state.json") -> int:
        path = self._save_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Save file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for dev_type, addresses in data.get("devices", {}).items():
            for addr_str, value in addresses.items():
                self.device_manager.write_word(dev_type, int(addr_str), value)
                count += 1
        return count
