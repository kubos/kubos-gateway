import asyncio
import json
import logging

from major_tom import MajorTom
from satellite import Satellite
from telemetry_service import TelemetryService

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('websockets.protocol').setLevel(logging.INFO)

with open('config/config.local.json', 'r') as configfile:
    config = json.loads(configfile.read())


def main():
    logging.info("Starting up!")
    loop = asyncio.get_event_loop()

    # Setup MajorTom
    major_tom = MajorTom(config)

    # Setup Satellite
    satellite = Satellite(host=config['sat-ip'],
                          major_tom=major_tom,
                          path_prefix_to_subsystem='kubos.hamilton.hamilton-1')
    major_tom.satellite = satellite

    # Connect to Major Tom
    asyncio.ensure_future(major_tom.connect_with_retries())

    # Setup TelemetryService
    satellite.register_service(TelemetryService(8005))

    loop.run_until_complete(satellite.start_services())
    # asyncio.ensure_future(telemetry_service.request())

    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    main()
