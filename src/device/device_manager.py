from threading import Lock
from src.device.plc_models import PlcModel


class DeviceManager:
    def __init__(self, plc_model: PlcModel | None = None) -> None:
        self._words: dict[str, list[int]] = {}
        self._lock = Lock()
        self._plc_model = plc_model
        self._callbacks: list[callable] = []

    def on_change(self, callback: callable) -> None:
        self._callbacks.append(callback)

    def _notify(self, device_type: str, address: int, value: int | bool) -> None:
        for cb in self._callbacks:
            cb(device_type, address, value)

    def _check_range(self, device_type: str, address: int) -> None:
        if self._plc_model is None:
            return
        rng = self._plc_model.device_range(device_type)
        if rng is None:
            return
        lo, hi = rng
        if not (lo <= address <= hi):
            raise ValueError(
                f"Device {device_type}{address} out of range "
                f"({lo}-{hi}) for {self._plc_model.name}"
            )

    def _ensure_word(self, device_type: str, address: int) -> None:
        if device_type not in self._words:
            self._words[device_type] = []
        words = self._words[device_type]
        needed = address + 1
        if len(words) < needed:
            words.extend([0] * (needed - len(words)))

    def read_word(self, device_type: str, address: int) -> int:
        self._check_range(device_type, address)
        with self._lock:
            self._ensure_word(device_type, address)
            return self._words[device_type][address] & 0xFFFF

    def write_word(self, device_type: str, address: int, value: int) -> None:
        self._check_range(device_type, address)
        with self._lock:
            self._ensure_word(device_type, address)
            self._words[device_type][address] = value & 0xFFFF
        self._notify(device_type, address, value & 0xFFFF)

    def read_bit(self, device_type: str, address: int) -> bool:
        self._check_range(device_type, address)
        word_addr = address // 16
        bit_pos = address % 16
        word = self.read_word(device_type, word_addr)
        return bool((word >> bit_pos) & 1)

    def write_bit(self, device_type: str, address: int, value: bool) -> None:
        self._check_range(device_type, address)
        word_addr = address // 16
        bit_pos = address % 16
        with self._lock:
            self._ensure_word(device_type, word_addr)
            word = self._words[device_type][word_addr]
            if value:
                word |= 1 << bit_pos
            else:
                word &= ~(1 << bit_pos)
            self._words[device_type][word_addr] = word & 0xFFFF
        self._notify(device_type, address, value)

    def batch_read(self, device_type: str, start: int, count: int) -> list[int]:
        end = start + count - 1
        self._check_range(device_type, start)
        self._check_range(device_type, end)
        with self._lock:
            self._ensure_word(device_type, end)
            return [self._words[device_type][start + i] & 0xFFFF for i in range(count)]

    def get_all_devices(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        with self._lock:
            for dev_type, words in self._words.items():
                result[dev_type] = {str(i): v for i, v in enumerate(words) if v != 0}
        return result

    def batch_write(self, device_type: str, start: int, values: list[int]) -> None:
        end = start + len(values) - 1
        self._check_range(device_type, start)
        self._check_range(device_type, end)
        with self._lock:
            self._ensure_word(device_type, end)
            for i, v in enumerate(values):
                self._words[device_type][start + i] = v & 0xFFFF
        for i, v in enumerate(values):
            self._notify(device_type, start + i, v & 0xFFFF)
