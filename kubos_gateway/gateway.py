import asyncio
import logging

from kubos_gateway.major_tom import MajorTom
from kubos_gateway.satellite import Satellite
from kubos_gateway.telemetry_service import TelemetryService
from kubos_gateway.example_service import ExampleService
from kubos_gateway.application_service import ApplicationService


class Gateway(object):
    @staticmethod
    def run_forever(config):
        logging.info("Starting up!")
        loop = asyncio.get_event_loop()

        # Setup MajorTom
        major_tom = MajorTom(config)

        # Setup Satellite
        satellite = Satellite(
            host=config['sat-ip'],
            major_tom=major_tom,
            system_name=config['system-name'])
        major_tom.satellite = satellite

        # Connect to Major Tom
        asyncio.ensure_future(major_tom.connect_with_retries())

        # Initialize telemetry service so we can start the heartbeat
        telemetry_service = TelemetryService(8006)

        # Setup services. Note that registry order matters.
        # Put services with more specific `match` methods first.
        satellite.register_service(
            ApplicationService(8000),
            telemetry_service,
            ExampleService(8080)
        )

        loop.run_until_complete(satellite.start_services())

        # Start heartbeat
        asyncio.ensure_future(telemetry_service.start_heartbeat())

        loop.run_forever()
        loop.close()

    @staticmethod
    def set_log_level(log_level=logging.INFO, very_verbose=False):
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
