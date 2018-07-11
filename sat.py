import asyncio
import logging

logger = logging.getLogger(__name__)


class SatConnection:
    def __init__(self, loop):
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        query = """
          { telemetry { timestamp, subsystem, parameter, value } }
        """
        logger.info('Send: {}'.format(query))
        self.transport.sendto(query.encode())

    def datagram_received(self, data, addr):
        logger.info("Received: {}".format(data.decode()))

        # logger.info("Close the socket")
        # self.transport.close()

    def error_received(self, exc):
        logger.info('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        logger.info("Socket closed")
        # self.loop.call_later(5, SatConnection.connect_to_sat())


class Sat:
    def __init__(self, config):
        self.services = {}
        self.config = config

    async def connect(self, service_name, host, port):
        logger.info("Connecting to the sat")
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(lambda: SatConnection(loop), remote_addr=(host, port))
        self.services[service_name] = (transport, protocol)
