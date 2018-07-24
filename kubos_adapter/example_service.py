import json
import logging

from kubos_adapter.command_result import CommandResult
from kubos_adapter.major_tom import Command
from kubos_adapter.sat_service import SatService

logger = logging.getLogger(__name__)


class ExampleService(SatService):
    def __init__(self, port):
        super().__init__('example_service', port)
        self.last_command_id = None  # FIXME - this should be handled by the satellite, not guessed by the adapter.

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        # {'errs': '', 'msg': {'setPower': {'power': True}}}
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
                                                output=ExampleService.pretty_message(message))

    def validate_command(self, command: Command) -> CommandResult:
        command_result = super().validate_command(command)

        if command.type == 'set_power':
            command_result.mark_as_matched()
            command.fields['power'] = True if command.fields['power'] == 1 else False  # FIXME in Major Tom
            command_result.validate_boolean("power", "power must be a boolean value")
            if command_result.valid():
                query = """
                  mutation { setPower(power: %s) { power } }
                """ % ('true' if command.fields["power"] else 'false')
                command_result.payload = query.strip()
        elif command.type == 'calibrate_thermometer':
            command_result.mark_as_matched()
            query = """
              mutation { calibrateThermometer { temperature } }
            """
            command_result.payload = query.strip()

        return command_result

    def match(self, command):
        return super().match(command)

    @staticmethod
    def pretty_message(message):
        if 'msg' not in message:
            return json.dumps(message)
        elif message['msg'].get('setPower'):
            return "Power is now {}".format(message['msg']['setPower']['power'])
        elif message['msg'].get('calibrateThermometer'):
            return "Temperature is now {}".format(message['msg']['calibrateThermometer']['temperature'])
        else:
            return json.dumps(message['msg'])
