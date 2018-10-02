import logging
import json

from kubos_gateway.command_result import CommandResult
from kubos_gateway.major_tom import Command
from kubos_gateway.sat_service import SatService

logger = logging.getLogger(__name__)

"""
passthrough query and mutation
"""


class PumpkinMCUService(SatService):
    def __init__(self, port):
        super().__init__('application', port)

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        if isinstance(message, dict) \
                and 'msg' in message\
                and message['msg'] is not []:
            await self.satellite.send_ack_to_mt(
                self.last_command_id,
                return_code=0,  # No error
                output=json.dumps(message),
                errors=[])

        else:
            super().message_received(message)

    def validate_command(self, command: Command) -> CommandResult:
        command_result = super().validate_command(command)

        if command.type == 'scpi_command':
            command_result.mark_as_matched()
            mutation = """
              mutation {
                    passthrough(module: "%s",
                                command: "%s") {
                        status,
                        command
                    }
                }
            """ % (command.subsystem, command.fields["SCPI Command"])
            command_result.payload = mutation.strip()
        else:
            command_result.errors.append(
                "No command of type: {}".format(command.type))
        return command_result

    def match(self, command):
        # Matches all subsystems
        if (command.subsystem in [
                "pim", "bim", "gpsrm", "sim",
                "bm2", "aim2", "bsm", "rhm",
                "pumpkin_mcu_service"]):
            return True
        return False
