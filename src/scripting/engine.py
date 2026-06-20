import asyncio
import time
from src.scripting.evaluator import SafeEvaluator
from src.device.device_manager import DeviceManager


class ScriptEngine:
    def __init__(self, device_manager: DeviceManager) -> None:
        self.device_manager = device_manager
        self.running = False
        self._scripts: list[dict] = []
        self._tasks: list[asyncio.Task] = []
        self._evaluator = SafeEvaluator(device_manager)

    def load_scripts(self, scripts: list[dict]) -> None:
        self._scripts = scripts

    async def start(self) -> None:
        self.running = True
        self._start_time = time.monotonic()
        for script in self._scripts:
            task = asyncio.create_task(self._run_script(script))
            self._tasks.append(task)

    async def stop(self) -> None:
        self.running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

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
            await asyncio.sleep(interval)
            if not self.running:
                break
            self._update_context()
            for action in actions:
                self._execute_action(action)

    async def _run_ramp(self, script: dict) -> None:
        target = script["target"]
        start_val = script["start_value"]
        end_val = script["end_value"]
        duration = script["duration_ms"] / 1000
        loop = script.get("loop", False)
        while self.running:
            ramp_start = time.monotonic()
            while self.running:
                elapsed = time.monotonic() - ramp_start
                if elapsed >= duration:
                    self.device_manager.write_word(target[:1], int(target[1:]), end_val)
                    if not loop:
                        return
                    break
                progress = elapsed / duration
                val = int(start_val + (end_val - start_val) * progress)
                self.device_manager.write_word(target[:1], int(target[1:]), val)
                await asyncio.sleep(0.02)

    async def _run_conditional(self, script: dict) -> None:
        interval = script.get("interval_ms", 500) / 1000
        while self.running:
            await asyncio.sleep(interval)
            if not self.running:
                break
            self._update_context()
            for cond in script["conditions"]:
                try:
                    result = self._evaluator.evaluate(cond["when"])
                    if result:
                        for action in cond["actions"]:
                            self._execute_action(action)
                except (ValueError, KeyError):
                    pass

    async def _run_sequence(self, script: dict) -> None:
        loop = script.get("loop", False)
        while self.running:
            for step in script["steps"]:
                if not self.running:
                    return
                await asyncio.sleep(step["wait_ms"] / 1000)
                if not self.running:
                    return
                self._update_context()
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
        target = action["target"]
        dev_type = target[:1]
        addr = int(target[1:])

        if "value" in action:
            val = action["value"]
        elif "expr" in action:
            val = self._evaluator.evaluate(action["expr"])
        else:
            return

        self.device_manager.write_word(dev_type, addr, int(val))
