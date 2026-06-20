import asyncio
import pytest
from src.server.tcp_server import TcpServer


@pytest.fixture
def server():
    srv = TcpServer(port=0)
    return srv


@pytest.mark.asyncio
async def test_server_start_stop(server):
    await server.start()
    assert server._server is not None
    await server.stop()
    assert server._server is None


@pytest.mark.asyncio
async def test_server_accepts_connection(server):
    await server.start()
    port = server.port
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    assert reader is not None
    assert writer is not None
    writer.close()
    await writer.wait_closed()
    await server.stop()
