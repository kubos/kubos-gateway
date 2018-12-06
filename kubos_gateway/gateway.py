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

        # from random import randint
        # import time
        # loop.run_until_complete(major_tom.transmit({
        #     'type': 'measurements',
        #     'measurements': [{'path': 'kubos.mission0.satellite14.pim.metric' + str(randint(0, 20)), 'value': randint(0, 100), 'timestamp': int((time.time() - 120) * 1000) + j} for j in range(0, 20)]
        # }))

        # loop.run_until_complete(major_tom.transmit_log_messages([{ "message": "Testing nominal", "path": config['path-prefix-to-subsystem'] }, { "message": "Testing error", "level": "error", "path": config['path-prefix-to-subsystem'] }]))

        asyncio.ensure_future(telemetry_service.start_heartbeat())

        loop.run_forever()
        loop.close()

    @staticmethod
    def set_log_level(log_level=logging.INFO, very_verbose=False):
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
