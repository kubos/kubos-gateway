import asyncio
import logging

from kubos_adapter.command_result import CommandResult
from kubos_adapter.major_tom import Command

logger = logging.getLogger(__name__)


class Satellite:
    def __init__(self, major_tom, host, path_prefix_to_subsystem):
        self.major_tom = major_tom
        self.host = host
        self.path_prefix_to_subsystem = path_prefix_to_subsystem
        self.registry = []

    def register_service(self, *services):
        for service in services:
            self.registry.append(service)
            service.satellite = self

    async def send_metrics_to_mt(self, metrics):
        # {'parameter': 'voltage', 'subsystem': 'eps',
        #  'timestamp': 1531412196211.0, 'value': '0.15'}
        for metric in metrics:
            if type(metric['value']) is not float:
                if metric['value'] in ['true', 'True']:
                    metric['value'] = 1.0
                elif metric['value'] in ['false', 'False']:
                    metric['value'] = 0.0
                try:
                    metric['value'] = float(metric['value'])
                except ValueError as e:
                    logger.warning("parameter: {}, subsystem: {}".format(
                            metric['parameter'],
                            metric['subsystem']
                        )+" has invalid string value " +
                        ": {} : Converting to 0".format(metric['value']))
                    metric['value'] = 0
            # Convert subsystem names and parameter names to lower case and
            # replace spaces with dashes TODO: make it enforce alphanumeric
            metric['subsystem'] = metric['subsystem'].replace(' ', '-').lower()
            metric['parameter'] = metric['parameter'].replace(' ', '-').lower()
        await self.major_tom.transmit_metrics([
            {
                # Major Tom expects path to look like:
                # 'team.mission.system.subsystem.metric'
                "path": '.'.join(
                    [
                        self.path_prefix_to_subsystem,
                        metric['subsystem'], metric['parameter']
                    ]),

                "value": metric['value'],

                # Timestamp is expected to be millisecond unix epoch
                "timestamp": int(metric['timestamp'])
            } for metric in metrics
        ])

    async def send_ack_to_mt(
            self, command_id, return_code, output=None, errors=None):
        await self.major_tom.transmit_command_ack(
            command_id, return_code, output, errors)

    async def handle_command(self, command: Command) -> CommandResult:
        matched_services = [
            service for service in self.registry if service.match(command)]
        if len(matched_services) == 0:
            return CommandResult(
                command,
                error=(
                    "No service was available to process command for "
                    f"{command.type} subsystem {command.subsystem}"))
        else:
            matched_service = matched_services[0]

            if len(matched_services) > 1:
                logger.info(
                    f"Multiple services matched command {command.type}."
                    f" Selected '{matched_service.name}'.")

            command_result: CommandResult = matched_service.validate_command(
                command)

            if not command_result.matched:
                command_result.errors.append(f"Unknown command {command.type}")

            if command_result.valid():
                matched_service.last_command_id = command.id  # FIXME
                logger.info('Sending to {}: {}'.format(
                    matched_service.name, command_result.payload))
                matched_service.transport.sendto(
                    command_result.payload.encode())
                command_result.mark_as_sent()

            return command_result

    async def start_services(self):
        await asyncio.gather(*[service.connect() for service in self.registry])
