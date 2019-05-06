import asyncio
import json
import os
import re
import ssl
import logging
import time
import traceback

import websockets

from kubos_gateway.command import Command
from kubos_gateway.satellite import Satellite

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
            ## Here is where we can build in sending to multiple systems/satellites
            if command.system == self.satellite.system_name:
                try:
                    await self.satellite.send_cmd(command)
                except Exception:
                    await self.fail_command(command.id, errors=["Failed to send","Error: {}".format(traceback.format_exc())])
            else:
                await self.fail_command(command.id, errors=["System: {} not available".format(command.system)])
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

    async def transmit_command_update(self, command_id: int, state: str, dict = {}):
        update = {
            "type": "command_update",
            "command": {
                "id": command_id,
                "state": state
            }
        }
        valid_fields = [
            "payload",
            "status",
            "output",
            "errors",
            "progress_1_current",
            "progress_1_max",
            "progress_1_label",
            "progress_2_current",
            "progress_2_max",
            "progress_2_label"
        ]

        for field in dict:
            if field in valid_fields:
                update['command'][field] = dict[field]
            else:
                logger.error('Field {} is not a valid metadata field. \nValid fields: {}'.format(field,valid_fields))
        await self.transmit(update)

    async def fail_command(self, command_id, errors: list):
        await self.transmit_command_update(command_id = command_id, state = "failed", dict = {"errors":errors})

    async def complete_command(self, command_id, output: str):
        await self.transmit_command_update(command_id = command_id, state = "completed", dict = {"output":output})

    async def transmitted_command(self, command_id, payload = "None Provided"):
        await self.transmit_command_update(command_id = command_id, state = "transmitted_to_system", dict = {"payload":payload})
