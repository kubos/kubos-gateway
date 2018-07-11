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
        self.queued_payloads = []

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
        await self.empty_queue()
        async for message in websocket:
            await self.handle_message(message)

    async def connect_with_retries(self):
        while True:
            try:
                return await self.connect()
            except (OSError, asyncio.streams.IncompleteReadError, websockets.ConnectionClosed) as e:
                self.websocket = None
                logger.warning("Connection error encountered, retrying in 5 seconds ({})".format(e))
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("Unhandled {} in `with_retries`".format(e.__class__.__name__))
                raise e

    # ActionCable channel subscribe
    async def subscribe(self):
        await self.websocket.send(json.dumps({
            "command": "subscribe",
            "identifier": json.dumps({"channel": "GatewayChannel"})
        }))

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

    # ActionCable wrapping
    async def transmit(self, payload):
        logger.debug("To Major Tom: {}".format(payload))
        if self.websocket:
            await self.websocket.send(json.dumps({
                "command": "message",
                "identifier": json.dumps({"channel": "GatewayChannel"}),
                "data": json.dumps(payload)
            }))
        else:
            # Switch to https://docs.python.org/3/library/asyncio-queue.html
            self.queued_payloads.append(payload)

    async def empty_queue(self):
        while len(self.queued_payloads) > 0 and self.websocket:
            payload = self.queued_payloads.pop(0)
            await self.transmit(payload)

    async def transmit_metrics(self, metrics):
        await self.transmit({
            "type": "measurements",
            "measurements": [
                {
                    # Major Tom expects path to look like 'team.mission.system.subsystem.metric'
                    "path": metric["path"],

                    "value": metric["value"],

                    # Timestamp is expected to be millisecond unix epoch
                    "timestamp": metric["timestamp"]
                } for metric in metrics
            ]
        })

    async def command_error(self, command_id, errors):
        await self.transmit({
            "type": "command_status",
            "command_status": {
                "source": "adapter",
                "id": command_id,
                "errors": errors
            }
        })

    async def script_error(self, script_id, errors):
        await self.transmit({
            "type": "script_status",
            "script_status": {
                "source": "adapter",
                "id": script_id,
                "errors": errors
            }
        })
