from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedRequest:
    command: int = 0
    subcommand: int = 0
    data: bytes = b""
    access_path: bytes = b"\x00\x00\x00\x00"
    devices: list[dict[str, Any]] = field(default_factory=list)
    serial: bytes = b"\x00\x00"
    frame_type: str = ""


@dataclass
class CommandResult:
    success: bool = True
    data: bytes = b""
    error_code: int = 0x0000


class ProtocolHandler(ABC):
    @abstractmethod
    def parse_request(self, data: bytes) -> ParsedRequest:
        ...

    @abstractmethod
    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        ...

    @abstractmethod
    def detect(self, data: bytes) -> bool:
        ...

    def extract_frame(self, buf: bytearray) -> bytes | None:
        """Extract a complete frame from buffer, removing consumed bytes."""
        return None
