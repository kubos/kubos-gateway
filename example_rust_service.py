import json
import logging

from command_result import CommandResult
from sat_service import SatService

logger = logging.getLogger(__name__)


class ExampleRustService(SatService):
    def __init__(self, port):
        super().__init__('example_rust_service', port)
        self.last_command_id = None

    async def message_received(self, message):
        # {'errs': '', 'msg': {'setPower': {'power': True}}}
        logger.info("Received: {}".format(message))

        if len(message['errs']) > 0:
            await self.satellite.send_command_ack_to_major_tom(self.last_command_id,
                                                               errors=[error["message"] for error in message['errs']],
                                                               return_code=1)
        else:
            await self.satellite.send_command_ack_to_major_tom(self.last_command_id,
                                                               return_code=0,
                                                               output=ExampleRustService.pretty_message(message))

    async def handle_command(self, command):
        command_result = CommandResult(command)

        if command.type == 'set_power':
            command.fields['power'] = True if command.fields['power'] == 1 else False  # FIXME in Major Tom
            command_result.validate_boolean("power", "power must be a boolean value")
            if command_result.valid():
                query = """
                  mutation { setPower(power: %s) { power } }
                """ % ('true' if command.fields["power"] else 'false')
                command_result.payload = query.strip()
                logger.info('Sent: {}'.format(command_result.payload))
                self.last_command_id = command.id  # FIXME, this is a big hack.
                self.transport.sendto(command_result.payload.encode())
                command_result.sent = True
        elif command.type == 'calibrate_thermometer':
            query = """
              mutation { calibrateThermometer { temperature } }
            """
            command_result.payload = query.strip()
            logger.info('Sent: {}'.format(command_result.payload))
            self.last_command_id = command.id  # FIXME
            self.transport.sendto(command_result.payload.encode())
            command_result.sent = True
        else:
            command_result.errors.append(f"Unknown command {command.type}")

        return command_result

    def match(self, command):
        return command.type in ["calibrate_thermometer", "set_power"]

    @staticmethod
    def pretty_message(message):
        if message['msg'].get('setPower'):
            return "Power is now {}".format(message['msg']['setPower']['power'])
        elif message['msg'].get('calibrateThermometer'):
            return "Temperature is now {}".format(message['msg']['calibrateThermometer']['temperature'])
        else:
            return json.dumps(message['msg'])
