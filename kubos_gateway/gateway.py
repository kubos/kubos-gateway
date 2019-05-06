import asyncio
import logging

from kubos_gateway.major_tom import MajorTom
from kubos_gateway.satellite import Satellite


class Gateway(object):
    @staticmethod
    def run_forever(config):
        logging.info("Starting up!")
        loop = asyncio.get_event_loop()

        # Setup MajorTom
        major_tom = MajorTom(config)

        # Setup Satellite(s)
        satellite = Satellite(
            system_name=config['system-name'],
            major_tom=major_tom,
            send_port=config['comm-service-port'],
            receive_port=config['receive-port'],
            host=config['sat-ip'],
            bind=config['bind-ip'])
        major_tom.satellite = satellite

        # Connect to Satellite
        asyncio.ensure_future(satellite.connect())

        # Connect to Major Tom
        asyncio.ensure_future(major_tom.connect_with_retries())


        loop.run_forever()
        loop.close()

    @staticmethod
    def set_log_level(log_level=logging.INFO, very_verbose=False):
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
