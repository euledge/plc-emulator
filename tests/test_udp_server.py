import asyncio
import pytest
from src.server.udp_server import UdpServer


@pytest.fixture
def server():
    srv = UdpServer(port=0)
    return srv


@pytest.mark.asyncio
async def test_server_start_stop(server):
    await server.start()
    assert server._transport is not None
    await server.stop()
    assert server._transport is None


@pytest.mark.asyncio
async def test_server_receives_datagram(server):
    await server.start()
    port = server.port
    transport, _ = await asyncio.get_event_loop().create_datagram_endpoint(
        lambda: asyncio.DatagramProtocol(),
        remote_addr=("127.0.0.1", port),
    )
    transport.sendto(b"test data")
    transport.close()
    await server.stop()
