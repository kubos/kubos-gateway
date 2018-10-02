import json
import logging

from kubos_gateway.command_result import CommandResult
from kubos_gateway.major_tom import Command
from kubos_gateway.sat_service import SatService

logger = logging.getLogger(__name__)


class ExampleService(SatService):
    def __init__(self, port):
        super().__init__('example_service', port)
        self.last_command_id = None  # FIXME - this should be handled by the satellite, not guessed by the gateway.

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        if message.get('msg').get('setPower') or message.get('msg').get('calibrateThermometer'):
            await self.satellite.send_ack_to_mt(self.last_command_id,
                                                return_code=0,
                                                output=ExampleService.pretty_message(message))
        else:
            super().message_received(message)

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
