from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedRequest:
    command: int = 0
    subcommand: int = 0
    data: bytes = b""
    devices: list[dict[str, Any]] = field(default_factory=list)


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
    def build_response(self, parsed: ParsedRequest, result: CommandResult) -> bytes:
        ...

    @abstractmethod
    def detect(self, data: bytes) -> bool:
        ...
