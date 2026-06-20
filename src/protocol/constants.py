from enum import IntEnum


class SubHeader(IntEnum):
    REQUEST_3E = 0x5000
    RESPONSE_3E = 0xD000
    REQUEST_4E = 0x5400
    RESPONSE_4E = 0xD400


class CommandCode(IntEnum):
    BATCH_READ = 0x0401
    BATCH_WRITE = 0x1401
    RANDOM_READ = 0x0403
    RANDOM_WRITE = 0x1402
    MONITOR_REGISTER = 0x0801
    MONITOR_EXECUTE = 0x0802
    CPU_TYPE_READ = 0x0101
    REMOTE_RUN = 0x1001
    REMOTE_STOP = 0x1002
    LOOPBACK_TEST = 0x0619
    REMOTE_PASSWORD_UNLOCK = 0x1630
    REMOTE_PASSWORD_LOCK = 0x1631


class SubCommand(IntEnum):
    WORD = 0x0000
    BIT = 0x0001
    WORD_EXT = 0x0002
    BIT_EXT = 0x0003


class ErrorCode(IntEnum):
    NORMAL = 0x0000
    COMMAND_TYPE_INVALID = 0xC050
    ADDRESS_RANGE_EXCEEDED = 0xC051
    DEVICE_SPECIFICATION_ERROR = 0xC056
    DEVICE_ADDRESS_INVALID = 0xC058
    UNSUPPORTED_COMMAND = 0xC059
    PARAMETER_ERROR = 0xC05B
    DATA_LENGTH_MISMATCH = 0xC061


class DeviceCode3E(IntEnum):
    X = 0x9C
    Y = 0x9D
    M = 0x90
    L = 0x92
    F = 0x93
    V = 0x94
    B = 0xA0
    SM = 0x91
    SB = 0xA1
    S = 0x98
    TS = 0xC1
    TC = 0xC0
    CS = 0xC4
    CC = 0xC3
    D = 0xA8
    W = 0xB4
    R = 0xAF
    ZR = 0xB0
    SD = 0xA9
    SW = 0xB5
    TN = 0xC2
    CN = 0xC5


class DeviceCode1E(IntEnum):
    X = 0x58
    Y = 0x59
    M = 0x4D
    L = 0x4C
    B = 0x42
    D = 0x44
    W = 0x57
    R = 0x52


DEVICE_CODE_TO_NAME_3E: dict[int, str] = {
    v: k for k, v in DeviceCode3E.__members__.items()
}

DEVICE_NAME_TO_CODE_3E: dict[str, int] = {
    k: v for k, v in DeviceCode3E.__members__.items()
}

DEVICE_CODE_TO_NAME_1E: dict[int, str] = {
    v: k for k, v in DeviceCode1E.__members__.items()
}

DEVICE_NAME_TO_CODE_1E: dict[str, int] = {
    k: v for k, v in DeviceCode1E.__members__.items()
}
