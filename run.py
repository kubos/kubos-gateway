import json
import logging
import sys

from kubos_adapter.adapter import Adapter

if len(sys.argv) > 1:
  config_file = sys.argv[1]
else:
  config_file = 'config/config.local.json'

with open(config_file, 'r') as configfile:
    config = json.loads(configfile.read())

Adapter.set_log_level(logging.DEBUG, very_verbose=False)
Adapter.run_forever(config)
