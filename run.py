import json
import logging

from kubos_adapter.adapter import Adapter

with open('config/config.local.json', 'r') as configfile:
    config = json.loads(configfile.read())

Adapter.set_log_level(logging.DEBUG)
Adapter.run_forever(config)
