import asyncio
import json
import logging
import aiohttp

from kubos_gateway.command_result import CommandResult
from kubos_gateway.major_tom import Command

logger = logging.getLogger(__name__)


class SatService:
    def __init__(self, name, port):
        self.name = name
        self.port = port
        self.satellite = None
        self.session = None
        self.last_command_id = None

    async def connect(self):
        logger.info(f'Connecting to the {self.name} sat service')
        loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=loop)
        logger.info(f'Connected to {self.name} sat service')

    async def query(self, query):
        query = query.replace("\n", "")
        query = query.replace("\t", "")
        query = query.replace(" ", "")
        wrapped_query = '{"query":"%s"}' % query
        logger.debug(f'{self.name} wrapped query {wrapped_query}')
        async with self.session.request(
                method='POST',
                url="http://{}:{}".format(self.satellite.host, self.port),
                data=wrapped_query,
                headers={"Content-Type":"application/json"}
        ) as resp:
            body = await resp.read()
            await self.message_received(json.loads(body))

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        # {'errs': '', 'msg': { errs: '..' }}
        if isinstance(message, dict) \
                and 'errs' in message \
                and len(message['errs']) > 0:
            await self.satellite.send_ack_to_mt(
                self.last_command_id,
                return_code=1,
                errors=[error["message"] for error in message['errs']])

        # [{'message': 'Unknown field "ping" on type "Query"',
        #   'locations': [{'line': 1, 'column': 2}]}]
        elif isinstance(message, list) \
                and len(message) > 0 \
                and isinstance(message[0], dict) \
                and 'locations' in message[0]:
            await self.satellite.send_ack_to_mt(
                self.last_command_id,
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
            command_result.validate_presence(
                "mutation", "Mutation is required")
            if command_result.valid():
                command_result.payload = command.fields["mutation"].strip()

        return command_result

    def match(self, command):
        return False
