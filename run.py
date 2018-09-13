import json
import logging
import sys

from kubos_adapter.adapter import Adapter

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = 'config/config.local.json'

with open(config_file, 'r') as configfile:
    # Allow "comments" in JSON for convenience.
    config = json.loads("\n".join([line for line in configfile if not line.startswith('/') or line.startswith('#')]))

Adapter.set_log_level(logging.DEBUG, very_verbose=False)
Adapter.run_forever(config)
