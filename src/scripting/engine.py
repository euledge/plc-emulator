import asyncio
import re
import time
from src.device.device_definition import get_device_type, DeviceType
from src.device.device_manager import DeviceManager
from src.scripting.evaluator import SafeEvaluator

DEVICE_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


class ScriptEngine:
    def __init__(self, device_manager: DeviceManager) -> None:
        self.device_manager = device_manager
        self.running = False
        self.paused = False
        self._scripts: list[dict] = []
        self._tasks: list[asyncio.Task] = []
        self._evaluator = SafeEvaluator(device_manager)
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    def load_scripts(self, scripts: list[dict]) -> None:
        self._scripts = scripts

    async def start(self) -> None:
        if self.running and self.paused:
            self.resume()
            return
        if self.running:
            return
        self.running = True
        self.paused = False
        self._pause_event.set()
        self._start_time = time.monotonic()
        for script in self._scripts:
            task = asyncio.create_task(self._run_script(script))
            self._tasks.append(task)

    def pause(self) -> None:
        if self.running and not self.paused:
            self.paused = True
            self._pause_event.clear()

    def resume(self) -> None:
        if self.running and self.paused:
            self.paused = False
            self._pause_event.set()

    async def stop(self) -> None:
        self.running = False
        self.paused = False
        self._pause_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _wait_if_paused(self) -> None:
        await self._pause_event.wait()
        while self.running and not getattr(self.device_manager, "is_running", True):
            await asyncio.sleep(0.05)

    async def _run_script(self, script: dict) -> None:
        stype = script["type"]
        try:
            if stype == "periodic":
                await self._run_periodic(script)
            elif stype == "ramp":
                await self._run_ramp(script)
            elif stype == "conditional":
                await self._run_conditional(script)
            elif stype == "sequence":
                await self._run_sequence(script)
        except asyncio.CancelledError:
            pass

    async def _run_periodic(self, script: dict) -> None:
        interval = script["interval_ms"] / 1000
        actions = script["actions"]
        while self.running:
            await self._wait_if_paused()
            await asyncio.sleep(interval)
            await self._wait_if_paused()
            if not self.running:
                break
            self._update_context()
            for action in actions:
                self._execute_action(action)

    async def _run_ramp(self, script: dict) -> None:
        target = script["target"]
        m = DEVICE_PATTERN.match(target)
        if not m:
            return
        dev_type = m.group(1).upper()
        addr = int(m.group(2))
        start_val = script["start_value"]
        end_val = script["end_value"]
        duration = script["duration_ms"] / 1000
        loop = script.get("loop", False)
        while self.running:
            await self._wait_if_paused()
            ramp_start = time.monotonic()
            paused_duration = 0.0
            while self.running:
                if self.paused:
                    p_start = time.monotonic()
                    await self._wait_if_paused()
                    paused_duration += time.monotonic() - p_start
                elapsed = time.monotonic() - ramp_start - paused_duration
                if elapsed >= duration:
                    self.device_manager.write_word(dev_type, addr, end_val)
                    if not loop:
                        return
                    break
                progress = max(0.0, min(1.0, elapsed / duration))
                val = int(start_val + (end_val - start_val) * progress)
                self.device_manager.write_word(dev_type, addr, val)
                await asyncio.sleep(0.02)

    async def _run_conditional(self, script: dict) -> None:
        interval = script.get("interval_ms", 500) / 1000
        while self.running:
            await self._wait_if_paused()
            await asyncio.sleep(interval)
            await self._wait_if_paused()
            if not self.running:
                break
            self._update_context()
            for cond in script["conditions"]:
                try:
                    result = self._evaluator.evaluate(cond["when"])
                    if result:
                        for action in cond["actions"]:
                            self._execute_action(action)
                except (ValueError, KeyError, TimeoutError):
                    pass

    async def _run_sequence(self, script: dict) -> None:
        loop = script.get("loop", False)
        while self.running:
            for step in script["steps"]:
                await self._wait_if_paused()
                if not self.running:
                    return
                await asyncio.sleep(step["wait_ms"] / 1000)
                await self._wait_if_paused()
                if not self.running:
                    return
                for action in step.get("actions", []):
                    self._execute_action(action)
            if not loop:
                break

    def _update_context(self) -> None:
        now = time.monotonic()
        elapsed = now - self._start_time
        dt = elapsed - self._evaluator.elapsed
        self._evaluator.elapsed = elapsed
        self._evaluator.delta = dt
        self._evaluator.tick += 1

    def _execute_action(self, action: dict) -> None:
        m = DEVICE_PATTERN.match(action["target"])
        if not m:
            return
        dev_type = m.group(1).upper()
        addr = int(m.group(2))

        if "value" in action:
            val = action["value"]
        elif "expr" in action:
            try:
                val = self._evaluator.evaluate(action["expr"])
            except (ValueError, TimeoutError):
                return
        else:
            return

        dtype = get_device_type(dev_type)
        if dtype == DeviceType.BIT:
            self.device_manager.write_bit(dev_type, addr, bool(val))
        else:
            self.device_manager.write_word(dev_type, addr, int(val))
