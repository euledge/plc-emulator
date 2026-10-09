import struct
from src.protocol.base import CommandResult, ParsedRequest
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
            return self._remote_run(data)
        elif command == 0x1002:
            return self._remote_stop(data)
        elif command == 0x0801:
            return self._monitor_register(data)
        elif command == 0x0802:
            return self._monitor_execute()
        else:
            return CommandResult(success=False, error_code=ErrorCode.UNSUPPORTED_COMMAND)

    def execute_request(self, req: ParsedRequest) -> CommandResult:
        if req.command == 0x0401:
            if not req.devices:
                return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
            dev = req.devices[0]
            try:
                values = self.device_manager.batch_read(dev["type"], dev["address"], dev["count"])
                return CommandResult(
                    success=True,
                    data=struct.pack(f"<{len(values)}H", *values),
                )
            except (ValueError, IndexError):
                return CommandResult(
                    success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
                )
        elif req.command == 0x1401:
            if not req.devices:
                return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
            dev = req.devices[0]
            count = dev["count"]
            if len(req.data) != count * 2:
                return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
            try:
                values = [
                    struct.unpack_from("<H", req.data, i)[0]
                    for i in range(0, len(req.data), 2)
                ]
                self.device_manager.batch_write(dev["type"], dev["address"], values)
                return CommandResult(success=True)
            except (ValueError, IndexError):
                return CommandResult(
                    success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
                )
        elif req.command == 0x0101:
            return self._cpu_type_read()
        elif req.command == 0x0619:
            return self._loopback(req.data)
        elif req.command == 0x1001:
            return self._remote_run(req.data)
        elif req.command == 0x1002:
            return self._remote_stop(req.data)
        elif req.command == 0x0801:
            return self._monitor_register(req.data)
        elif req.command == 0x0802:
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
        if len(data) < 6:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            if len(data) != 6 + count * 2:
                return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
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
        if self.device_manager.plc_model:
            name = self.device_manager.plc_model.cpu_type_string
        else:
            name = "Q03UDE"
        cpu_name = f"{name:<20}"
        return CommandResult(success=True, data=cpu_name.encode("ascii"))

    def _loopback(self, data: bytes) -> CommandResult:
        return CommandResult(success=True, data=data)

    def _remote_run(self, data: bytes = b"") -> CommandResult:
        if 0 < len(data) < 3:
            return CommandResult(success=False, error_code=ErrorCode.PARAMETER_ERROR)
        if len(data) >= 3:
            clear_mode = data[2]
            if clear_mode == 1:
                self.device_manager.clear_memory(preserve_latch=True)
            elif clear_mode == 2:
                self.device_manager.clear_memory(preserve_latch=False)
        self.device_manager.set_plc_status("RUN")
        return CommandResult(success=True)

    def _remote_stop(self, data: bytes = b"") -> CommandResult:
        if len(data) == 1:
            return CommandResult(success=False, error_code=ErrorCode.PARAMETER_ERROR)
        self.device_manager.set_plc_status("STOP")
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
