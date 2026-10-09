from threading import Lock
from src.device.plc_models import PlcModel


class DeviceSpecificationError(ValueError):
    """Unknown device or invalid point count."""
    pass


class AddressRangeExceededError(ValueError):
    """Start address exceeds the model range."""
    pass


class DeviceAddressInvalidError(ValueError):
    """End address exceeds the model range."""
    pass


class DeviceManager:
    def __init__(self, plc_model: PlcModel | None = None) -> None:
        self._words: dict[str, list[int]] = {}
        self._lock = Lock()
        self._plc_model = plc_model
        self._callbacks: list[callable] = []
        self.plc_status: str = "RUN"
        self._remote_password: str = ""
        self._is_locked: bool = False
    @property
    def plc_model(self) -> PlcModel | None:
        return self._plc_model

    @plc_model.setter
    def plc_model(self, model: PlcModel | None) -> None:
        self._plc_model = model


    @property
    def remote_password(self) -> str:
        return self._remote_password

    @remote_password.setter
    def remote_password(self, pwd: str) -> None:
        self._remote_password = pwd or ""
        self._is_locked = bool(self._remote_password)

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    def unlock(self, pwd: str | bytes) -> bool:
        if isinstance(pwd, bytes):
            try:
                pwd_str = pwd.decode("ascii", errors="replace").strip("\x00 \r\n")
            except Exception:
                pwd_str = ""
        else:
            pwd_str = str(pwd).strip("\x00 \r\n")

        if not self._remote_password or pwd_str == self._remote_password:
            self._is_locked = False
            return True
        return False

    def lock(self) -> None:
        if self._remote_password:
            self._is_locked = True

    def reset_connection_lock(self) -> None:
        if self._remote_password:
            self._is_locked = True
    @property
    def is_running(self) -> bool:
        return self.plc_status == "RUN"

    def set_plc_status(self, status: str) -> None:
        val = status.upper()
        if val not in ("RUN", "STOP"):
            raise ValueError(f"Invalid PLC status: {status}")
        self.plc_status = val

    def clear_memory(self, preserve_latch: bool = False, device_type: str | None = None) -> None:
        cleared_entries = []
        with self._lock:
            if device_type:
                dt = device_type.upper()
                if dt in self._words:
                    for addr, v in enumerate(self._words[dt]):
                        if v != 0:
                            cleared_entries.append((dt, addr))
                    self._words[dt] = [0] * len(self._words[dt])
            else:
                for dt in list(self._words.keys()):
                    if preserve_latch and dt.upper() == "L":
                        continue
                    for addr, v in enumerate(self._words[dt]):
                        if v != 0:
                            cleared_entries.append((dt, addr))
                    self._words[dt] = [0] * len(self._words[dt])
        for dt, addr in cleared_entries:
            self._notify(dt, addr, 0)
    def on_change(self, callback: callable) -> None:
        self._callbacks.append(callback)

    def _notify(self, device_type: str, address: int, value: int | bool) -> None:
        for cb in self._callbacks:
            cb(device_type, address, value)

    def _check_start_range(self, device_type: str, address: int) -> None:
        if self._plc_model is None:
            return
        rng = self._plc_model.device_range(device_type)
        if rng is None:
            raise DeviceSpecificationError(f"Unknown device type: {device_type}")
        lo, hi = rng
        if not (lo <= address <= hi):
            raise AddressRangeExceededError(
                f"Device {device_type}{address} start address out of range "
                f"({lo}-{hi}) for {self._plc_model.name}"
            )

    def _check_end_range(self, device_type: str, address: int) -> None:
        if self._plc_model is None:
            return
        rng = self._plc_model.device_range(device_type)
        if rng is None:
            raise DeviceSpecificationError(f"Unknown device type: {device_type}")
        lo, hi = rng
        if not (lo <= address <= hi):
            raise DeviceAddressInvalidError(
                f"Device {device_type}{address} end address out of range "
                f"({lo}-{hi}) for {self._plc_model.name}"
            )

    def _check_range(self, device_type: str, address: int) -> None:
        self._check_start_range(device_type, address)

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
        if count <= 0:
            raise DeviceSpecificationError("Point count must be greater than 0")
        end = start + count - 1
        self._check_start_range(device_type, start)
        self._check_end_range(device_type, end)
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
        if not values:
            raise DeviceSpecificationError("Values list must not be empty")
        end = start + len(values) - 1
        self._check_start_range(device_type, start)
        self._check_end_range(device_type, end)
        with self._lock:
            self._ensure_word(device_type, end)
            for i, v in enumerate(values):
                self._words[device_type][start + i] = v & 0xFFFF
        for i, v in enumerate(values):
            self._notify(device_type, start + i, v & 0xFFFF)
