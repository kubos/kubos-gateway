import asyncio
import logging

from command_result import CommandResult
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

        await self.satellite.send_metrics_to_major_tom(message['msg']['telemetry'])

    async def handle_command(self, command):
        command_result = CommandResult(command)

        if command.type == 'telemetry':
            command_result.validate_range("limit", 0, 10, int, "Limit must be between 0 and 10")
            command_result.validate_presence("subsystem", "Subsystem is required")  # FIXME
            if command_result.valid():
                query = """
                  { telemetry(limit: %i, subsystem: "%s") { timestamp, subsystem, parameter, value } }
                """ % (command.fields["limit"], command.fields["subsystem"])
                command_result.payload = query.strip()
                logger.info('Sent: {}'.format(command_result.payload))
                self.transport.sendto(command_result.payload.encode())
                command_result.sent = True
        else:
            command_result.errors.append(f"Unknown command {command.type}")

        return command_result

    def match(self, command):
        return command.type == "telemetry"

    async def start_request(self):
        while True:
            await self.request()
            await asyncio.sleep(10)

    async def request(self):
        query = """
          { telemetry { timestamp, subsystem, parameter, value } }
        """
        logger.info('Sent: {}'.format(query))
        self.transport.sendto(query.encode())
