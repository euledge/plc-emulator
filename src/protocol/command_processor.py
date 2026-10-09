import struct
from src.protocol.base import CommandResult, ParsedRequest
from src.protocol.device_parser import parse_device_mc, parse_device_slmp
from src.device.device_manager import (
    DeviceManager,
    DeviceSpecificationError,
    AddressRangeExceededError,
    DeviceAddressInvalidError,
)
from src.protocol.constants import ErrorCode


class CommandProcessor:
    def __init__(self, device_manager: DeviceManager) -> None:
        self.device_manager = device_manager
        self._monitor_devices: list[dict] = []

    def execute(self, command: int, subcommand: int, data: bytes) -> CommandResult:
        if command == 0x0401:
            return self._batch_read(data, subcommand=subcommand)
        elif command == 0x1401:
            return self._batch_write(data, subcommand=subcommand)
        elif command == 0x0403:
            return self._random_read(data, subcommand=subcommand)
        elif command == 0x1402:
            return self._random_write(data, subcommand=subcommand)
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
            dev_type = dev["type"]
            start_addr = dev["address"]
            count = dev["count"]
            is_bit = req.subcommand in (0x0001, 0x0003)
            try:
                if is_bit:
                    if count <= 0:
                        return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                    self.device_manager._check_start_range(dev_type, start_addr)
                    self.device_manager._check_end_range(dev_type, start_addr + count - 1)
                    bit_values = [
                        1 if self.device_manager.read_bit(dev_type, start_addr + i) else 0
                        for i in range(count)
                    ]
                    packed = bytearray()
                    for i in range(0, count, 2):
                        b0 = bit_values[i]
                        b1 = bit_values[i + 1] if i + 1 < count else 0
                        packed.append(((b0 & 1) << 4) | (b1 & 1))
                    return CommandResult(success=True, data=bytes(packed))
                else:
                    values = self.device_manager.batch_read(dev_type, start_addr, count)
                    return CommandResult(
                        success=True,
                        data=struct.pack(f"<{len(values)}H", *values),
                    )
            except DeviceSpecificationError:
                return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
            except AddressRangeExceededError:
                return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
            except DeviceAddressInvalidError:
                return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
            except (ValueError, IndexError):
                return CommandResult(
                    success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
                )
        elif req.command == 0x1401:
            if not req.devices:
                return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
            dev = req.devices[0]
            dev_type = dev["type"]
            start_addr = dev["address"]
            count = dev["count"]
            is_bit = req.subcommand in (0x0001, 0x0003)
            if is_bit:
                if count <= 0:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                expected_len = (count + 1) // 2
                if len(req.data) != expected_len:
                    return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                try:
                    self.device_manager._check_start_range(dev_type, start_addr)
                    self.device_manager._check_end_range(dev_type, start_addr + count - 1)
                    for i in range(count):
                        byte_idx = i // 2
                        is_high = (i % 2 == 0)
                        byte_val = req.data[byte_idx]
                        bit_val = bool((byte_val >> 4) & 1 if is_high else (byte_val & 1))
                        self.device_manager.write_bit(dev_type, start_addr + i, bit_val)
                    return CommandResult(success=True)
                except DeviceSpecificationError:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                except AddressRangeExceededError:
                    return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
                except DeviceAddressInvalidError:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
                except (ValueError, IndexError):
                    return CommandResult(
                        success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
                    )
            else:
                if count <= 0:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                if len(req.data) != count * 2:
                    return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                try:
                    values = [
                        struct.unpack_from("<H", req.data, i)[0]
                        for i in range(0, len(req.data), 2)
                    ]
                    self.device_manager.batch_write(dev_type, start_addr, values)
                    return CommandResult(success=True)
                except DeviceSpecificationError:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                except AddressRangeExceededError:
                    return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
                except DeviceAddressInvalidError:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
                except (ValueError, IndexError):
                    return CommandResult(
                        success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
                    )
        elif req.command == 0x0403:
            return self._random_read(req.data, subcommand=req.subcommand)
        elif req.command == 0x1402:
            return self._random_write(req.data, subcommand=req.subcommand)
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
    def _batch_read(self, data: bytes, subcommand: int = 0x0000) -> CommandResult:
        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            is_bit = subcommand in (0x0001, 0x0003)
            if is_bit:
                if count <= 0:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                self.device_manager._check_start_range(dev_type, dev_addr)
                self.device_manager._check_end_range(dev_type, dev_addr + count - 1)
                bit_values = [
                    1 if self.device_manager.read_bit(dev_type, dev_addr + i) else 0
                    for i in range(count)
                ]
                packed = bytearray()
                for i in range(0, count, 2):
                    b0 = bit_values[i]
                    b1 = bit_values[i + 1] if i + 1 < count else 0
                    packed.append(((b0 & 1) << 4) | (b1 & 1))
                return CommandResult(success=True, data=bytes(packed))
            else:
                values = self.device_manager.batch_read(dev_type, dev_addr, count)
                return CommandResult(
                    success=True,
                    data=struct.pack(f"<{len(values)}H", *values),
                )
        except DeviceSpecificationError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
        except AddressRangeExceededError:
            return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
        except DeviceAddressInvalidError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
        except (ValueError, IndexError):
            return CommandResult(
                success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID
            )

    def _batch_write(self, data: bytes, subcommand: int = 0x0000) -> CommandResult:
        if len(data) < 6:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        try:
            dev_type, dev_addr = parse_device_mc(data[:4])
            count = struct.unpack_from("<H", data, 4)[0]
            is_bit = subcommand in (0x0001, 0x0003)
            if is_bit:
                if count <= 0:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                expected_len = (count + 1) // 2
                if len(data) != 6 + expected_len:
                    return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                values_data = data[6:6 + expected_len]
                self.device_manager._check_start_range(dev_type, dev_addr)
                self.device_manager._check_end_range(dev_type, dev_addr + count - 1)
                for i in range(count):
                    byte_idx = i // 2
                    is_high = (i % 2 == 0)
                    byte_val = values_data[byte_idx]
                    bit_val = bool((byte_val >> 4) & 1 if is_high else (byte_val & 1))
                    self.device_manager.write_bit(dev_type, dev_addr + i, bit_val)
                return CommandResult(success=True)
            else:
                if count <= 0:
                    return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
                if len(data) != 6 + count * 2:
                    return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                values_data = data[6:6 + count * 2]
                values = [
                    struct.unpack_from("<H", values_data, i)[0]
                    for i in range(0, len(values_data), 2)
                ]
                self.device_manager.batch_write(dev_type, dev_addr, values)
                return CommandResult(success=True)
        except DeviceSpecificationError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
        except AddressRangeExceededError:
            return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
        except DeviceAddressInvalidError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
        except (ValueError, IndexError):
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

    def _random_read(self, data: bytes, subcommand: int = 0x0000) -> CommandResult:
        if len(data) < 2:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        word_count = data[0]
        dword_count = data[1]
        is_slmp = subcommand in (0x0002, 0x0003)
        dev_len = 6 if is_slmp else 4
        parser = parse_device_slmp if is_slmp else parse_device_mc

        expected_len = 2 + word_count * dev_len + dword_count * dev_len
        if len(data) < expected_len:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        try:
            offset = 2
            word_vals = []
            for _ in range(word_count):
                dev_type, dev_addr = parser(data[offset:offset + dev_len])
                offset += dev_len
                self.device_manager._check_start_range(dev_type, dev_addr)
                val = self.device_manager.read_word(dev_type, dev_addr)
                word_vals.append(val)

            dword_vals = []
            for _ in range(dword_count):
                dev_type, dev_addr = parser(data[offset:offset + dev_len])
                offset += dev_len
                self.device_manager._check_start_range(dev_type, dev_addr)
                self.device_manager._check_end_range(dev_type, dev_addr + 1)
                w_low = self.device_manager.read_word(dev_type, dev_addr)
                w_high = self.device_manager.read_word(dev_type, dev_addr + 1)
                val = w_low | (w_high << 16)
                dword_vals.append(val)

            result_bytes = b"".join(struct.pack("<H", v) for v in word_vals) + b"".join(
                struct.pack("<I", v) for v in dword_vals
            )
            return CommandResult(success=True, data=result_bytes)
        except DeviceSpecificationError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
        except AddressRangeExceededError:
            return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
        except DeviceAddressInvalidError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
        except (ValueError, IndexError):
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
    def _random_write(self, data: bytes, subcommand: int = 0x0000) -> CommandResult:
        if len(data) < 2:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        word_count = data[0]
        dword_count = data[1]
        is_slmp = subcommand in (0x0002, 0x0003)
        dev_len = 6 if is_slmp else 4
        parser = parse_device_slmp if is_slmp else parse_device_mc

        word_entry_len = dev_len + 2
        dword_entry_len = dev_len + 4
        expected_len = 2 + word_count * word_entry_len + dword_count * dword_entry_len
        if len(data) != expected_len:
            return CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)

        try:
            offset = 2
            word_writes = []
            for _ in range(word_count):
                dev_type, dev_addr = parser(data[offset:offset + dev_len])
                val = struct.unpack_from("<H", data, offset + dev_len)[0]
                offset += word_entry_len
                self.device_manager._check_start_range(dev_type, dev_addr)
                word_writes.append((dev_type, dev_addr, val))

            dword_writes = []
            for _ in range(dword_count):
                dev_type, dev_addr = parser(data[offset:offset + dev_len])
                val = struct.unpack_from("<I", data, offset + dev_len)[0]
                offset += dword_entry_len
                self.device_manager._check_start_range(dev_type, dev_addr)
                self.device_manager._check_end_range(dev_type, dev_addr + 1)
                dword_writes.append((dev_type, dev_addr, val))

            for dev_type, dev_addr, val in word_writes:
                self.device_manager.write_word(dev_type, dev_addr, val)

            for dev_type, dev_addr, val in dword_writes:
                self.device_manager.write_word(dev_type, dev_addr, val & 0xFFFF)
                self.device_manager.write_word(dev_type, dev_addr + 1, (val >> 16) & 0xFFFF)

            return CommandResult(success=True)
        except DeviceSpecificationError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
        except AddressRangeExceededError:
            return CommandResult(success=False, error_code=ErrorCode.ADDRESS_RANGE_EXCEEDED)
        except DeviceAddressInvalidError:
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
        except (ValueError, IndexError):
            return CommandResult(success=False, error_code=ErrorCode.DEVICE_ADDRESS_INVALID)
