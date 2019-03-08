#!/usr/bin/env python

import time
import csv
from datetime import datetime
import os
import traceback
from random import randint
import asyncio
import logging


class DemoDataStreaming(object):
    def __init__(self,config):
        self.system_name = config["system-name"]

    @staticmethod
    def run_forever(config):
        from kubos_gateway.major_tom import MajorTom

        logging.info("Starting up!")
        loop = asyncio.get_event_loop()

        # Setup MajorTom
        major_tom = MajorTom(config)

        # Connect to Major Tom
        asyncio.ensure_future(major_tom.connect_with_retries())

        # Initialize fake data streaming service
        tlm_stream = DemoDataStreaming(config)

        # Start streaming recorded satellite data
        asyncio.ensure_future(tlm_stream.power_tlm(major_tom))

        loop.run_forever()
        loop.close()

    async def power_tlm(self, major_tom, time_multiplier=100):
        await asyncio.sleep(5) # wait 5 seconds to start
        logging.info("power_tlm: Starting power telemetry for system {} at {} times recorded speed".format(self.system_name,time_multiplier))
        while True:
            try:
                logging.info("power_tlm: Opening Telemetry File")
                dir_path = os.path.dirname(os.path.realpath(__file__))
                with open(dir_path + "/power_tlm.csv") as tlm_csv:
                    tlm = csv.reader(tlm_csv, delimiter=',')
                    block = []
                    line = 0
                    for row in tlm:
                        line += 1
                        rowtime = datetime.strptime(row[4], '%Y.%m.%d %H:%M:%S %Z')
                        logging.debug("power_tlm: rowtime: " + str(rowtime))
                        # Account for first line
                        if line == 1:
                            previous_rowtime = rowtime

                        if rowtime == previous_rowtime:
                            block.append(row)
                            # Makes sure the last line is sent
                            if line == 383837:  # Last line
                                await self.send_measurements(major_tom, block)
                                logging.info("power_tlm: last line")
                                await asyncio.sleep(1 * 60)  # Sleep 1 minute before repeating
                        elif rowtime != previous_rowtime:
                            # Sends measurements when the next timestamp is reached
                            delta = rowtime - previous_rowtime
                            previous_rowtime = rowtime
                            logging.debug("power_tlm: Sending measurements, time delta: " + \
                                          str(delta.total_seconds()))
                            await self.send_measurements(major_tom, block)
                            block = []
                            block.append(row)
                            await asyncio.sleep((delta.total_seconds()) / time_multiplier)
            except Exception as e:
                logging.error(traceback.format_exc())
                await asyncio.sleep(60)

    async def send_measurements(self, major_tom, block):
        metrics = []

        for measurement in block:
            metrics.append({
                "system": self.system_name,
                "subsystem": measurement[0].replace(" ", "_"),
                "metric": measurement[1].replace(" ", "_"),
                "value": float(measurement[2]),
                "timestamp": int(time.time() * 1000)
            })

        await major_tom.transmit_metrics(metrics=metrics)
