import asyncio
import json
import logging

from major_tom import MajorTom
from telemetry_service import TelemetryService

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('websockets.protocol').setLevel(logging.INFO)

with open('config/config.local.json', 'r') as configfile:
    config = json.loads(configfile.read())


def main():
    logging.info("Starting up!")
    loop = asyncio.get_event_loop()

    telemetry_service = TelemetryService(config['sat-ip'], 8005, 'phase-four.rose-1.rose-1')
    major_tom = MajorTom(config)

    # Tell the components about each other. We should probably create and register message handlers here.
    telemetry_service.major_tom = major_tom

    asyncio.ensure_future(major_tom.connect_with_retries())

    loop.run_until_complete(telemetry_service.connect())
    asyncio.ensure_future(telemetry_service.request())

    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    main()
