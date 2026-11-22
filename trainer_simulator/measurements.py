"""FTMS and Heart Rate Service payloads, independent of the radio."""

import math
import struct
from dataclasses import dataclass
from enum import IntEnum


RATES = (0.5, 1, 2, 4, 5, 10)
POWER_RANGE = (0, 1000, 5)
RESISTANCE_RANGE = (0, 20, 1)

# Cadence, resistance level, and power measurement. Target resistance and power.
FEATURES = struct.pack("<II", (1 << 1) | (1 << 7) | (1 << 14), (1 << 2) | (1 << 3))
SUPPORTED_POWER = struct.pack("<hhH", *POWER_RANGE)
SUPPORTED_RESISTANCE = bytes(RESISTANCE_RANGE)


class Opcode(IntEnum):
    REQUEST_CONTROL = 0x00
    TARGET_RESISTANCE = 0x04
    TARGET_POWER = 0x05
    START = 0x07
    STOP_PAUSE = 0x08


class Result(IntEnum):
    SUCCESS = 0x01
    UNSUPPORTED = 0x02
    INVALID_PARAMETER = 0x03
    CONTROL_NOT_PERMITTED = 0x05


def in_range(value: int, limits: tuple[int, int, int]) -> bool:
    minimum, maximum, step = limits
    return minimum <= value <= maximum and (value - minimum) % step == 0


@dataclass
class TrainerLoad:
    controlled: bool = False
    running: bool = False
    target_watts: int | None = None
    target_resistance: int | None = None

    def command(self, packet: bytes) -> bytes:
        opcode = packet[0]
        result = self._apply(opcode, packet[1:])
        return bytes((0x80, opcode, result))

    def _apply(self, opcode: int, parameters: bytes) -> Result:
        if opcode not in Opcode:
            return Result.UNSUPPORTED
        if opcode == Opcode.REQUEST_CONTROL:
            if parameters:
                return Result.INVALID_PARAMETER
            self.controlled = True
            return Result.SUCCESS
        if not self.controlled:
            return Result.CONTROL_NOT_PERMITTED
        if opcode == Opcode.START:
            if parameters:
                return Result.INVALID_PARAMETER
            self.running = True
        elif opcode == Opcode.STOP_PAUSE:
            if parameters not in (b"\x01", b"\x02"):
                return Result.INVALID_PARAMETER
            self.running = False
            if parameters == b"\x01":
                self.target_watts = self.target_resistance = None
        else:
            if len(parameters) != 2:
                return Result.INVALID_PARAMETER
            target = int.from_bytes(parameters, "little", signed=True)
            if opcode == Opcode.TARGET_POWER:
                if not in_range(target, POWER_RANGE):
                    return Result.INVALID_PARAMETER
                self.target_watts, self.target_resistance = target, None
            else:
                resistance, remainder = divmod(target, 10)
                if remainder or not in_range(resistance, RESISTANCE_RANGE):
                    return Result.INVALID_PARAMETER
                self.target_watts, self.target_resistance = None, resistance
        return Result.SUCCESS

    def measurement(self, cadence: int) -> tuple[bytes, int]:
        resistance = self.target_resistance or 0
        watts = 0
        if self.running:
            if self.target_watts is None:
                watts = round(cadence * (0.5 + 0.25 * resistance))
            else:
                watts = round(self.target_watts * min(cadence / 85, 1))
        # Speed (0.01 km/h), cadence (0.5 rpm), resistance (whole level), watts.
        packet = struct.pack("<HHHBh", 0x0064, cadence * 30, cadence * 2, resistance, watts)
        return packet, watts


def heart_rate(bpm: int) -> bytes:
    return bytes((0, bpm))


def next_deadline(previous: float, now: float, rate: float) -> float:
    """Advance on the original monotonic grid to the first future deadline."""
    period = 1 / rate
    steps = max(1, math.floor((now - previous) / period) + 1)
    deadline = previous + steps * period
    return deadline if deadline > now else deadline + period
