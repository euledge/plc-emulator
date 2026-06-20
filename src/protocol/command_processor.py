import struct
from src.protocol.base import CommandResult
from src.protocol.device_parser import parse_device_mc
from src.device.device_manager import DeviceManager
from src.protocol.constants import ErrorCode


class CommandProcessor:
    def __init__(self, device_manager: DeviceManager) -> None:
        self.device_manager = device_manager
        self._monitor_devices: list[dict] = []

    def execute(self, command: int, subcommand: int, data: bytes) -> CommandResult:
        if command == 0x0401:
            return self._batch_read(data)
        elif command == 0x1401:
            return self._batch_write(data)
        elif command == 0x0101:
            return self._cpu_type_read()
        elif command == 0x0619:
            return self._loopback(data)
        elif command == 0x1001:
            return self._remote_run()
        elif command == 0x1002:
            return self._remote_stop()
        elif command == 0x0801:
            return self._monitor_register(data)
        elif command == 0x0802:
            return self._monitor_execute()
        else:
            return CommandResult(success=False, error_code=ErrorCode.UNSUPPORTED_COMMAND)

    def _batch_read(self, data: bytes) -> CommandResult:
        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            values = self.device_manager.batch_read(dev_type, dev_addr, count)
            return CommandResult(
                success=True,
                data=struct.pack(f"<{len(values)}H", *values),
            )
        except (ValueError, IndexError) as e:
            return CommandResult(
                success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
            )

    def _batch_write(self, data: bytes) -> CommandResult:
        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            values_data = data[6:6 + count * 2]
            values = [
                struct.unpack_from("<H", values_data, i)[0]
                for i in range(0, len(values_data), 2)
            ]
            self.device_manager.batch_write(dev_type, dev_addr, values)
            return CommandResult(success=True)
        except (ValueError, IndexError) as e:
            return CommandResult(
                success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
            )

    def _cpu_type_read(self) -> CommandResult:
        cpu_name = "Q03UDE              "
        return CommandResult(success=True, data=cpu_name.encode("ascii"))

    def _loopback(self, data: bytes) -> CommandResult:
        return CommandResult(success=True, data=data)

    def _remote_run(self) -> CommandResult:
        return CommandResult(success=True)

    def _remote_stop(self) -> CommandResult:
        return CommandResult(success=True)

    def _monitor_register(self, data: bytes) -> CommandResult:
        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            self._monitor_devices = [
                {"type": dev_type, "address": dev_addr + i}
                for i in range(count)
            ]
            return CommandResult(success=True)
        except (ValueError, IndexError):
            return CommandResult(
                success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
            )

    def _monitor_execute(self) -> CommandResult:
        try:
            values = []
            for dev in self._monitor_devices:
                v = self.device_manager.read_word(dev["type"], dev["address"])
                values.append(v)
            return CommandResult(
                success=True,
                data=struct.pack(f"<{len(values)}H", *values),
            )
        except ValueError:
            return CommandResult(
                success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
            )
