import asyncio
import logging

from command_result import CommandResult
from major_tom import Command
from sat_service import SatService

logger = logging.getLogger(__name__)


class TelemetryService(SatService):
    def __init__(self, port):
        super().__init__('telemetry', port)

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        # {'errs': '', 'msg': {'telemetry': [
        #   {'parameter': 'voltage', 'subsystem': 'eps', 'timestamp': 1531412196211.0, 'value': '0.15'},
        #   ...

        await self.satellite.send_metrics_to_mt(message['msg']['telemetry'])

    def validate_command(self, command: Command) -> CommandResult:
        command_result = super().validate_command(command)

        if command.type == 'telemetry':
            command_result.mark_as_matched()
            command_result.validate_range("limit", 0, 10, int, "Limit must be between 0 and 10")
            command_result.validate_presence("subsystem", "Subsystem is required")  # FIXME
            if command_result.valid():
                query = """
                  { telemetry(limit: %i, subsystem: "%s") { timestamp, subsystem, parameter, value } }
                """ % (command.fields["limit"], command.fields["subsystem"])
                command_result.payload = query.strip()

        return command_result

    def match(self, command):
        return command.type == "telemetry"  # Matches all subsystems

    async def start_heartbeat(self):
        while True:
            query = """
                      { telemetry { timestamp, subsystem, parameter, value } }
                    """
            # self.transport.sendto(query.encode())
            await asyncio.sleep(10)
