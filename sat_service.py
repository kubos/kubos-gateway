import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class SatConnectionProtocol:
    def __init__(self, loop, service):
        self.loop = loop
        self.transport = None
        self.service = service

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.service.message_received(json.loads(data.decode())))
        # self.transport.close()

    def error_received(self, exc):
        logger.info('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        logger.info("Socket closed")
        # self.loop.call_later(5, SatConnection.connect_to_sat())


class SatService:
    def __init__(self, service_name, host, port):
        self.services = {}
        self.service_name = service_name
        self.host = host
        self.port = port
        self.transport = None
        self.protocol = None
        self.major_tom = None

    async def connect(self):
        logger.info(f'Connecting to the {self.service_name} sat service')
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(lambda: SatConnectionProtocol(loop, self),
                                                                            remote_addr=(self.host, self.port))

    async def message_received(self, message):
        logger.warning("Unhandled message_received!")
