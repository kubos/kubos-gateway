import asyncio
import time

from command_result import CommandResult


class Satellite:
    def __init__(self, major_tom, host, path_prefix_to_subsystem):
        self.major_tom = major_tom
        self.host = host
        self.path_prefix_to_subsystem = path_prefix_to_subsystem
        self.registry = {}

    def register_service(self, *service):
        for service in service:
            self.registry[service.name] = service
            service.satellite = self

    async def send_metrics_to_major_tom(self, metrics):
        # {'parameter': 'voltage', 'subsystem': 'eps', 'timestamp': 1531412196211.0, 'value': '0.15'}
        await self.major_tom.transmit_metrics([
            {
                # Major Tom expects path to look like 'team.mission.system.subsystem.metric'
                "path": '.'.join([self.path_prefix_to_subsystem, metric['subsystem'], metric['parameter']]),

                "value": metric['value'],

                # Timestamp is expected to be millisecond unix epoch
                # "timestamp": int(metric['timestamp'])
                # FIXME
                "timestamp": int(time.time()) * 1000
            } for metric in metrics
        ])

    async def send_command_ack_to_major_tom(self, command_id, return_code, output=None, errors=None):
        await self.major_tom.transmit_command_ack(command_id, return_code, output, errors)

    async def handle_command(self, command):
        routes = [service for service in self.registry.values() if service.match(command)]
        if len(routes) == 0:
            service = self.registry.get(command.subsystem)
            if service:
                return await service.handle_command(command)
            else:
                return CommandResult(command, error=f"No service was available to process command {command.type} for "
                                                    f"subsystem {command.subsystem}")
        elif len(routes) > 1:
            return CommandResult(command, error=f"Adapter error: multiple services matched command {command.type}")
        else:
            return await routes[0].handle_command(command)

    async def start_services(self):
        await asyncio.gather(*[service.connect() for service in self.registry.values()])
