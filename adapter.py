import asyncio
import json
import logging

from major_tom import MajorTom
from sat import Sat

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

with open('config/config.local.json', 'r') as configfile:
    config = json.loads(configfile.read())


def main():
    logging.info("Starting up!")
    loop = asyncio.get_event_loop()

    sat = Sat(config)
    major_tom = MajorTom(config)

    # Tell the components about each other. We should probably create and register message handlers here.
    sat.major_tom = major_tom
    major_tom.sat = sat

    asyncio.ensure_future(sat.connect('telemetry', config['sat-ip'], 8005))
    asyncio.ensure_future(MajorTom.with_retries(major_tom.connect))

    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    main()
