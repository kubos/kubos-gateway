import asyncio
import json
import os
import re
import ssl
import logging
import time

import websockets

from kubos_gateway.command import Command
from kubos_gateway.command_result import CommandResult

logger = logging.getLogger(__name__)


class MajorTom:
    def __init__(self, config):
        self.config = config
        self.websocket = None
        self.queued_payloads = []
        self.satellite = None

    async def connect(self):
        if re.match(r"^wss://", self.config["major-tom-endpoint"], re.IGNORECASE):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

            if "ssl-verify" not in self.config or self.config["ssl-verify"] is True:
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                ssl_context.check_hostname = True
                # Should probably fetch from https://curl.haxx.se/docs/caextract.html
                ssl_context.load_verify_locations(self.config["ssl-ca-bundle"])
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        else:
            ssl_context = None

        logger.info("Connecting to Major Tom")
        websocket = await websockets.connect(self.config["major-tom-endpoint"],
                                             extra_headers={
                                                 "X-Gateway-Token": self.config["gateway-token"]
                                             },
                                             ssl=ssl_context)
        logger.info("Connected to Major Tom")
        self.websocket = websocket
        await asyncio.sleep(1)
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
                logger.error("Unhandled {} in `connect_with_retries`".format(e.__class__.__name__))
                raise e

    async def handle_message(self, json_data):
        message = json.loads(json_data)
        message_type = message["type"]
        logger.info("From Major Tom: {}".format(message))
        if message_type == "command":
            command = Command(message["command"])
            command_result: CommandResult = await self.satellite.handle_command(command)
            if command_result.sent:
                await self.transmit_command_payload(command.id, command_result.payload)
            else:
                await self.transmit_command_error(command.id, command_result.errors)
        elif message_type == "error":
            logger.error("Error from Major Tom: {}".format(message["error"]))
        elif message_type == "hello":
            logger.info("Major Tom says hello: {}".format(message))
        else:
            logger.warning("Unknown message type {} received from Major Tom: {}".format(message_type, message))

    async def empty_queue(self):
        while len(self.queued_payloads) > 0 and self.websocket:
            payload = self.queued_payloads.pop(0)
            await self.transmit(payload)

    async def transmit(self, payload):
        if self.websocket:
            logger.debug("To Major Tom: {}".format(payload))
            await self.websocket.send(json.dumps(payload))
        else:
            # Switch to https://docs.python.org/3/library/asyncio-queue.html
            self.queued_payloads.append(payload)

    async def transmit_metrics(self, metrics):
        await self.transmit({
            "type": "measurements",
            "measurements": [
                {
                    "system": metric["system"],
                    "subsystem": metric["subsystem"],
                    "metric": metric["metric"],
                    "value": metric["value"],
                    # Timestamp is expected to be millisecond unix epoch
                    "timestamp": metric["timestamp"]
                } for metric in metrics
            ]
        })

    async def transmit_log_messages(self, log_messages):
        await self.transmit({
            "type": "log_messages",
            "log_messages": [
                {
                    "system": log_message["system"],

                    # Can be "debug", "nominal", "warning", or "error".
                    "level": log_message.get("level", "nominal"),

                    "message": log_message["message"],

                    # Timestamp is expected to be millisecond unix epoch
                    "timestamp": log_message.get("timestamp", int(time.time() * 1000))
                } for log_message in log_messages
            ]
        })

    async def transmit_command_payload(self, command_id, payload):
        await self.transmit({
            "type": "command_status",
            "command_status": {
                "source": "gateway",
                "id": command_id,
                "payload": payload
            }
        })

    async def transmit_command_ack(self, command_id, return_code, output, errors):
        await self.transmit({
            "type": "command_status",
            "command_status": {
                "source": "remote",
                "id": command_id,
                "errors": errors,
                "code": return_code,
                "output": output
            }
        })

    async def transmit_command_error(self, command_id, errors):
        await self.transmit({
            "type": "command_status",
            "command_status": {
                "source": "gateway",
                "id": command_id,
                "errors": errors
            }
        })

    async def transmit_script_error(self, script_id, errors):
        await self.transmit({
            "type": "script_status",
            "script_status": {
                "source": "gateway",
                "id": script_id,
                "errors": errors
            }
        })
