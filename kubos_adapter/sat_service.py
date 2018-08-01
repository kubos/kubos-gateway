import asyncio
import json
import logging

from kubos_adapter.command_result import CommandResult
from kubos_adapter.major_tom import Command

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

    # TODO: "[Errno 61] Connection refused" never gets fed back to Major Tom.
    def error_received(self, exc):
        logger.info('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        logger.info("Socket closed")
        # self.loop.call_later(5, SatConnection.connect_to_sat())


class SatService:
    def __init__(self, name, port):
        self.name = name
        self.port = port
        self.transport = None
        self.protocol = None
        self.satellite = None

    async def connect(self):
        logger.info(f'Connecting to the {self.name} sat service')
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(lambda: SatConnectionProtocol(loop, self),
                                                                            remote_addr=(self.satellite.host, self.port))
        logger.info(f'Connected to {self.name} sat service')

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        # {'errs': '', 'msg': { errs: '..' }}
        if isinstance(message, dict) \
                and 'errs' in message \
                and len(message['errs']) > 0:
            await self.satellite.send_ack_to_mt(self.last_command_id,
                                                return_code=1,
                                                errors=[error["message"] for error in message['errs']])

        # [{'message': 'Unknown field "ping" on type "Query"', 'locations': [{'line': 1, 'column': 2}]}]
        elif isinstance(message, list) \
                and len(message) > 0 \
                and isinstance(message[0], dict) \
                and 'locations' in message[0]:
            await self.satellite.send_ack_to_mt(self.last_command_id,
                                                return_code=1,
                                                errors=[json.dumps(error) for error in message])

        else:
            await self.satellite.send_ack_to_mt(self.last_command_id,
                                                return_code=0,
                                                output=json.dumps(message))

    def validate_command(self, command: Command) -> CommandResult:
        command_result = CommandResult(command)

        # Handle commands supported by all services.
        if command.type == 'raw_telemetry_query':
            command_result.mark_as_matched()
            command_result.validate_presence("query", "Query is required")
            if command_result.valid():
                command_result.payload = command.fields["query"].strip()
        elif command.type == 'raw_mutation':
            command_result.mark_as_matched()
            command_result.validate_presence("mutation", "Mutation is required")
            if command_result.valid():
                command_result.payload = command.fields["mutation"].strip()

        return command_result

    def match(self, command):
        return command.subsystem == self.name
