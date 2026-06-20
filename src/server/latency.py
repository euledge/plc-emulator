import asyncio
import random
import time


class LatencyEmulator:
    def __init__(self) -> None:
        self.mode: str = "none"
        self.params: dict = {}
        self._delays: list[float] = []

    async def apply_delay(self) -> float:
        delay_ms = 0.0

        if self.mode == "none":
            delay_ms = 0.0
        elif self.mode == "fixed":
            delay_ms = float(self.params.get("delay_ms", 0))
            await asyncio.sleep(delay_ms / 1000)
        elif self.mode == "random":
            min_ms = float(self.params.get("min_ms", 0))
            max_ms = float(self.params.get("max_ms", 0))
            delay_ms = random.uniform(min_ms, max_ms)
            await asyncio.sleep(delay_ms / 1000)
        elif self.mode == "normal":
            mean_ms = float(self.params.get("mean_ms", 0))
            std_ms = float(self.params.get("std_ms", 0))
            delay_ms = max(0, random.gauss(mean_ms, std_ms))
            await asyncio.sleep(delay_ms / 1000)
        elif self.mode == "timeout":
            rate = float(self.params.get("timeout_rate", 0))
            if random.random() < rate:
                self._delays.append(-1)
                return -1
            delay_ms = 0.0

        self._delays.append(delay_ms)
        return delay_ms

    def stats(self) -> dict:
        if not self._delays:
            return {"count": 0, "min": 0, "max": 0, "avg": 0}
        vals = [d for d in self._delays if d >= 0]
        if not vals:
            return {"count": len(self._delays), "min": 0, "max": 0, "avg": 0}
        return {
            "count": len(self._delays),
            "min": min(vals),
            "max": max(vals),
            "avg": sum(vals) / len(vals),
        }

    def reset_stats(self) -> None:
        self._delays.clear()
