import asyncio
import json
import re
import ssl
import logging
import websockets

logger = logging.getLogger(__name__)


class MajorTom:
    def __init__(self, config):
        self.config = config
        self.websocket = None

    async def connect(self):
        if re.match(r"^wss://", self.config["major-tom-endpoint"], re.IGNORECASE):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            ssl_context = None

        logger.info("Connecting to Major Tom")
        websocket = await websockets.connect(self.config["major-tom-endpoint"],
                                             origin=self.config["major-tom-origin"],
                                             extra_headers={
                                                 "X-Agent-Token": self.config["agent-token"]
                                             },
                                             ssl=ssl_context)
        logger.info("Connected to Major Tom")
        self.websocket = websocket
        async for message in websocket:
            await self.handle_message(message)

    async def handle_message(self, message):
        data = json.loads(message)
        logger.info("Got: {}".format(data))

    @staticmethod
    async def with_retries(coroutine):
        while True:
            try:
                return await coroutine()
            except (OSError, asyncio.streams.IncompleteReadError, websockets.ConnectionClosed) as e:
                logger.warning("Connection error encountered, retrying in 5 seconds ({})".format(e))
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("Unhandled {} in `with_retries`".format(e.__class__.__name__))
                raise e
