import logging
import json

from kubos_gateway.command_result import CommandResult
from kubos_gateway.major_tom import Command
from kubos_gateway.sat_service import SatService

logger = logging.getLogger(__name__)

"""
passthrough query and mutation
"""


class ApplicationService(SatService):
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
            await super().message_received(message)

    def validate_command(self, command: Command) -> CommandResult:
        command_result = super().validate_command(command)

        if command.type == 'register_app':
            command_result.mark_as_matched()
            mutation = """
              mutation {
                    register(path: "%s") {
                        active,
                        app {
                            name,
                            version
                        }
                    }
                }
            """ % (command.fields["Path"])
            command_result.payload = mutation.strip()
        elif command.type == 'app_query':
            command_result.mark_as_matched()
            query = """
                {
                    apps {
                        active,
                        app {
                            uuid,
                            name,
                            version
                        }
                    }
                }
            """
            command_result.payload = query.strip()
        elif command.type in ['run_app', 'deploy_ants']:
            command_result.mark_as_matched()
            query = """
                mutation {
                    startApp(uuid: "%s", runLevel: "%s")
                }
            """ % (command.fields["UUID"], command.fields["Run Level"])
            command_result.payload = query.strip()
        elif command.type == 'python_app':
            command_result.mark_as_matched()
            query = """
                mutation {
                    startApp(
                        uuid: "%s",
                        runLevel: "%s",
                        args: ["-s", "%s", "-i", "%d"])
                }
            """ % (command.fields["UUID"],
                   command.fields["Run Level"],
                   command.fields["String Argument"],
                   command.fields["Integer Argument"])
            command_result.payload = query.strip()
        else:
            command_result.errors.append(
                "No application command of type: {}".format(command.type))
        return command_result

    def match(self, command):
        if command.type == "app_query":
            return True
        return False
