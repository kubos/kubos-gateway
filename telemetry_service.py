import asyncio
import json
import logging
import time

from sat_service import SatService

logger = logging.getLogger(__name__)


class TelemetryService(SatService):
    def __init__(self, host, port, path_prefix):
        super().__init__('telemetry', host, port)
        self.path_prefix = path_prefix

    async def message_received(self, message):
        logger.info("Received: {}".format(message))

        # {'errs': '', 'msg': {'telemetry': [
        #   {'parameter': 'voltage', 'subsystem': 'eps', 'timestamp': -1975424672, 'value': '0.15'},
        #   ...

        await self.major_tom.transmit_metrics([
            {
                # Major Tom expects path to look like 'team.mission.system.subsystem.metric'
                "path": '.'.join([self.path_prefix, telemetry['subsystem'], telemetry['parameter']]),

                "value": telemetry['value'],

                # Timestamp is expected to be millisecond unix epoch
                # "timestamp": telemetry['timestamp']
                "timestamp": int(time.time()) * 1000
            } for telemetry in message['msg']['telemetry']
        ])

    async def request(self):
        query = """
          { telemetry { timestamp, subsystem, parameter, value } }
        """
        logger.info('Sent: {}'.format(query))
        self.transport.sendto(query.encode())
