import pytest
from src.server.latency import LatencyEmulator


@pytest.mark.asyncio
async def test_none_mode_returns_zero():
    emu = LatencyEmulator()
    emu.mode = "none"
    result = await emu.apply_delay()
    assert result == 0


@pytest.mark.asyncio
async def test_fixed_mode():
    emu = LatencyEmulator()
    emu.mode = "fixed"
    emu.params = {"delay_ms": 10}
    result = await emu.apply_delay()
    assert result >= 10


@pytest.mark.asyncio
async def test_random_mode_within_range():
    emu = LatencyEmulator()
    emu.mode = "random"
    emu.params = {"min_ms": 5, "max_ms": 20}
    for _ in range(10):
        result = await emu.apply_delay()
        assert 5 <= result <= 20


@pytest.mark.asyncio
async def test_stats_tracking():
    emu = LatencyEmulator()
    emu.mode = "fixed"
    emu.params = {"delay_ms": 5}
    await emu.apply_delay()
    await emu.apply_delay()
    await emu.apply_delay()
    stats = emu.stats()
    assert stats["count"] == 3
    assert stats["min"] >= 5
    assert stats["max"] >= 5
    assert stats["avg"] >= 5


@pytest.mark.asyncio
async def test_timeout_mode_returns_minus_one():
    emu = LatencyEmulator()
    emu.mode = "timeout"
    emu.params = {"timeout_rate": 1.0}
    result = await emu.apply_delay()
    assert result == -1
