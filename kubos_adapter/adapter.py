import asyncio
import logging

from kubos_adapter.major_tom import MajorTom
from kubos_adapter.satellite import Satellite
from kubos_adapter.telemetry_service import TelemetryService
from kubos_adapter.example_service import ExampleService
from kubos_adapter.application_service import ApplicationService
from kubos_adapter.pumpkin_mcu_service import PumpkinMCUService


class Adapter(object):
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
            path_prefix_to_subsystem=config['path-prefix-to-subsystem'])
        major_tom.satellite = satellite

        # Connect to Major Tom
        asyncio.ensure_future(major_tom.connect_with_retries())

        # Initialize telemetry service so we can start the heartbeat
        telemetry_service = TelemetryService(8005)

        # Setup services. Note that registry order matters.
        # Put services with more specific `match` methods first.
        satellite.register_service(
            ApplicationService(8000),
            telemetry_service,
            PumpkinMCUService(8004),
            ExampleService(8080)
        )

        loop.run_until_complete(satellite.start_services())

        asyncio.ensure_future(telemetry_service.start_heartbeat())

        loop.run_forever()
        loop.close()

    @staticmethod
    def set_log_level(log_level=logging.INFO, very_verbose=False):
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        if not very_verbose:
            logging.getLogger('asyncio').setLevel(logging.WARNING)
            logging.getLogger('websockets.protocol').setLevel(logging.INFO)
