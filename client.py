import asyncio
import json
import re

import websockets
import logging
import ssl

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

with open('config.local.json', 'r') as configfile:
    config = json.loads(configfile.read())


class SatConnection:
    def __init__(self, loop):
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        query = """
          { telemetry { timestamp, subsystem, parameter, value } }
        """
        logging.info('Send: {}'.format(query))
        self.transport.sendto(query.encode())

    def datagram_received(self, data, addr):
        logging.info("Received: {}".format(data.decode()))

        # logging.info("Close the socket")
        # self.transport.close()

    def error_received(self, exc):
        logging.info('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        logging.info("Socket closed")
        self.loop.call_later(5, SatConnection.connect_to_sat())


class Sat:
    def __init__(self):
        self.services = {}

    async def connect(self, service_name, host, port):
        logging.info("Connecting to the sat")
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(lambda: SatConnection(loop), remote_addr=(host, port))
        self.services[service_name] = (transport, protocol)


class MajorTom:
    def __init__(self):
        self.websocket = None

    async def connect(self):
        if re.match(r"^wss://", config["major-tom-endpoint"], re.IGNORECASE):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            ssl_context = None

        logging.info("Connecting to Major Tom")
        websocket = await websockets.connect(config["major-tom-endpoint"],
                                             origin=config["major-tom-origin"],
                                             extra_headers={
                                                 "X-Agent-Token": config["agent-token"]
                                             },
                                             ssl=ssl_context)
        logging.info("Connected to Major Tom")
        self.websocket = websocket
        async for message in websocket:
            await self.handle_message(message)

    async def handle_message(self, message):
        data = json.loads(message)
        logging.info("Got: {}".format(data))

    @staticmethod
    async def with_retries(coroutine):
        while True:
            try:
                return await coroutine()
            except (OSError, asyncio.streams.IncompleteReadError, websockets.ConnectionClosed) as e:
                logging.warning("Connection error encountered, retrying in 5 seconds ({})".format(e))
                await asyncio.sleep(5)
            except Exception as e:
                logging.error("Unhandled {} in `with_retries`".format(e.__class__.__name__))
                raise e


def main():
    logging.info("Starting up!")
    loop = asyncio.get_event_loop()

    sat = Sat()
    major_tom = MajorTom()
    asyncio.ensure_future(sat.connect('telemetry', config['sat-ip'], 8005))
    asyncio.ensure_future(MajorTom.with_retries(major_tom.connect))

    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    main()
