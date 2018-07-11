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
        await self.subscribe()
        async for message in websocket:
            await self.handle_message(message)

    async def subscribe(self):
        await self.websocket.send(
            json.dumps({"command": "subscribe", "identifier": json.dumps({"channel": "GatewayChannel"})}))

    async def handle_message(self, message):
        data = json.loads(message)

        if "type" in data and data["type"] in ['ping', 'confirm_subscription', 'welcome']:
            return

        logger.debug(data)

        if "message" not in data:
            logger.warning("Unknown message received from Major Tom: {}".format(message))
        elif data["message"]["type"] == "command":
            logger.warning("Commands not implemented")
        elif data["message"]["type"] == "script":
            logger.warning("Scripts not implemented")
        elif data["message"]["type"] == "error":
            logger.warning("Error from backend: {}".format(data["error"]))
        else:
            logger.warning(
                "Unknown message type {} received from Major Tom: {}".format(data["message"]["type"], message))

    async def transmit(self, payload):
        logger.debug("To Major Tom: {}".format(payload))
        await self.websocket.send(json.dumps(
            {"command": "message", "identifier": json.dumps({"channel": "GatewayChannel"}), "data": json.dumps(payload)}))

    async def command_error(self, command_id, errors):
        await self.transmit(
            {"type": "command_status", "command_status": {"source": "adapter", "id": command_id, "errors": errors}})

    async def script_error(self, script_id, errors):
        await self.transmit(
            {"type": "script_status", "script_status": {"source": "adapter", "id": script_id, "errors": errors}})

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
