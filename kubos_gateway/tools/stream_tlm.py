#!/usr/bin/env python

import time
import csv
from datetime import datetime
import os
import traceback
from random import randint
import asyncio
import logging


class TelemetryStreaming(object):
    def __init__(self):
        pass

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
        tlm_stream = TelemetryStreaming()

        # Start streaming fixed rate random data
        asyncio.ensure_future(tlm_stream.fixed_rate(major_tom))

        loop.run_forever()
        loop.close()

    async def fixed_rate(self, major_tom, frequency_in_hz=1, num_systems=1, num_subsystems=1, num_metrics=1):
        await asyncio.sleep(5)
        logging.info(
            "fixed_rate: sent measurements. {} systems {} subsystems {} metrics at {} Hz".format(
                num_systems, num_subsystems, num_metrics, frequency_in_hz))
        while True:
            metrics = []
            for sys in range(num_systems):
                for sub in range(num_subsystems):
                    for metric in range(num_metrics):
                        metrics.append({
                            "system": "test system " + str(sys),
                            "subsystem": "test subsystem " + str(sub),
                            "metric": "test metric " + str(metric),
                            "value": randint(-100000, 100000),
                            "timestamp": int(time.time() * 1000)
                        })

            await major_tom.transmit_metrics(metrics=metrics)
            logging.info("fixed_rate: sent measurements")
            await asyncio.sleep(1 / frequency_in_hz)

    async def send_measurements(self, major_tom, block):
        metrics = []

        for measurement in block:
            metrics.append({
                "system": "Jesse Test",
                "subsystem": measurement[0].replace(" ", "_"),
                "metric": measurement[1].replace(" ", "_"),
                "value": float(measurement[2]),
                "timestamp": int(time.time() * 1000)
            })

        await major_tom.transmit_metrics(metrics=metrics)
